from formscope.financials import summarize_facts, annual_observations


def obs(start, end, value, filed="2025-02-01"):
    return {
        "start": start,
        "end": end,
        "val": value,
        "filed": filed,
        "form": "10-K",
        "fp": "FY",
    }


def test_mismatched_periods_do_not_produce_margin():
    facts = {
        "cik": 1,
        "facts": {
            "us-gaap": {
                "Revenues": {"units": {"USD": [obs("2023-01-01", "2023-12-31", 100)]}},
                "NetIncomeLoss": {
                    "units": {"USD": [obs("2022-10-01", "2023-09-30", 20)]}
                },
            }
        },
    }
    row = summarize_facts(facts, "Example", "EXM")["periods"][0]
    assert "net_margin" not in row
    assert "net_income" not in row
    assert row["provenance"]["revenue"]["start"] == "2023-01-01"


def test_newer_restatement_wins_across_fallback_concepts():
    facts = {
        "facts": {
            "us-gaap": {
                "Revenues": {
                    "units": {
                        "USD": [obs("2023-01-01", "2023-12-31", 100, "2024-02-01")]
                    }
                },
                "SalesRevenueNet": {
                    "units": {
                        "USD": [obs("2023-01-01", "2023-12-31", 105, "2025-02-01")]
                    }
                },
            }
        }
    }
    result = annual_observations(facts, ["Revenues", "SalesRevenueNet"])
    assert result[0]["value"] == 105


def test_distinct_periods_in_same_year_are_retained():
    facts = {
        "facts": {
            "us-gaap": {
                "Revenues": {
                    "units": {
                        "USD": [
                            obs("2022-10-01", "2023-09-30", 100),
                            obs("2023-01-01", "2023-12-31", 120),
                        ]
                    }
                }
            }
        }
    }
    assert len(annual_observations(facts, ["Revenues"])) == 2
