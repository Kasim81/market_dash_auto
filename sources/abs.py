"""
sources/abs.py
==============
Australian Bureau of Statistics (ABS) Data API source module
(data.api.abs.gov.au).

SDMX 2.1 over REST. The API serves SDMX-CSV (and SDMX-ML), but NOT
SDMX-JSON (verified live 2026-05-28 — the JSON Accept header returns HTTP
406, ``text/csv`` returns the CSV flavour). We use CSV — same shape as the
ECB Data Portal, so parsing is identical (TIME_PERIOD + OBS_VALUE columns).

    https://data.api.abs.gov.au/rest/data/<flow>/<key>
        ?lastNObservations=<n>   # latest n observations (snapshot fast path)

Per G20 catalogue: no registration, no API key.

Series ID convention: ``<flow>/<key>`` where the key is the dot-separated
SDMX dimension tuple, e.g. ``CPI/1.10001.10.50.Q`` (CPI all-groups index,
weighted avg of 8 capital cities, quarterly) or
``LF/M13.3.1599.20.AUS.M`` (unemployment rate, persons 15+, SA, monthly).

CSV shape:
    DATAFLOW,MEASURE,...dims...,TIME_PERIOD,OBS_VALUE,UNIT_MEASURE,...
We only read TIME_PERIOD + OBS_VALUE.
"""

from __future__ import annotations

import io
import pathlib
import time
from datetime import date, datetime

import pandas as pd
import requests


_LIBRARY_CSV = pathlib.Path(__file__).parent.parent / "data" / "macro_library_abs.csv"
ABS_BASE = "https://data.api.abs.gov.au/rest/data"
DEFAULT_HIST_START = "1948-01-01"

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; market_dash_auto/1.0)",
    "Accept": "text/csv",
}


# ---------------------------------------------------------------------------
# LIBRARY LOADER
# ---------------------------------------------------------------------------

def load_library() -> list[dict]:
    """Load ABS indicator definitions from macro_library_abs.csv."""
    if not _LIBRARY_CSV.exists():
        return []
    df = pd.read_csv(_LIBRARY_CSV, dtype=str, keep_default_na=False)
    df["sort_key"] = pd.to_numeric(df["sort_key"], errors="coerce").fillna(0)
    df = df.sort_values("sort_key")
    result = []
    for _, row in df.iterrows():
        result.append({
            "source":       "ABS",
            "source_id":    row["series_id"].strip(),
            "col":          row["col"].strip(),
            "name":         row["name"].strip(),
            "country":      row.get("country", "").strip() or "AUS",
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
    last_n: int | None = None,
    timeout: int = 60,
    retries: int = 3,
) -> str | None:
    """Fetch a single ABS series as raw SDMX-CSV text, or None.

    series_id: '<flow>/<key>' format.
    last_n:    if set, append ?lastNObservations=<n> (snapshot fast path).
    """
    if "/" not in series_id:
        print(f"    [ABS] invalid series_id {series_id!r} (expected '<FLOW>/<KEY>')")
        return None
    url = f"{ABS_BASE}/{series_id}"
    params = {}
    if last_n is not None and last_n > 0:
        params["lastNObservations"] = last_n

    for attempt in range(retries):
        try:
            resp = requests.get(url, params=params, headers=_HEADERS, timeout=timeout)
            if resp.status_code == 200 and resp.text.strip():
                return resp.text
            if 500 <= resp.status_code < 600:
                wait = 2 ** attempt
                print(f"    [ABS HTTP {resp.status_code}] {series_id} — backing off {wait}s")
                time.sleep(wait)
                continue
            print(f"    [ABS HTTP {resp.status_code}] {series_id} — skipping")
            return None
        except requests.Timeout:
            wait = 2 ** attempt
            print(f"    [ABS timeout] {series_id} — backing off {wait}s")
            time.sleep(wait)
        except requests.RequestException as e:
            print(f"    [ABS request error] {series_id}: {e} — skipping")
            return None

    print(f"    [ABS FAIL] {series_id} — {retries} attempts exhausted")
    return None


# ---------------------------------------------------------------------------
# CSV PARSING
# ---------------------------------------------------------------------------

def parse_csv(text: str, series_id: str) -> list[tuple[date, float]]:
    """Parse ABS SDMX-CSV → list of (date, value) tuples (missing values dropped)."""
    obs: list[tuple[date, float]] = []
    if not text or not text.strip():
        return obs
    try:
        df = pd.read_csv(io.StringIO(text))
    except Exception as e:
        print(f"    [ABS] CSV parse failed for {series_id}: {e}")
        return obs

    if "TIME_PERIOD" not in df.columns or "OBS_VALUE" not in df.columns:
        print(f"    [ABS] unexpected CSV schema for {series_id}: {list(df.columns)[:8]}")
        return obs

    for _, row in df.iterrows():
        d_str = str(row["TIME_PERIOD"]).strip()
        v_raw = row["OBS_VALUE"]
        if pd.isna(v_raw) or not d_str or d_str.lower() in ("nan", ""):
            continue
        d = _parse_period(d_str)
        if d is None:
            continue
        try:
            v = float(v_raw)
        except (ValueError, TypeError):
            continue
        obs.append((d, v))
    return obs


def _parse_period(p: str) -> date | None:
    """Parse ABS period strings to a calendar date.

    Cadences: monthly YYYY-MM, quarterly YYYY-Qn, annual YYYY, daily YYYY-MM-DD.
    """
    p = p.strip()
    if not p:
        return None
    try:
        return datetime.strptime(p, "%Y-%m-%d").date()
    except ValueError:
        pass
    if "-Q" in p:
        try:
            yr, q = p.split("-Q")
            return date(int(yr), int(q) * 3, 1)
        except (ValueError, IndexError):
            pass
    try:
        return datetime.strptime(p + "-01", "%Y-%m-%d").date()
    except ValueError:
        pass
    if len(p) == 4 and p.isdigit():
        return date(int(p), 12, 31)
    return None


def fetch_series_as_pandas(
    series_id: str,
    col_name: str | None = None,
    last_n: int | None = None,
) -> pd.Series | None:
    """Fetch one series and return a date-indexed pd.Series, or None on failure."""
    text = fetch_series(series_id, last_n=last_n)
    if text is None:
        return None
    obs = parse_csv(text, series_id)
    if not obs:
        return None
    s = pd.Series(
        {pd.Timestamp(d): v for d, v in obs},
        name=col_name or series_id,
    )
    s = s.sort_index()
    return s
