"""
sources/boc.py
==============
Bank of Canada Valet API source module (www.bankofcanada.ca/valet).

Valet is the BoC's free, no-key JSON/CSV/XML API for every series the Bank
publishes — policy rate, benchmark Government of Canada bond yields, the
Bank's CPI inflation measures, and daily FX reference rates.

    https://www.bankofcanada.ca/valet/observations/<seriesNames>/json
        ?recent=<n>            # latest n observations
        &start_date=YYYY-MM-DD  # full history from a start date

Per G20 catalogue: no registration, no API key. Verified live 2026-05-28
against a plain ``Mozilla/5.0`` UA (no 403 quirk, unlike BoE IADB).

Series IDs are Valet series names, e.g. ``V39079`` (Target for the overnight
rate), ``FXUSDCAD`` (USD/CAD), ``BD.CDN.10YR.DQ.YLD`` (GoC 10y benchmark).

Indicator definitions live in ``data/macro_library_boc.csv``.

Response shape (json):
    {"observations": [{"d": "2026-05-27", "V39079": {"v": "2.25"}}, ...]}
The series-name key inside each observation object equals the requested
series name; the numeric value is the nested ``"v"`` string.
"""

from __future__ import annotations

import pathlib
import time
from datetime import date, datetime

import pandas as pd
import requests


_LIBRARY_CSV = pathlib.Path(__file__).parent.parent / "data" / "macro_library_boc.csv"
BOC_BASE = "https://www.bankofcanada.ca/valet/observations"
DEFAULT_HIST_START = "1975-01-01"

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; market_dash_auto/1.0)",
    "Accept": "application/json",
}


# ---------------------------------------------------------------------------
# LIBRARY LOADER
# ---------------------------------------------------------------------------

def load_library() -> list[dict]:
    """Load Bank of Canada Valet indicator definitions from macro_library_boc.csv."""
    if not _LIBRARY_CSV.exists():
        return []
    df = pd.read_csv(_LIBRARY_CSV, dtype=str, keep_default_na=False)
    df["sort_key"] = pd.to_numeric(df["sort_key"], errors="coerce").fillna(0)
    df = df.sort_values("sort_key")
    result = []
    for _, row in df.iterrows():
        result.append({
            "source":       "BoC",
            "source_id":    row["series_id"].strip(),
            "col":          row["col"].strip(),
            "name":         row["name"].strip(),
            "country":      row.get("country", "").strip() or "CAN",
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
    start: str = DEFAULT_HIST_START,
    recent: int | None = None,
    timeout: int = 30,
    retries: int = 3,
) -> dict | None:
    """Fetch a single Valet series; returns the parsed JSON response or None.

    recent: if set, fetch only the latest ``recent`` observations
            (&recent=n) — fast path for snapshot calls. Otherwise fetch the
            full history from ``start`` (&start_date=).
    """
    url = f"{BOC_BASE}/{series_id}/json"
    if recent is not None and recent > 0:
        params = {"recent": recent}
    else:
        params = {"start_date": start}

    for attempt in range(retries):
        try:
            resp = requests.get(url, params=params, headers=_HEADERS, timeout=timeout)
            if resp.status_code == 200 and resp.text:
                return resp.json()
            if 500 <= resp.status_code < 600:
                wait = 2 ** attempt
                print(f"    [BoC HTTP {resp.status_code}] {series_id} — backing off {wait}s")
                time.sleep(wait)
                continue
            print(f"    [BoC HTTP {resp.status_code}] {series_id} — skipping")
            return None
        except requests.Timeout:
            wait = 2 ** attempt
            print(f"    [BoC timeout] {series_id} — backing off {wait}s")
            time.sleep(wait)
        except requests.RequestException as e:
            print(f"    [BoC request error] {series_id}: {e} — skipping")
            return None

    print(f"    [BoC FAIL] {series_id} — {retries} attempts exhausted")
    return None


# ---------------------------------------------------------------------------
# JSON PARSING
# ---------------------------------------------------------------------------

def parse_response(doc: dict, series_id: str) -> list[tuple[date, float]]:
    """Parse Valet JSON → list of (date, value) tuples (missing values dropped)."""
    obs: list[tuple[date, float]] = []
    if not doc:
        return obs
    observations = doc.get("observations")
    if not isinstance(observations, list):
        print(f"    [BoC] unexpected JSON schema for {series_id}: keys={list(doc.keys())[:6]}")
        return obs

    for o in observations:
        d_str = str(o.get("d", "")).strip()
        cell = o.get(series_id)
        if not d_str or not isinstance(cell, dict):
            continue
        v_str = str(cell.get("v", "")).strip()
        if not v_str or v_str.lower() in ("nan", "n/a", ""):
            continue
        try:
            d = datetime.strptime(d_str, "%Y-%m-%d").date()
        except ValueError:
            continue
        try:
            v = float(v_str)
        except ValueError:
            continue
        obs.append((d, v))
    return obs


def fetch_series_as_pandas(
    series_id: str,
    start: str = DEFAULT_HIST_START,
    col_name: str | None = None,
    recent: int | None = None,
) -> pd.Series | None:
    """Fetch one series and return a date-indexed pd.Series, or None on failure.

    recent: forward a small value (e.g. 2) for snapshot calls to keep the
            response tiny; omit for full history.
    """
    doc = fetch_series(series_id, start=start, recent=recent)
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
