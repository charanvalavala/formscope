from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Any


TAG_CANDIDATES = {
    "revenue": ["RevenueFromContractWithCustomerExcludingAssessedTax", "Revenues", "SalesRevenueNet"],
    "net_income": ["NetIncomeLoss"],
    "operating_income": ["OperatingIncomeLoss"],
    "operating_cash_flow": ["NetCashProvidedByUsedInOperatingActivities"],
    "capital_expenditures": ["PaymentsToAcquirePropertyPlantAndEquipment"],
    "diluted_eps": ["EarningsPerShareDiluted"],
}


def annual_observations(facts: dict[str, Any], candidates: list[str]) -> list[dict[str, Any]]:
    taxonomy = facts.get("facts", {}).get("us-gaap", {})
    by_year: dict[int, dict[str, Any]] = {}
    for priority, tag in enumerate(candidates):
        record = taxonomy.get(tag)
        if not record:
            continue
        units = record.get("units", {})
        unit = next((name for name in ("USD", "USD/shares") if name in units), None)
        if not unit:
            continue
        for observation in units[unit]:
            start = observation.get("start")
            end = observation.get("end")
            if observation.get("form") != "10-K" or observation.get("fp") != "FY" or not start or not end:
                continue
            try:
                duration_days = (date.fromisoformat(end) - date.fromisoformat(start)).days
                year = int(end[:4])
            except (TypeError, ValueError):
                continue
            if not 330 <= duration_days <= 400:
                continue
            filed = str(observation.get("filed", ""))
            current = by_year.get(year)
            if current is None or priority < current["tag_priority"] or (priority == current["tag_priority"] and filed > current["filed"]):
                by_year[year] = {"year": year, "value": observation["val"], "start": start, "end": end, "filed": filed, "unit": unit, "tag_priority": priority}
    result = sorted(by_year.values(), key=lambda item: item["year"])[-6:]
    return [{key: value for key, value in item.items() if key != "tag_priority"} for item in result]


def summarize_facts(facts: dict[str, Any], company_name: str, ticker: str) -> dict[str, Any]:
    fact_sets = {name: annual_observations(facts, tags) for name, tags in TAG_CANDIDATES.items()}
    revenue = {item["year"]: item for item in fact_sets["revenue"]}
    net_income = {item["year"]: item for item in fact_sets["net_income"]}
    operating_income = {item["year"]: item for item in fact_sets["operating_income"]}
    rows = []
    for year in sorted(revenue):
        row: dict[str, Any] = {"year": year, "revenue": revenue[year]["value"], "unit": revenue[year]["unit"], "as_of": revenue[year]["end"]}
        if year in net_income:
            row["net_income"] = net_income[year]["value"]
            if row["revenue"]:
                row["net_margin"] = row["net_income"] / row["revenue"]
        if year in operating_income:
            row["operating_income"] = operating_income[year]["value"]
        previous = revenue.get(year - 1)
        if previous and previous["value"]:
            row["revenue_growth"] = row["revenue"] / previous["value"] - 1
        rows.append(row)
    return {
        "ticker": ticker,
        "company": company_name,
        "cik": facts.get("cik"),
        "periods": rows,
        "additional_metrics": {key: value for key, value in fact_sets.items() if key not in {"revenue", "net_income", "operating_income"}},
        "source": f"https://data.sec.gov/api/xbrl/companyfacts/CIK{int(facts.get('cik', 0)):010d}.json",
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "notes": ["Annual 10-K XBRL facts only.", "Metric availability varies by issuer and fiscal year.", "This tool summarizes filed facts; it does not recommend securities or forecast returns."],
    }
