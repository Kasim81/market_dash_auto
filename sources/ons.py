"""
sources/ons.py
==============
UK Office for National Statistics (ONS) source module
(api.beta.ons.gov.uk).

The legacy ``api.ons.gov.uk/timeseries`` endpoint was decommissioned
(retired 2024-11-25). The current free, no-key path is the Zebedee reader
``/data`` endpoint, which returns the JSON behind any ONS website page:

    https://api.beta.ons.gov.uk/v1/data?uri=<taxonomy-path>/timeseries/<cdid>/<dataset>

Per G20 catalogue: no registration, no API key, JSON.

Series ID convention: the website URI of the timeseries (leading slash
optional), e.g. ``economy/inflationandpriceindices/timeseries/d7g7/mm23``
(CPI annual rate) or
``employmentandlabourmarket/peoplenotinwork/unemployment/timeseries/mgsx/lms``.

Response shape (json):
    {"description": {"title": ..., "cdid": ..., "unit": ...},
     "months":   [{"date": "2026 APR", "value": "2.8", "month": "April", "year": "2026"}, ...],
     "quarters": [{"date": "2026 Q1", "value": "3.1", "quarter": "Q1", "year": "2026"}, ...],
     "years":    [{"date": "2026", "value": ..., "year": "2026"}, ...]}
A series is published at a single native frequency; the finer arrays carry
the observations and the coarser arrays carry aggregates. We pick the
finest non-empty array (months > quarters > years).
"""

from __future__ import annotations

import pathlib
import time
from datetime import date, datetime

import pandas as pd
import requests


_LIBRARY_CSV = pathlib.Path(__file__).parent.parent / "data" / "macro_library_ons.csv"
ONS_DATA = "https://api.beta.ons.gov.uk/v1/data"

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; market_dash_auto/1.0)",
    "Accept": "application/json",
}

_MONTHS = {
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
    "july": 7, "august": 8, "september": 9, "october": 10, "november": 11,
    "december": 12,
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "jun": 6, "jul": 7, "aug": 8,
    "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}


# ---------------------------------------------------------------------------
# LIBRARY LOADER
# ---------------------------------------------------------------------------

def load_library() -> list[dict]:
    """Load ONS indicator definitions from macro_library_ons.csv."""
    if not _LIBRARY_CSV.exists():
        return []
    df = pd.read_csv(_LIBRARY_CSV, dtype=str, keep_default_na=False)
    df["sort_key"] = pd.to_numeric(df["sort_key"], errors="coerce").fillna(0)
    df = df.sort_values("sort_key")
    result = []
    for _, row in df.iterrows():
        result.append({
            "source":       "ONS",
            "source_id":    row["series_id"].strip(),
            "col":          row["col"].strip(),
            "name":         row["name"].strip(),
            "country":      row.get("country", "").strip() or "GBR",
            "category":     row["category"].strip(),
            "subcategory":  row["subcategory"].strip(),
            "concept":      row.get("concept", "").strip(),
            "cycle_timing": row.get("cycle_timing", "").strip(),
            "units":        row["units"].strip(),
            "frequency":    row["frequency"].strip(),
            "notes":        row.get("notes", "").strip(),
            "sort_key":     float(row["sort_key"]),
            "series_id":    row["series_id"].strip(),
        })
    return result


# ---------------------------------------------------------------------------
# SERIES FETCH
# ---------------------------------------------------------------------------

def fetch_series(
    series_id: str,
    timeout: int = 30,
    retries: int = 3,
) -> dict | None:
    """Fetch a single ONS timeseries; returns the parsed JSON response or None."""
    uri = series_id.strip()
    if not uri.startswith("/"):
        uri = "/" + uri

    for attempt in range(retries):
        try:
            resp = requests.get(ONS_DATA, params={"uri": uri}, headers=_HEADERS, timeout=timeout)
            if resp.status_code == 200 and resp.text:
                return resp.json()
            if 500 <= resp.status_code < 600:
                wait = 2 ** attempt
                print(f"    [ONS HTTP {resp.status_code}] {uri} — backing off {wait}s")
                time.sleep(wait)
                continue
            print(f"    [ONS HTTP {resp.status_code}] {uri} — skipping")
            return None
        except requests.Timeout:
            wait = 2 ** attempt
            print(f"    [ONS timeout] {uri} — backing off {wait}s")
            time.sleep(wait)
        except requests.RequestException as e:
            print(f"    [ONS request error] {uri}: {e} — skipping")
            return None

    print(f"    [ONS FAIL] {uri} — {retries} attempts exhausted")
    return None


# ---------------------------------------------------------------------------
# JSON PARSING
# ---------------------------------------------------------------------------

def _entry_date(entry: dict, kind: str) -> date | None:
    """Map an ONS observation entry → calendar date.

    kind in {"months","quarters","years"}. Period-end conventions match the
    other sources (quarter → last month of quarter, day 1; year → year-end).
    """
    year_raw = str(entry.get("year", "")).strip()
    try:
        year = int(year_raw)
    except ValueError:
        return None

    if kind == "months":
        mname = str(entry.get("month", "")).strip().lower()
        m = _MONTHS.get(mname)
        if m is None:
            # fall back to parsing the "date" field, e.g. "2026 APR"
            parts = str(entry.get("date", "")).split()
            if len(parts) == 2:
                m = _MONTHS.get(parts[1].lower())
        if m is None:
            return None
        return date(year, m, 1)

    if kind == "quarters":
        q = str(entry.get("quarter", "")).strip().upper().lstrip("Q")
        try:
            qn = int(q)
        except ValueError:
            return None
        if qn not in (1, 2, 3, 4):
            return None
        return date(year, qn * 3, 1)

    # annual
    return date(year, 12, 31)


def parse_response(doc: dict, series_id: str) -> list[tuple[date, float]]:
    """Parse an ONS /data response → list of (date, value) tuples.

    Picks the finest non-empty array (months > quarters > years)."""
    obs: list[tuple[date, float]] = []
    if not doc:
        return obs

    chosen = None
    for kind in ("months", "quarters", "years"):
        arr = doc.get(kind)
        if isinstance(arr, list) and arr:
            chosen = kind
            break
    if chosen is None:
        print(f"    [ONS] no observation array for {series_id}")
        return obs

    for entry in doc[chosen]:
        v_str = str(entry.get("value", "")).strip()
        if not v_str or v_str.lower() in ("nan", "n/a", "", "..", "-"):
            continue
        d = _entry_date(entry, chosen)
        if d is None:
            continue
        try:
            v = float(v_str)
        except ValueError:
            continue
        obs.append((d, v))
    return obs


def fetch_series_as_pandas(
    series_id: str,
    col_name: str | None = None,
) -> pd.Series | None:
    """Fetch one series and return a date-indexed pd.Series, or None on failure."""
    doc = fetch_series(series_id)
    if doc is None:
        return None
    obs = parse_response(doc, series_id)
    if not obs:
        return None
    s = pd.Series(
        {pd.Timestamp(d): v for d, v in obs},
        name=col_name or series_id,
    )
    s = s.sort_index()
    return s
