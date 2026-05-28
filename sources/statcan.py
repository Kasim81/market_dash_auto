"""
sources/statcan.py
==================
Statistics Canada Web Data Service (WDS) source module
(www150.statcan.gc.ca/t1/wds/rest).

WDS is StatCan's free, no-key REST API. Series are addressed by numeric
*vector* IDs (e.g. ``v41690973`` = Total CPI, all-items, Canada). We use
the POST endpoint that returns the latest N periods for a set of vectors:

    POST /t1/wds/rest/getDataFromVectorsAndLatestNPeriods
        body: [{"vectorId": 41690973, "latestN": 2}, ...]

Per G20 catalogue: no registration, no API key, JSON. Covers CPI, the
Labour Force Survey (employment / unemployment), monthly real GDP, etc.

Indicator definitions live in ``data/macro_library_statcan.csv``.

Series ID convention: the vector number, with or without a leading ``v``
(e.g. ``41690973`` or ``v41690973``).

Response shape (json):
    [{"status": "SUCCESS",
      "object": {"vectorId": 41690973, "productId": 18100004,
                 "vectorDataPoint": [{"refPer": "2026-04-01",
                                      "value": 168.0, ...}, ...]}}]
"""

from __future__ import annotations

import pathlib
import time
from datetime import date, datetime

import pandas as pd
import requests


_LIBRARY_CSV = pathlib.Path(__file__).parent.parent / "data" / "macro_library_statcan.csv"
WDS_LATEST_N = ("https://www150.statcan.gc.ca/t1/wds/rest/"
                "getDataFromVectorsAndLatestNPeriods")
DEFAULT_HIST_START = "1970-01-01"
# Upper bound on periods pulled for a "full history" request. 4000 periods
# comfortably covers >300 years of monthly data or ~11 years of daily —
# StatCan WDS series of interest here are monthly/quarterly.
HIST_LATEST_N = 4000

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; market_dash_auto/1.0)",
    "Content-Type": "application/json",
    "Accept": "application/json",
}


# ---------------------------------------------------------------------------
# LIBRARY LOADER
# ---------------------------------------------------------------------------

def load_library() -> list[dict]:
    """Load StatCan WDS indicator definitions from macro_library_statcan.csv."""
    if not _LIBRARY_CSV.exists():
        return []
    df = pd.read_csv(_LIBRARY_CSV, dtype=str, keep_default_na=False)
    df["sort_key"] = pd.to_numeric(df["sort_key"], errors="coerce").fillna(0)
    df = df.sort_values("sort_key")
    result = []
    for _, row in df.iterrows():
        result.append({
            "source":       "StatCan",
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

def _vector_int(series_id: str) -> int | None:
    """'v41690973' or '41690973' -> 41690973; None if not parseable."""
    s = series_id.strip().lower().lstrip("v")
    try:
        return int(s)
    except ValueError:
        return None


def fetch_series(
    series_id: str,
    latest_n: int = HIST_LATEST_N,
    timeout: int = 60,
    retries: int = 3,
) -> dict | None:
    """Fetch a single StatCan vector; returns the parsed JSON 'object' or None."""
    vid = _vector_int(series_id)
    if vid is None:
        print(f"    [StatCan] invalid vector id {series_id!r}")
        return None

    body = [{"vectorId": vid, "latestN": latest_n}]
    for attempt in range(retries):
        try:
            resp = requests.post(WDS_LATEST_N, json=body, headers=_HEADERS, timeout=timeout)
            if resp.status_code == 200 and resp.text:
                doc = resp.json()
                if not isinstance(doc, list) or not doc:
                    print(f"    [StatCan] unexpected response for v{vid}")
                    return None
                item = doc[0]
                if item.get("status") != "SUCCESS":
                    print(f"    [StatCan] status={item.get('status')} for v{vid}")
                    return None
                return item.get("object")
            if 500 <= resp.status_code < 600:
                wait = 2 ** attempt
                print(f"    [StatCan HTTP {resp.status_code}] v{vid} — backing off {wait}s")
                time.sleep(wait)
                continue
            print(f"    [StatCan HTTP {resp.status_code}] v{vid} — skipping")
            return None
        except requests.Timeout:
            wait = 2 ** attempt
            print(f"    [StatCan timeout] v{vid} — backing off {wait}s")
            time.sleep(wait)
        except requests.RequestException as e:
            print(f"    [StatCan request error] v{vid}: {e} — skipping")
            return None

    print(f"    [StatCan FAIL] v{vid} — {retries} attempts exhausted")
    return None


# ---------------------------------------------------------------------------
# JSON PARSING
# ---------------------------------------------------------------------------

def parse_object(obj: dict, series_id: str) -> list[tuple[date, float]]:
    """Parse a WDS vector 'object' → list of (date, value) tuples."""
    obs: list[tuple[date, float]] = []
    if not obj:
        return obs
    points = obj.get("vectorDataPoint")
    if not isinstance(points, list):
        print(f"    [StatCan] no vectorDataPoint for {series_id}")
        return obs

    for p in points:
        d_str = str(p.get("refPer", "")).strip()
        v_raw = p.get("value")
        if not d_str or v_raw is None:
            continue
        d = None
        for fmt in ("%Y-%m-%d", "%Y-%m", "%Y"):
            try:
                d = datetime.strptime(d_str, fmt).date()
                break
            except ValueError:
                continue
        if d is None:
            continue
        try:
            v = float(v_raw)
        except (ValueError, TypeError):
            continue
        obs.append((d, v))
    return obs


def fetch_series_as_pandas(
    series_id: str,
    latest_n: int = HIST_LATEST_N,
    col_name: str | None = None,
) -> pd.Series | None:
    """Fetch one vector and return a date-indexed pd.Series, or None on failure.

    latest_n: pass a small value (e.g. 2) for snapshot calls.
    """
    obj = fetch_series(series_id, latest_n=latest_n)
    if obj is None:
        return None
    obs = parse_object(obj, series_id)
    if not obs:
        return None
    s = pd.Series(
        {pd.Timestamp(d): v for d, v in obs},
        name=col_name or series_id,
    )
    s = s.sort_index()
    return s
