"""
sources/dbnomics.py
===================
DB.nomics (api.db.nomics.world) source module.  Provides library loading,
single-series fetcher, observation parsing, and period-string date handling.

Indicator definitions live in data/macro_library_dbnomics.csv.
"""

from __future__ import annotations

import pathlib
import time
from datetime import datetime, timedelta

import pandas as pd
import requests

_LIBRARY_CSV = pathlib.Path(__file__).parent.parent / "data" / "macro_library_dbnomics.csv"

DBNOMICS_BASE = "https://api.db.nomics.world/v22"


# ---------------------------------------------------------------------------
# LIBRARY LOADER
# ---------------------------------------------------------------------------

def load_library() -> list[dict]:
    """Load DB.nomics indicator definitions from macro_library_dbnomics.csv."""
    df = pd.read_csv(_LIBRARY_CSV, dtype=str, keep_default_na=False)
    df["sort_key"] = pd.to_numeric(df["sort_key"], errors="coerce").fillna(0)
    df = df.sort_values("sort_key")
    result = []
    for _, row in df.iterrows():
        result.append({
            "series_id":   row["series_id"].strip(),
            "col":         row["col"].strip(),
            "name":        row["name"].strip(),
            "category":    row["category"].strip(),
            "subcategory": row["subcategory"].strip(),
            "units":       row["units"].strip(),
            "frequency":   row["frequency"].strip(),
            "country":     row["country"].strip(),
            "notes":       row["notes"].strip(),
        })
    return result


# ---------------------------------------------------------------------------
# SERIES FETCH
# ---------------------------------------------------------------------------

def fetch_series(
    series_id: str,
    retries: int = 4,
    backoff_base: int = 2,
    timeout: int = 30,
) -> dict | None:
    """
    Fetch a single series document (including observations) from DB.nomics.
    series_id format: "PROVIDER/DATASET/SERIES_CODE".  Returns the first
    docs[] entry or None on failure.
    """
    url = f"{DBNOMICS_BASE}/series"
    params = {"observations": "1", "series_ids": series_id, "limit": 1}

    for attempt in range(retries):
        try:
            resp = requests.get(url, params=params, timeout=timeout)

            if resp.status_code == 200:
                data = resp.json()
                docs = data.get("series", {}).get("docs", [])
                return docs[0] if docs else None

            if resp.status_code == 429 or resp.status_code >= 500:
                wait = backoff_base ** (attempt + 1)
                print(
                    f"    [DB.nomics HTTP {resp.status_code}] {series_id} — "
                    f"backing off {wait}s (attempt {attempt + 1}/{retries})"
                )
                time.sleep(wait)
                continue

            print(f"    [DB.nomics HTTP {resp.status_code}] {series_id} — skipping")
            return None

        except requests.exceptions.Timeout:
            wait = backoff_base ** (attempt + 1)
            print(f"    [DB.nomics timeout] {series_id} — backing off {wait}s")
            time.sleep(wait)

        except requests.exceptions.RequestException as e:
            print(f"    [DB.nomics request error] {series_id}: {e} — skipping")
            return None

    print(f"    [DB.nomics FAIL] {series_id} — {retries} attempts exhausted")
    return None


# ---------------------------------------------------------------------------
# OBSERVATION PARSING
# ---------------------------------------------------------------------------

def parse_observations(doc: dict) -> list[tuple[str, float]]:
    """
    Extract (period_str, value) pairs from a DB.nomics series document.
    Filters nulls / "NA" values; returns ascending by period.
    """
    periods = doc.get("period", [])
    values  = doc.get("value", [])
    pairs: list[tuple[str, float]] = []
    for p, v in zip(periods, values):
        if v is None or str(v).lower() in ("na", "nan", ""):
            continue
        try:
            pairs.append((str(p), float(v)))
        except (ValueError, TypeError):
            continue
    pairs.sort(key=lambda x: x[0])
    return pairs


def parse_period_to_date(period: str) -> datetime | None:
    """
    Convert a DB.nomics period string to a datetime at end-of-period.
    Handles YYYY-MM-DD, YYYY-MM, YYYY-QN, and YYYY formats.
    """
    p = str(period).strip()

    # YYYY-MM-DD
    if len(p) == 10 and p[4] == "-" and p[7] == "-":
        return datetime.strptime(p, "%Y-%m-%d")

    # YYYY-QN (quarterly) — check before YYYY-MM since both are length 7
    if len(p) == 7 and p[4] == "-" and p[5] == "Q":
        year = int(p[:4])
        q = int(p[6])
        month = q * 3
        if month == 12:
            return datetime(year, 12, 31)
        return datetime(year, month + 1, 1) - timedelta(days=1)

    # YYYY-MM
    if len(p) == 7 and p[4] == "-":
        dt = datetime.strptime(p + "-01", "%Y-%m-%d")
        if dt.month == 12:
            return dt.replace(day=31)
        return dt.replace(month=dt.month + 1, day=1) - timedelta(days=1)

    # YYYY (annual)
    if len(p) == 4 and p.isdigit():
        return datetime(int(p), 12, 31)

    return None


def obs_to_series(obs: list[tuple[str, float]], col_name: str) -> pd.Series:
    """
    Convert observation pairs to a DatetimeIndex pd.Series (end-of-period dates).
    """
    dates, vals = [], []
    for period, val in obs:
        try:
            dt = parse_period_to_date(period)
            if dt:
                dates.append(dt)
                vals.append(val)
        except (ValueError, TypeError):
            continue

    if not dates:
        return pd.Series(dtype=float)
    return pd.Series(vals, index=pd.DatetimeIndex(dates), name=col_name)
