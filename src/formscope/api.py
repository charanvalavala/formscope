from __future__ import annotations

from contextlib import asynccontextmanager
import logging
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from formscope.config import MAX_QUERY_CHARS, validate_settings
from formscope.limits import enforce_limit
from formscope.service import answer_from_filings, company_report

STATIC_DIR = Path(__file__).resolve().parents[2] / "static"
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI):
    validate_settings()
    yield


app = FastAPI(title="FormScope", version="1.0.0", description="Source-linked SEC filings analysis and financial fact exploration.", lifespan=lifespan)


@app.get("/")
def home():
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/health")
def health():
    return {"status": "ok", "data_source": "SEC EDGAR"}


@app.get("/api/company")
def get_company(request: Request, ticker: str = Query(min_length=1, max_length=10)):
    enforce_limit(request, "company", 12)
    try:
        return company_report(ticker)
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except Exception as error:
        logger.exception("SEC company request failed")
        raise HTTPException(status_code=502, detail="The SEC data request failed. Try again shortly.") from error


@app.get("/api/filing-search")
def filing_search(request: Request, ticker: str = Query(min_length=1, max_length=10), question: str = Query(min_length=3, max_length=MAX_QUERY_CHARS)):
    enforce_limit(request, "filing-search", 12)
    try:
        return answer_from_filings(ticker, question)
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except Exception as error:
        logger.exception("SEC filing request failed")
        raise HTTPException(status_code=502, detail="The SEC filing request failed. Try again shortly.") from error


app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
