from __future__ import annotations

import argparse
import json
import sys
import time
from collections import Counter
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

import httpx
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from formscope.config import SEC_TIMEOUT, SEC_USER_AGENT
from formscope.financials import TAG_CANDIDATES
from formscope.sec_client import ARCHIVES_BASE, HEADERS, company_facts, company_submissions, company_tickers
from formscope.service import company_report

TICKERS = ("AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "ORCL", "TSLA", "CSCO", "INTC", "AMD", "QCOM", "NFLX", "DIS", "KO", "PG", "WMT", "COST", "PFE", "CRM")
FIXTURE_PATH = ROOT / "data" / "financial-ground-truth-20.json"
REPORT_PATH = ROOT / "reports" / "financial-ground-truth-results.json"


def local_name(tag: Any) -> str:
    return str(tag.name or "").lower().rsplit(":", 1)[-1]


def inline_duration_contexts(soup: BeautifulSoup, report_date: str) -> dict[str, tuple[str, str]]:
    contexts = {}
    for context in soup.find_all(lambda tag: local_name(tag) == "context"):
        if context.find(lambda tag: local_name(tag) in {"segment", "explicitmember", "typedmember"}):
            continue
        start_tag = context.find(lambda tag: local_name(tag) == "startdate")
        end_tag = context.find(lambda tag: local_name(tag) == "enddate")
        if not start_tag or not end_tag:
            continue
        start = start_tag.get_text(strip=True)
        end = end_tag.get_text(strip=True)
        try:
            days = (date.fromisoformat(end) - date.fromisoformat(start)).days
        except ValueError:
            continue
        if end == report_date and 330 <= days <= 400:
            contexts[str(context.get("id", ""))] = (start, end)
    return contexts


def fact_value(fact: Any) -> Decimal:
    raw = fact.get_text(" ", strip=True).replace(",", "").replace("−", "-")
    negative = raw.startswith("(") and raw.endswith(")")
    if negative:
        raw = raw[1:-1]
    try:
        value = Decimal(raw) * (Decimal(10) ** int(fact.get("scale") or "0"))
    except (InvalidOperation, TypeError, ValueError):
        raise ValueError(f"Could not parse inline XBRL fact value {raw!r}.")
    if negative or fact.get("sign") == "-":
        value = -abs(value)
    return value


def extract_annual_value(soup: BeautifulSoup, tags: list[str], report_date: str) -> tuple[str, Decimal]:
    contexts = inline_duration_contexts(soup, report_date)
    facts = soup.find_all(lambda tag: local_name(tag) == "nonfraction")
    for requested_tag in tags:
        values = []
        for fact in facts:
            name = str(fact.get("name", "")).rsplit(":", 1)[-1]
            context_id = str(fact.get("contextref", ""))
            unit = str(fact.get("unitref", "")).casefold()
            if name != requested_tag or context_id not in contexts or not unit.endswith("usd"):
                continue
            try:
                values.append(fact_value(fact))
            except ValueError:
                continue
        if values:
            frequencies = Counter(values)
            value, count = frequencies.most_common(1)[0]
            if count != len(values) and len(frequencies) > 1:
                raise ValueError(f"Ambiguous inline XBRL values for {requested_tag} at {report_date}.")
            return requested_tag, value
    raise ValueError(f"No annual {', '.join(tags)} fact was found for {report_date}.")


def latest_10k(ticker: str, cik: str) -> dict[str, str]:
    recent = company_submissions(cik).get("filings", {}).get("recent", {})
    for index, form in enumerate(recent.get("form", [])):
        if form == "10-K":
            return {
                "accession": recent["accessionNumber"][index],
                "document": recent["primaryDocument"][index],
                "report_date": recent["reportDate"][index],
            }
    raise ValueError(f"No recent 10-K found for {ticker}.")


def fetch_filing_html(cik: str, filing: dict[str, str]) -> tuple[str, BeautifulSoup]:
    url = f"{ARCHIVES_BASE}/{int(cik)}/{filing['accession'].replace('-', '')}/{filing['document']}"
    with httpx.stream("GET", url, headers=HEADERS, timeout=SEC_TIMEOUT) as response:
        response.raise_for_status()
        body = bytearray()
        for chunk in response.iter_bytes():
            body.extend(chunk)
            if len(body) > 15 * 1024 * 1024:
                raise ValueError("The filing exceeds the 15 MB validation limit.")
    return url, BeautifulSoup(bytes(body), "html.parser")


def filing_ground_truth(ticker: str, company: dict[str, Any]) -> dict[str, Any]:
    filing = latest_10k(ticker, company["cik"])
    url, soup = fetch_filing_html(company["cik"], filing)
    try:
        revenue_tag, revenue = extract_annual_value(soup, TAG_CANDIDATES["revenue"], filing["report_date"])
        income_tag, income = extract_annual_value(soup, TAG_CANDIDATES["net_income"], filing["report_date"])
    except ValueError as error:
        raise ValueError(f"{ticker}: {error}") from error
    return {
        "ticker": ticker,
        "company": company["name"],
        "cik": company["cik"],
        "accession": filing["accession"],
        "report_date": filing["report_date"],
        "filing_url": url,
        "revenue_tag": revenue_tag,
        "revenue": format(revenue, "f"),
        "net_income_tag": income_tag,
        "net_income": format(income, "f"),
    }


def compare_to_formscope(expected: dict[str, Any]) -> dict[str, Any]:
    current = company_report(expected["ticker"])
    period = next((item for item in current["periods"] if item["as_of"] == expected["report_date"]), None)
    revenue = Decimal(str(period["revenue"])) if period else None
    net_income = Decimal(str(period["net_income"])) if period and period.get("net_income") is not None else None
    expected_revenue = Decimal(expected["revenue"])
    expected_income = Decimal(expected["net_income"])
    return {
        "ticker": expected["ticker"],
        "company": expected["company"],
        "report_date": expected["report_date"],
        "accession": expected["accession"],
        "revenue_expected": expected["revenue"],
        "revenue_actual": format(revenue, "f") if revenue is not None else None,
        "revenue_match": revenue == expected_revenue,
        "net_income_expected": expected["net_income"],
        "net_income_actual": format(net_income, "f") if net_income is not None else None,
        "net_income_match": net_income == expected_income,
        "filing_url": expected["filing_url"],
    }


def run(refresh: bool, add_missing: bool) -> dict[str, Any]:
    if not SEC_USER_AGENT:
        raise RuntimeError("Set SEC_USER_AGENT to an identifying name and contact email before running the SEC check.")
    listed = company_tickers()
    if refresh or add_missing:
        expected = json.loads(FIXTURE_PATH.read_text(encoding="utf-8")) if add_missing and FIXTURE_PATH.exists() else []
        known_tickers = {item["ticker"] for item in expected}
        FIXTURE_PATH.parent.mkdir(parents=True, exist_ok=True)
        for ticker in TICKERS:
            if ticker in known_tickers:
                continue
            if ticker not in listed:
                raise ValueError(f"Ticker {ticker} was not found in the SEC company list.")
            expected.append(filing_ground_truth(ticker, listed[ticker]))
            FIXTURE_PATH.write_text(json.dumps(expected, indent=2) + "\n", encoding="utf-8")
            known_tickers.add(ticker)
            time.sleep(0.12)
    else:
        expected = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    rows = []
    for item in expected:
        rows.append(compare_to_formscope(item))
        time.sleep(0.12)
    revenue_matches = sum(row["revenue_match"] for row in rows)
    income_matches = sum(row["net_income_match"] for row in rows)
    return {
        "companies": len(rows),
        "revenue_fact_checks": len(rows),
        "revenue_matches": revenue_matches,
        "revenue_match_rate": revenue_matches / len(rows) if rows else 0.0,
        "net_income_fact_checks": len(rows),
        "net_income_matches": income_matches,
        "net_income_match_rate": income_matches / len(rows) if rows else 0.0,
        "total_fact_checks": 2 * len(rows),
        "total_matches": revenue_matches + income_matches,
        "total_match_rate": (revenue_matches + income_matches) / (2 * len(rows)) if rows else 0.0,
        "ground_truth": "Revenue and net income were read from the latest 10-K inline XBRL filing values; FormScope output was read from SEC Company Facts.",
        "details": rows,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--refresh-fixture", action="store_true")
    parser.add_argument("--add-missing-fixture", action="store_true")
    parser.add_argument("--output", type=Path, default=REPORT_PATH)
    arguments = parser.parse_args()
    report = run(arguments.refresh_fixture, arguments.add_missing_fixture)
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    arguments.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: value for key, value in report.items() if key != "details"}, indent=2))
    print(f"Wrote {arguments.output}")


if __name__ == "__main__":
    main()
