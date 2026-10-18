# FormScope

FormScope is an evidence-linked SEC filings explorer. It resolves a ticker through SEC company submissions, reads XBRL company facts, computes annual revenue growth and net margins, links every filing, and ranks passages from the latest 10-K against a user's question.

## Capabilities

- Live SEC company facts and filing metadata, without a commercial market-data key.
- Annual 10-K XBRL series for revenue, net income, operating income, operating cash flow, capital expenditures, and diluted EPS when reported.
- Derived year-over-year revenue change and net margin with formulas visible in the UI.
- Search over the latest 10-K text with source-linked passages and an explicit ranked-evidence response, not unsupported generated financial advice.
- Responsive dashboard, Docker packaging, and direct links to original EDGAR filings.

## Run locally

The SEC asks API clients to identify themselves. Copy `.env.example` to `.env` and replace the placeholder with an identifying name and contact email. The app loads this local `.env` file and exits on startup if the placeholder is unchanged. Never commit `.env`.

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
$env:PYTHONPATH = "src"
uvicorn formscope.api:app --reload
```

Open `http://127.0.0.1:8000` and try AAPL, MSFT, NVDA, or GOOGL. The application caches company lists for one day and facts, submissions, and filings for one hour; it caps each filing download at 15 MB. In-process request limits are keyed by client address and reset on restart; they are a demo safeguard, not shared multi-worker or proxy-aware abuse protection. For deployment, configure `SEC_USER_AGENT` as an environment variable or secret and respect SEC fair-access guidance.

On macOS or Linux, use:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
export SEC_USER_AGENT="FormScope/1.0 Your Name contact@example.org"
export PYTHONPATH=src
uvicorn formscope.api:app --reload
```

Build and run the container with a real SEC contact identity:

```powershell
docker build -t formscope .
docker run --rm -p 8000:8000 -e SEC_USER_AGENT="FormScope/1.0 Your Name real-email@example.com" formscope
```

Replace the Docker command's example identity with your own identifying name and contact email. Do not leave the placeholders unchanged.

## Endpoints

- `GET /health`
- `GET /api/company?ticker=AAPL`
- `GET /api/filing-search?ticker=AAPL&question=supply%20chain`

## Sources and interpretation

The application uses public SEC EDGAR endpoints: the [SEC API documentation](https://www.sec.gov/edgar/sec-api-documentation), [company facts](https://data.sec.gov/api/xbrl/companyfacts/CIK0000320193.json), [submissions](https://data.sec.gov/submissions/CIK0000320193.json), and the linked primary filing documents. The values are historical reported facts. XBRL concepts can vary between issuers and years, and this tool does not make investment recommendations, price predictions, or accounting judgments.

## Financial fact validation

The checked-in ground-truth fixture records the revenue and net income values read from each issuer's latest 10-K inline XBRL, including its accession and filing URL. FormScope's SEC Company Facts output matched both values for all 20 issuers in the snapshot: 20/20 revenue values and 20/20 net income values (40/40 fact checks). This validates extraction and fiscal-period matching for these filings; it does not establish that every issuer uses comparable accounting concepts.

Reproduce the live comparison with your identifying SEC User-Agent:

```powershell
$env:SEC_USER_AGENT = "FormScope/1.0 Your Name contact@example.org"
$env:PYTHONPATH = "src"
python scripts/validate_financials.py
```

```bash
export SEC_USER_AGENT="FormScope/1.0 Your Name contact@example.org"
PYTHONPATH=src python scripts/validate_financials.py
```

To refresh the pinned filing snapshot and report, run `python scripts/validate_financials.py --refresh-fixture`. The report is written to `reports/financial-ground-truth-results.json`. Tests use the checked-in values and do not make network requests.

Run the tests with:

```powershell
$env:PYTHONPATH = "src"
python -m pip install -r requirements-dev.txt
python -m pytest -q
```

```bash
python -m pip install -r requirements-dev.txt
PYTHONPATH=src python -m pytest -q
```

## Known limits

- The XBRL mapping uses common US-GAAP tags; unusual issuer-specific tags may be absent.
- Metric comparability across firms requires accounting context beyond a single tag lookup.
- Filing passage ranking is lexical and should be treated as a navigation aid, not legal or financial interpretation.
- The app does not store user data or trade securities.

The repository includes a Render Blueprint at `render.yaml`. Set `SEC_USER_AGENT` as a secret when creating the service; the deployment does not contain a placeholder identity.
