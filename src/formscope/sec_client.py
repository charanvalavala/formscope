from __future__ import annotations

from functools import lru_cache
from time import time
from typing import Any

import httpx
from bs4 import BeautifulSoup

from formscope.config import ARCHIVES_BASE, SEC_BASE, SEC_TIMEOUT, SEC_USER_AGENT

HEADERS = {"User-Agent": SEC_USER_AGENT, "Accept-Encoding": "gzip, deflate"}


@lru_cache(maxsize=4)
def _company_tickers(_: int) -> dict[str, dict[str, Any]]:
    response = httpx.get("https://www.sec.gov/files/company_tickers.json", headers=HEADERS, timeout=SEC_TIMEOUT)
    response.raise_for_status()
    records = response.json().values()
    return {str(item["ticker"]).upper(): {"cik": f"{int(item['cik_str']):010d}", "name": item["title"]} for item in records}


def company_tickers() -> dict[str, dict[str, Any]]:
    return _company_tickers(int(time() // 86400))


@lru_cache(maxsize=256)
def _company_facts(cik: str, _: int) -> dict[str, Any]:
    response = httpx.get(f"{SEC_BASE}/api/xbrl/companyfacts/CIK{cik}.json", headers=HEADERS, timeout=SEC_TIMEOUT)
    response.raise_for_status()
    return response.json()


def company_facts(cik: str) -> dict[str, Any]:
    return _company_facts(cik, int(time() // 3600))


@lru_cache(maxsize=256)
def _company_submissions(cik: str, _: int) -> dict[str, Any]:
    headers = {**HEADERS, "Host": "data.sec.gov"}
    response = httpx.get(f"{SEC_BASE}/submissions/CIK{cik}.json", headers=headers, timeout=SEC_TIMEOUT)
    response.raise_for_status()
    return response.json()


def company_submissions(cik: str) -> dict[str, Any]:
    return _company_submissions(cik, int(time() // 3600))


def filing_url(cik: str, accession: str, primary_document: str) -> str:
    return f"{ARCHIVES_BASE}/{int(cik)}/{accession.replace('-', '')}/{primary_document}"


@lru_cache(maxsize=8)
def _filing_text(cik: str, accession: str, primary_document: str, _: int) -> tuple[str, str]:
    url = filing_url(cik, accession, primary_document)
    headers = {"User-Agent": SEC_USER_AGENT, "Accept-Encoding": "gzip, deflate"}
    body = bytearray()
    with httpx.stream("GET", url, headers=headers, timeout=SEC_TIMEOUT) as response:
        response.raise_for_status()
        if int(response.headers.get("content-length", "0") or 0) > 15 * 1024 * 1024:
            raise RuntimeError("The filing exceeds the 15 MB processing limit.")
        for chunk in response.iter_bytes():
            body.extend(chunk)
            if len(body) > 15 * 1024 * 1024:
                raise RuntimeError("The filing exceeds the 15 MB processing limit.")
    soup = BeautifulSoup(bytes(body), "html.parser")
    for node in soup(["script", "style", "ix:header"]):
        node.decompose()
    text = " ".join(soup.stripped_strings)
    return url, text


def filing_text(cik: str, accession: str, primary_document: str) -> tuple[str, str]:
    return _filing_text(cik, accession, primary_document, int(time() // 3600))
