# FormScope

Reported financials, comparable annual periods, and semantic SEC filing search.

[Instant saved walkthrough](https://charanvalavala.github.io/demos/formscope/) · [Live app](https://charan-formscope.onrender.com)

## Product and AI

Enter a ticker, optionally compare another company, and inspect historical revenue, growth, net income and margin. The trend chart and table use the same reported values. Each metric exposes its reporting period, source concept, filing date and accession when available; original filings stay one click away.

Search now uses a real pinned MiniLM embedding model through quantized ONNX CPU inference, combined with the lexical baseline using reciprocal-rank fusion. This is semantic retrieval, not an LLM-generated financial explanation or a forecasting model. The response reports `hybrid-minilm-onnx` or an explicit `lexical` fallback warning when embeddings fail. The frontend never silently labels fallback as AI search.

Facts are keyed by full start/end dates and unit. Ratios require matching periods; latest-filed restatements win, with concept priority breaking ties. Charts label period-end dates rather than assuming calendar year equals fiscal year. Annual duration checks and fallback tags do not solve all accounting comparability problems. Historical concept changes, unusual contexts, non-USD issuers and fiscal transitions still need human review.

## Measured results

Thirty manually authored questions were evaluated across twenty cropped filing excerpts from ten issuers:

| Retriever | Hit@1 | MRR |
| --- | ---: | ---: |
| Lexical baseline | 27/30 | 0.939 |
| Quantized MiniLM semantic | 28/30 | 0.967 |
| Hybrid | 30/30 | 1.000 |

Hybrid p50 was 7.9 ms and p95 10.2 ms on this CPU run after the model was available. Cold startup/download is excluded from those percentiles, and the report retains all per-query times. The set was selected from competition-related lexical results, creating selection bias. Each issuer contributes only two excerpts. These results do not establish full-10-K retrieval quality, unseen-company generalization or financial reasoning. The benchmark reports all methods, queries, source URLs and failures in `reports/search-evaluation.json`.

```bash
PYTHONPATH=src python scripts/evaluate_search.py
```

The earlier pinned financial snapshot matched revenue and net income for twenty issuer filings (40/40 checks). `data/financial-ground-truth-20.json` contains accessions and expected facts; `reports/financial-ground-truth-results.json` preserves that run. Offline tests verify the recorded comparisons and extraction edge cases. This upgrade did not refresh that SEC-wide comparison: direct SEC requests from the development host returned 403. Do not interpret the old snapshot as a fresh validation of all issuers under the updated period logic.

```bash
export SEC_USER_AGENT="FormScope/1.0 Your Name your-real-contact@example.org"
PYTHONPATH=src python scripts/validate_financials.py
```

In PowerShell use `$env:SEC_USER_AGENT="FormScope/1.0 Your Name your-real-contact@example.org"`. Replace the example with a real contact. The service validates configuration at startup; never commit `.env`.

## Deployment and limits

The Docker build downloads the pinned ~23 MB quantized model into the image, avoiding model downloads in the first search. No PyTorch runtime is required by this project. Local first use downloads the model. Inference runs in bounded batches; the embedding cache holds at most four filing passage collections, and facts/submission caches each hold at most four entries.

```bash
docker build -t formscope .
docker run --rm -p 8000:8000 -e SEC_USER_AGENT="FormScope/1.0 Your Name your-real-contact@example.org" formscope
```

SEC rate/access policies and changing company concepts can cause failures. Filing downloads cap at 15 MB; request limits are per process. The saved walkthrough uses a clearly dated Apple snapshot and saved semantic passage result. It works without SEC or a live API; arbitrary comparisons and new queries require the live service. It does not offer investment recommendations.

Architecture: ticker resolution -> company facts/submissions -> annual-period selection -> exact-period ratios -> UI; filing HTML -> bounded passages -> quantized embeddings + lexical candidates -> RRF -> original-filing links. Tests cover period mismatches, restatements, semantic ranking, lexical fallback disclosure and API assets.

Sources: [SEC APIs](https://www.sec.gov/edgar/sec-api-documentation), [MiniLM model](https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2). Model revision and source excerpt URLs are pinned in code/data.

## Reproduce

Python 3.12 is recommended. From the repository root:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt -r requirements-dev.txt
PYTHONPATH=src uvicorn formscope.api:app --reload
```

PowerShell:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt -r requirements-dev.txt
$env:PYTHONPATH = "src"
uvicorn formscope.api:app --reload
```

Open http://127.0.0.1:8000. Run regressions with `PYTHONPATH=src python -m pytest -q` (PowerShell: set `PYTHONPATH` as above, then `python -m pytest -q`). GitHub Actions runs this suite, builds the Docker image and checks container health/frontend assets on pushes and pull requests.

The frontend is plain JavaScript modules. `ui.js` owns requests, cancellation, timeouts, feedback and escaping; `app.js` owns application state and rendering. Requests use per-operation abort controllers. Static saved outputs are in `static/sample.json`; they never masquerade as fresh model responses.
