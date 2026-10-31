import argparse
from datetime import UTC, datetime
from decimal import Decimal
import json
from pathlib import Path
import time
import urllib.parse
import urllib.request


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="https://charan-formscope.onrender.com")
    parser.add_argument(
        "--output", type=Path, default=Path("reports/deployed-facts-check.json")
    )
    args = parser.parse_args()
    fixtures = json.loads(Path("data/financial-ground-truth-20.json").read_text())
    rows = []
    for fixture in fixtures:
        ticker = fixture["ticker"]
        row = {
            "ticker": ticker,
            "report_date": fixture["report_date"],
            "accession": fixture["accession"],
            "filing_url": fixture["filing_url"],
        }
        try:
            with urllib.request.urlopen(
                args.base_url.rstrip("/")
                + "/api/company?ticker="
                + urllib.parse.quote(ticker),
                timeout=40,
            ) as response:
                report = json.load(response)
            period = next(
                (
                    period
                    for period in report["periods"]
                    if period["as_of"] == fixture["report_date"]
                ),
                None,
            )
            for key in ("revenue", "net_income"):
                actual = period.get(key) if period else None
                row[key + "_expected"] = fixture[key]
                row[key + "_actual"] = actual
                row[key + "_match"] = actual is not None and Decimal(
                    str(actual)
                ) == Decimal(fixture[key])
            row["provenance"] = period.get("provenance") if period else None
            if ticker == "AAPL":
                Path(".cache").mkdir(exist_ok=True)
                Path(".cache/latest-aapl.json").write_text(
                    json.dumps(report, indent=2), encoding="utf8"
                )
        except Exception as error:
            row["error"] = str(error)
        rows.append(row)
        print(
            ticker,
            (
                "error"
                if row.get("error")
                else (row["revenue_match"], row["net_income_match"])
            ),
            flush=True,
        )
        if len(rows) >= 3 and all(row.get("error") for row in rows[-3:]):
            break
        time.sleep(6)
    checks = [
        row.get(key + "_match", False)
        for row in rows
        for key in ("revenue", "net_income")
    ]
    output = {
        "captured_at": datetime.now(UTC).isoformat(),
        "base_url": args.base_url,
        "companies_attempted": len(rows),
        "expected_companies": len(fixtures),
        "checks_attempted": len(checks),
        "matches": sum(checks),
        "errors": sum("error" in row for row in rows),
        "scope": "Updated deployed API compared against the previously pinned 20-filing revenue/net-income ground truth. Source filings were not fetched again. Errors count as non-matches; new restatements may legitimately differ from the pinned figures.",
        "details": rows,
    }
    args.output.parent.mkdir(exist_ok=True, parents=True)
    args.output.write_text(json.dumps(output, indent=2), encoding="utf8")
    print(
        json.dumps(
            {key: value for key, value in output.items() if key != "details"}, indent=2
        )
    )

    if len(rows) != len(fixtures) or not all(checks):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
