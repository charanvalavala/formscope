from __future__ import annotations

from typing import Any

from formscope.config import MAX_QUERY_CHARS
from formscope.financials import summarize_facts
from formscope.retrieval import rank_passages, split_passages
from formscope.sec_client import company_facts, company_submissions, company_tickers, filing_text


def company_report(ticker: str) -> dict[str, Any]:
    normalized = ticker.strip().upper()
    companies = company_tickers()
    if normalized not in companies:
        raise ValueError(f"Ticker {normalized!r} was not found in the SEC company list.")
    company = companies[normalized]
    facts = company_facts(company["cik"])
    report = summarize_facts(facts, company["name"], normalized)
    recent = company_submissions(company["cik"]).get("filings", {}).get("recent", {})
    filings = []
    count = len(recent.get("form", []))
    for index in range(count):
        if recent["form"][index] != "10-K":
            continue
        filings.append({
            "filed": recent["filingDate"][index],
            "period": recent["reportDate"][index],
            "accession": recent["accessionNumber"][index],
            "url": f"https://www.sec.gov/Archives/edgar/data/{int(company['cik'])}/{recent['accessionNumber'][index].replace('-', '')}/{recent['primaryDocument'][index]}",
        })
        if len(filings) == 5:
            break
    report["filings"] = filings
    return report


def answer_from_filings(ticker: str, question: str) -> dict[str, Any]:
    normalized = ticker.strip().upper()
    if len(question) > MAX_QUERY_CHARS:
        raise ValueError(f"Question must be at most {MAX_QUERY_CHARS} characters.")
    company = company_tickers().get(normalized)
    if not company:
        raise ValueError(f"Ticker {normalized!r} was not found in the SEC company list.")
    recent = company_submissions(company["cik"]).get("filings", {}).get("recent", {})
    filing_index = next((index for index, form in enumerate(recent.get("form", [])) if form == "10-K"), None)
    if filing_index is None:
        raise ValueError("No recent 10-K filing was found for this ticker.")
    accession = recent["accessionNumber"][filing_index]
    document = recent["primaryDocument"][filing_index]
    url, text = filing_text(company["cik"], accession, document)
    ranked = rank_passages(question, split_passages(text), 5)
    if not ranked:
        return {"company": company["name"], "ticker": normalized, "answer": "No matching passages were found in the latest 10-K. Try a specific phrase or risk topic.", "citations": [], "mode": "evidence-search"}
    return {
        "company": company["name"],
        "ticker": normalized,
        "answer": "The passages below are the closest matches from the latest filed 10-K. Review the linked filing before drawing conclusions.",
        "citations": [{**item, "url": url, "filing": accession} for item in ranked],
        "mode": "evidence-search",
    }
