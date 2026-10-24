from decimal import Decimal
import json
from datetime import date, timedelta
from pathlib import Path

from bs4 import BeautifulSoup

from scripts.validate_financials import extract_annual_value
from formscope.financials import summarize_facts


def test_inline_xbrl_parser_filters_to_annual_consolidated_context_and_applies_scale():
    html = """
    <ix:header>
      <xbrli:context id="annual"><xbrli:period><xbrli:startDate>2024-01-01</xbrli:startDate><xbrli:endDate>2024-12-31</xbrli:endDate></xbrli:period></xbrli:context>
      <xbrli:context id="quarter"><xbrli:period><xbrli:startDate>2024-10-01</xbrli:startDate><xbrli:endDate>2024-12-31</xbrli:endDate></xbrli:period></xbrli:context>
      <xbrli:context id="segment"><xbrli:period><xbrli:startDate>2024-01-01</xbrli:startDate><xbrli:endDate>2024-12-31</xbrli:endDate></xbrli:period><xbrli:segment><xbrldi:explicitMember dimension="x">x:y</xbrldi:explicitMember></xbrli:segment></xbrli:context>
    </ix:header>
    <ix:nonfraction name="us-gaap:Revenues" contextref="annual" unitref="usd" scale="6">125</ix:nonfraction>
    <ix:nonfraction name="us-gaap:Revenues" contextref="quarter" unitref="usd" scale="6">30</ix:nonfraction>
    <ix:nonfraction name="us-gaap:Revenues" contextref="segment" unitref="usd" scale="6">80</ix:nonfraction>
    """

    tag, value = extract_annual_value(BeautifulSoup(html, "html.parser"), ["Revenues"], "2024-12-31")

    assert tag == "Revenues"
    assert value == Decimal("125000000")


def test_inline_xbrl_parser_applies_negative_sign():
    html = """
    <xbrli:context id="annual"><xbrli:period><xbrli:startDate>2024-01-01</xbrli:startDate><xbrli:endDate>2024-12-31</xbrli:endDate></xbrli:period></xbrli:context>
    <ix:nonfraction name="us-gaap:NetIncomeLoss" contextref="annual" unitref="usd" scale="3" sign="-">12</ix:nonfraction>
    """

    tag, value = extract_annual_value(BeautifulSoup(html, "html.parser"), ["NetIncomeLoss"], "2024-12-31")

    assert tag == "NetIncomeLoss"
    assert value == Decimal("-12000")


def test_formscope_matches_checked_in_values_from_twenty_filed_10ks():
    root = Path(__file__).resolve().parents[1]
    fixture = json.loads((root / "data" / "financial-ground-truth-20.json").read_text(encoding="utf-8"))
    report = json.loads((root / "reports" / "financial-ground-truth-results.json").read_text(encoding="utf-8"))
    report_rows = {item["ticker"]: item for item in report["details"]}

    assert len(fixture) == 20
    assert len(report_rows) == len(fixture)
    assert report["companies"] == len(fixture)
    assert report["total_matches"] == report["total_fact_checks"] == 40
    for item in fixture:
        report_row = report_rows[item["ticker"]]
        assert report_row["revenue_expected"] == report_row["revenue_actual"] == item["revenue"]
        assert report_row["net_income_expected"] == report_row["net_income_actual"] == item["net_income"]
        assert report_row["revenue_match"] is True
        assert report_row["net_income_match"] is True
        end = date.fromisoformat(item["report_date"])
        start = (end - timedelta(days=365)).isoformat()
        observation = {"start": start, "end": item["report_date"], "filed": item["report_date"], "form": "10-K", "fp": "FY"}
        facts = {
            "cik": int(item["cik"]),
            "facts": {
                "us-gaap": {
                    item["revenue_tag"]: {"units": {"USD": [{**observation, "val": int(Decimal(item["revenue"]))}]}},
                    item["net_income_tag"]: {"units": {"USD": [{**observation, "val": int(Decimal(item["net_income"]))}]}},
                }
            },
        }
        result = summarize_facts(facts, item["company"], item["ticker"])
        period = next(row for row in result["periods"] if row["as_of"] == item["report_date"])

        assert period["revenue"] == int(Decimal(item["revenue"]))
        assert period["net_income"] == int(Decimal(item["net_income"]))
