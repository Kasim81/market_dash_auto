"""
sources/bls.py
==============
US Bureau of Labor Statistics (BLS) Public Data API source module
(api.bls.gov).

The BLS API is a "single-key" source: a free registration key unlocks the
v2 endpoint (500 queries/day, 50 series/query, 20-year span). Without a key
the v2 shared pool is quickly exhausted, but the **v1 GET endpoint** still
serves data keyless (returns the latest ~3-year window per series). This
module therefore:

  * reads ``BLS_API_KEY`` from the environment;
  * when set  → POSTs to v2 with the key (full history, chunked into
    <=19-year spans);
  * when unset → GETs the keyless v1 endpoint (recent window only).

    v2: POST https://api.bls.gov/publicAPI/v2/timeseries/data/
        body {"seriesid": [...], "startyear": "YYYY", "endyear": "YYYY",
              "registrationkey": "<key>"}
    v1: GET  https://api.bls.gov/publicAPI/v1/timeseries/data/<seriesid>

Per G20 catalogue: free registration (key optional for low-volume use).

Series ID convention: the BLS series ID, e.g. ``CUUR0000SA0`` (CPI-U all
items NSA), ``LNS14000000`` (unemployment rate SA), ``CES0000000001``
(total nonfarm employment SA).

Response shape (json):
    {"status": "REQUEST_SUCCEEDED",
     "Results": {"series": [{"seriesID": ...,
        "data": [{"year": "2026", "period": "M04", "periodName": "April",
                  "value": "333.020"}, ...]}]}}
Periods: M01-M12 monthly, M13 annual avg; Q01-Q04 quarterly, Q05 annual;
A01 annual; S01/S02 semiannual, S03 annual. Aggregate markers (M13/Q05/S03)
are skipped so they don't mix with the native cadence.
"""

from __future__ import annotations

import json
import os
import pathlib
import time
from datetime import date, datetime

import pandas as pd
import requests


_LIBRARY_CSV = pathlib.Path(__file__).parent.parent / "data" / "macro_library_bls.csv"
BLS_V2 = "https://api.bls.gov/publicAPI/v2/timeseries/data/"
BLS_V1 = "https://api.bls.gov/publicAPI/v1/timeseries/data/"
DEFAULT_HIST_START_YEAR = 1947
# Unregistered span cap is 10y; registered is 20y. Use 19 to stay safely
# under the registered cap (the keyless path doesn't range-query anyway).
_MAX_SPAN_YEARS = 19

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; market_dash_auto/1.0)",
    "Content-Type": "application/json",
    "Accept": "application/json",
}


# ---------------------------------------------------------------------------
# LIBRARY LOADER
# ---------------------------------------------------------------------------

def load_library() -> list[dict]:
    """Load BLS indicator definitions from macro_library_bls.csv."""
    if not _LIBRARY_CSV.exists():
        return []
    df = pd.read_csv(_LIBRARY_CSV, dtype=str, keep_default_na=False)
    df["sort_key"] = pd.to_numeric(df["sort_key"], errors="coerce").fillna(0)
    df = df.sort_values("sort_key")
    result = []
    for _, row in df.iterrows():
        result.append({
            "source":       "BLS",
            "source_id":    row["series_id"].strip(),
            "col":          row["col"].strip(),
            "name":         row["name"].strip(),
            "country":      row.get("country", "").strip() or "USA",
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
# RAW FETCH
# ---------------------------------------------------------------------------

def _post_v2(series_id: str, start_year: int, end_year: int, key: str,
             timeout: int, retries: int) -> list[dict] | None:
    """One v2 POST for a single series + year range; returns the data list."""
    body = {
        "seriesid": [series_id],
        "startyear": str(start_year),
        "endyear": str(end_year),
        "registrationkey": key,
    }
    for attempt in range(retries):
        try:
            resp = requests.post(BLS_V2, data=json.dumps(body), headers=_HEADERS, timeout=timeout)
            doc = resp.json() if resp.status_code == 200 else {}
            status = doc.get("status")
            if status == "REQUEST_SUCCEEDED":
                series = doc.get("Results", {}).get("series", [])
                return series[0].get("data", []) if series else []
            if status == "REQUEST_NOT_PROCESSED":
                wait = 2 ** attempt
                print(f"    [BLS v2] throttled for {series_id} — backing off {wait}s "
                      f"({doc.get('message')})")
                time.sleep(wait)
                continue
            print(f"    [BLS v2 HTTP {resp.status_code}] {series_id} — {doc.get('message')}")
            return None
        except requests.Timeout:
            time.sleep(2 ** attempt)
        except requests.RequestException as e:
            print(f"    [BLS v2 request error] {series_id}: {e}")
            return None
    return None


def _get_v1(series_id: str, timeout: int, retries: int) -> list[dict] | None:
    """Keyless v1 GET for a single series (latest ~3-year window)."""
    url = f"{BLS_V1}{series_id}"
    for attempt in range(retries):
        try:
            resp = requests.get(url, headers={"User-Agent": _HEADERS["User-Agent"]}, timeout=timeout)
            doc = resp.json() if resp.status_code == 200 else {}
            status = doc.get("status")
            if status == "REQUEST_SUCCEEDED":
                series = doc.get("Results", {}).get("series", [])
                return series[0].get("data", []) if series else []
            if status == "REQUEST_NOT_PROCESSED":
                wait = 2 ** attempt
                print(f"    [BLS v1] throttled for {series_id} — backing off {wait}s")
                time.sleep(wait)
                continue
            print(f"    [BLS v1 HTTP {resp.status_code}] {series_id} — {doc.get('message')}")
            return None
        except requests.Timeout:
            time.sleep(2 ** attempt)
        except requests.RequestException as e:
            print(f"    [BLS v1 request error] {series_id}: {e}")
            return None
    return None


def fetch_series(
    series_id: str,
    recent: bool = False,
    timeout: int = 30,
    retries: int = 4,
) -> list[dict] | None:
    """Fetch a single BLS series; returns the raw 'data' list of dicts or None.

    With BLS_API_KEY set, uses v2 (full history, or just the last two years
    when recent=True). Without a key, uses the keyless v1 GET window.
    """
    key = os.environ.get("BLS_API_KEY", "").strip()
    if not key:
        # Keyless: v1 GET only (no year-range support — returns recent window).
        return _get_v1(series_id, timeout, retries)

    now_year = date.today().year
    if recent:
        return _post_v2(series_id, now_year - 1, now_year, key, timeout, retries)

    # Full history: walk back in <=19-year spans, newest chunk first, merge.
    merged: list[dict] = []
    end = now_year
    while end >= DEFAULT_HIST_START_YEAR:
        start = max(DEFAULT_HIST_START_YEAR, end - _MAX_SPAN_YEARS + 1)
        chunk = _post_v2(series_id, start, end, key, timeout, retries)
        if chunk is None:
            break
        if not chunk:
            # Empty chunk: no data this far back — stop walking.
            if merged:
                break
        merged.extend(chunk)
        end = start - 1
        time.sleep(0.3)
    return merged or None


# ---------------------------------------------------------------------------
# PARSING
# ---------------------------------------------------------------------------

def _period_to_date(year: int, period: str) -> date | None:
    """Map a BLS (year, period) pair to a calendar date.

    Aggregate markers (M13 annual avg, Q05 annual, S03 annual) return None so
    they don't mix with the series' native cadence.
    """
    p = (period or "").strip().upper()
    if not p:
        return None
    if p.startswith("M"):
        try:
            m = int(p[1:])
        except ValueError:
            return None
        if 1 <= m <= 12:
            return date(year, m, 1)
        return None  # M13 annual average
    if p.startswith("Q"):
        try:
            q = int(p[1:])
        except ValueError:
            return None
        if 1 <= q <= 4:
            return date(year, q * 3, 1)
        return None  # Q05 annual
    if p.startswith("S"):
        if p == "S01":
            return date(year, 6, 1)
        if p == "S02":
            return date(year, 12, 1)
        return None  # S03 annual
    if p == "A01":
        return date(year, 12, 31)
    return None


def parse_data(data: list[dict], series_id: str) -> list[tuple[date, float]]:
    """Parse a BLS 'data' list → list of (date, value) tuples."""
    obs: list[tuple[date, float]] = []
    if not data:
        return obs
    for d in data:
        try:
            year = int(str(d.get("year", "")).strip())
        except ValueError:
            continue
        dt = _period_to_date(year, str(d.get("period", "")))
        if dt is None:
            continue
        v_str = str(d.get("value", "")).strip()
        if not v_str or v_str.lower() in ("nan", "n/a", "-", ""):
            continue
        try:
            v = float(v_str)
        except ValueError:
            continue
        obs.append((dt, v))
    # BLS returns newest-first and may repeat periods across chunks; dedupe.
    merged: dict[date, float] = {}
    for dt, v in obs:
        merged.setdefault(dt, v)
    return sorted(merged.items())


def fetch_series_as_pandas(
    series_id: str,
    col_name: str | None = None,
    recent: bool = False,
) -> pd.Series | None:
    """Fetch one series and return a date-indexed pd.Series, or None on failure."""
    data = fetch_series(series_id, recent=recent)
    if data is None:
        return None
    obs = parse_data(data, series_id)
    if not obs:
        return None
    s = pd.Series(
        {pd.Timestamp(d): v for d, v in obs},
        name=col_name or series_id,
    )
    s = s.sort_index()
    return s
