from formscope.financials import annual_observations, summarize_facts


def observation(value, filed, start="2023-10-01", end="2024-09-30", form="10-K", fp="FY"):
    return {"val": value, "start": start, "end": end, "filed": filed, "form": form, "fp": fp}


def test_annual_observations_selects_latest_filed_annual_value():
    facts = {
        "facts": {
            "us-gaap": {
                "RevenueFromContractWithCustomerExcludingAssessedTax": {
                    "units": {
                        "USD": [
                            observation(100, "2024-11-01"),
                            observation(110, "2025-02-01"),
                            observation(20, "2025-02-01", "2024-07-01", "2024-09-30"),
                            observation(30, "2025-02-01", "2023-10-01", "2024-09-30", form="10-Q"),
                        ]
                    }
                }
            }
        }
    }

    result = annual_observations(facts, ["RevenueFromContractWithCustomerExcludingAssessedTax"])

    assert result == [{"year": 2024, "value": 110, "start": "2023-10-01", "end": "2024-09-30", "filed": "2025-02-01", "unit": "USD"}]


def test_annual_observations_uses_fallback_concept_and_unit():
    facts = {
        "facts": {
            "us-gaap": {
                "Revenues": {"units": {"USD": [observation(200, "2025-01-01")]}}
            }
        }
    }

    result = annual_observations(facts, ["MissingRevenueTag", "Revenues"])

    assert result[0]["value"] == 200
    assert result[0]["unit"] == "USD"


def test_summary_calculates_growth_and_net_margin_from_annual_facts():
    facts = {
        "cik": 123456,
        "facts": {
            "us-gaap": {
                "Revenues": {
                    "units": {
                        "USD": [
                            observation(100, "2024-11-01", "2022-10-01", "2023-09-30"),
                            observation(125, "2025-11-01", "2023-10-01", "2024-09-30"),
                        ]
                    }
                },
                "NetIncomeLoss": {
                    "units": {
                        "USD": [observation(20, "2024-11-01", "2022-10-01", "2023-09-30"), observation(25, "2025-11-01")]
                    }
                },
            }
        },
    }

    result = summarize_facts(facts, "Example Corp", "EXM")

    assert result["periods"][1]["revenue_growth"] == 0.25
    assert result["periods"][0]["net_margin"] == 0.2
    assert result["periods"][1]["net_margin"] == 0.2
    assert result["source"].endswith("CIK0000123456.json")
