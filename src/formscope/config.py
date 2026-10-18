from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")
SEC_USER_AGENT = os.getenv("SEC_USER_AGENT", "").strip()
SEC_TIMEOUT = float(os.getenv("SEC_TIMEOUT", "20"))
SEC_BASE = "https://data.sec.gov"
ARCHIVES_BASE = "https://www.sec.gov/Archives/edgar/data"
MAX_QUERY_CHARS = 500


def validate_settings():
    if not SEC_USER_AGENT or "your name" in SEC_USER_AGENT.casefold() or "example.com" in SEC_USER_AGENT.casefold():
        raise RuntimeError("Set SEC_USER_AGENT in .env or the process environment to an identifying name and contact email.")
