from fastapi.testclient import TestClient
from formscope import api, service, semantic


def test_failed_semantic_model_discloses_lexical_fallback(monkeypatch):
    monkeypatch.setattr(api, "validate_settings", lambda: None)
    monkeypatch.setattr(
        service, "company_tickers", lambda: {"EXM": {"cik": "1", "name": "Example"}}
    )
    monkeypatch.setattr(
        service,
        "company_submissions",
        lambda cik: {
            "filings": {
                "recent": {
                    "form": ["10-K"],
                    "accessionNumber": ["abc"],
                    "primaryDocument": ["filing.htm"],
                }
            }
        },
    )
    monkeypatch.setattr(
        service,
        "filing_text",
        lambda *args: (
            "https://www.sec.gov/example",
            "Supply chain disruptions increase component costs.",
        ),
    )

    def fail(*args):
        raise RuntimeError("model unavailable")

    monkeypatch.setattr(semantic, "rank_hybrid", fail)
    with TestClient(api.app) as client:
        result = client.get(
            "/api/filing-search",
            params={"ticker": "EXM", "question": "supply chain costs"},
        )
        assert result.status_code == 200
        assert result.json()["mode"] == "lexical"
        assert result.json()["warning"]
        assert result.json()["citations"][0]["url"] == "https://www.sec.gov/example"
        assert client.get("/app.js").status_code == 200
