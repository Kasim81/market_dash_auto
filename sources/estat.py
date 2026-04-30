"""
sources/estat.py
================
e-Stat (Statistics Bureau of Japan) source module — api.e-stat.go.jp.

e-Stat aggregates Japan government statistics across ministries (METI,
MIC, MoF, etc.) and exposes them via a JSON REST API. Free registration
required for an App ID (read from env var ``ESTAT_APP_ID``).

Per G20 catalogue: registration only, JSON/XML/CSV, covers JP CPI, GDP,
Labour Force Survey, retail/wholesale price surveys, household
income/expenditure, etc. Crucially for §3.1, e-Stat is the canonical
free path for METI's Indices of Industrial Production — i.e. the
``JPN_IND_PROD`` resolution target.

Indicator definitions live in ``data/macro_library_estat.csv``.

Wired §3.1 Stage D.4 (2026-04-30) for ``JPN_IND_PROD``. All aggregator
paths (FRED / OECD / IMF) are frozen at 2023-11 — a documented upstream
freeze, not a path issue. e-Stat direct via METI's IP table is the only
fresh-data path.

API conventions:
  - Base: https://api.e-stat.go.jp/rest/3.0/app/json/getStatsData
  - Authentication: query parameter ``appId``
  - A "table" is identified by ``statsDataId`` (a 9-digit number).
  - Multi-dimension tables need ``cdCat01``/``cdCat02``/... category-
    code filters to slice down to a single time series.
  - Response is deeply-nested JSON: GET_STATS_DATA → STATISTICAL_DATA →
    DATA_INF → VALUE = list of {"@time": "YYYYMMDD", "$": "value"}.

Series ID convention used in the registry:
  - Plain ``<statsDataId>`` if the table is single-series (rare).
  - ``<statsDataId>?cdCat01=XXX&cdCat02=YYY`` for multi-dim tables — the
    string after ``?`` is interpreted verbatim as additional URL-encoded
    query parameters appended to the API call.
"""

from __future__ import annotations

import json
import os
import pathlib
import time
from datetime import date, datetime
from urllib.parse import parse_qsl, urlencode

import pandas as pd
import requests


_LIBRARY_CSV = pathlib.Path(__file__).parent.parent / "data" / "macro_library_estat.csv"
ESTAT_BASE = "https://api.e-stat.go.jp/rest/3.0/app/json/getStatsData"
DEFAULT_HIST_START = "1990-01-01"

# e-Stat doesn't typically WAF-block default User-Agents but we send a
# polite identifier matching the existing sources/* convention.
_HEADERS = {
    "User-Agent": "market_dash_auto/1.0 (+https://github.com/Kasim81/market_dash_auto)",
    "Accept": "application/json",
}


# ---------------------------------------------------------------------------
# LIBRARY LOADER
# ---------------------------------------------------------------------------

def load_library() -> list[dict]:
    """Load e-Stat indicator definitions from macro_library_estat.csv."""
    if not _LIBRARY_CSV.exists():
        return []
    df = pd.read_csv(_LIBRARY_CSV, dtype=str, keep_default_na=False)
    df["sort_key"] = pd.to_numeric(df["sort_key"], errors="coerce").fillna(0)
    df = df.sort_values("sort_key")
    result = []
    for _, row in df.iterrows():
        result.append({
            "source":       "e-Stat",
            "source_id":    row["series_id"].strip(),
            "col":          row["col"].strip(),
            "name":         row["name"].strip(),
            "country":      row.get("country", "").strip() or "JPN",
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

def _split_series_id(series_id: str) -> tuple[str, dict]:
    """Split '<statsDataId>?cdCat01=XX&cdCat02=YY' → (statsDataId, {cdCat01:XX,...})."""
    if "?" not in series_id:
        return series_id.strip(), {}
    sid, qs = series_id.split("?", 1)
    extras = dict(parse_qsl(qs))
    return sid.strip(), extras


def fetch_series(
    series_id: str,
    start: str = DEFAULT_HIST_START,
    timeout: int = 60,
    retries: int = 3,
) -> dict | None:
    """Fetch a single e-Stat series; returns the parsed JSON response or None.

    series_id format: '<statsDataId>' or '<statsDataId>?cdCat01=...&cdCat02=...'
    Reads ESTAT_APP_ID from env. Without a key, returns None gracefully so
    the workflow can proceed; the missing data surfaces in Section D / audit.
    """
    app_id = os.environ.get("ESTAT_APP_ID", "")
    if not app_id:
        print(f"    [e-Stat] no ESTAT_APP_ID env var — skipping {series_id}")
        return None

    stats_data_id, extras = _split_series_id(series_id)
    if not stats_data_id:
        print(f"    [e-Stat] invalid series_id {series_id!r}")
        return None

    params = {
        "appId": app_id,
        "statsDataId": stats_data_id,
        "lang": "E",
    }
    params.update(extras)

    for attempt in range(retries):
        try:
            resp = requests.get(ESTAT_BASE, params=params, headers=_HEADERS, timeout=timeout)
            if resp.status_code == 200 and resp.text:
                try:
                    doc = resp.json()
                except json.JSONDecodeError as e:
                    print(f"    [e-Stat] JSON decode failed for {stats_data_id}: {e}")
                    return None
                # e-Stat returns 200 even for query errors; check the RESULT block.
                result = doc.get("GET_STATS_DATA", {}).get("RESULT", {})
                status = result.get("STATUS")
                if status not in (0, "0"):
                    err_msg = result.get("ERROR_MSG", "<no message>")
                    print(f"    [e-Stat] API error STATUS={status} for {stats_data_id}: {err_msg}")
                    return None
                return doc
            if 500 <= resp.status_code < 600:
                wait = 2 ** attempt
                print(f"    [e-Stat HTTP {resp.status_code}] {stats_data_id} — backing off {wait}s")
                time.sleep(wait)
                continue
            print(f"    [e-Stat HTTP {resp.status_code}] {stats_data_id} — skipping")
            return None
        except requests.Timeout:
            wait = 2 ** attempt
            print(f"    [e-Stat timeout] {stats_data_id} — backing off {wait}s")
            time.sleep(wait)
        except requests.RequestException as e:
            print(f"    [e-Stat request error] {stats_data_id}: {e} — skipping")
            return None

    print(f"    [e-Stat FAIL] {stats_data_id} — {retries} attempts exhausted")
    return None


# ---------------------------------------------------------------------------
# JSON PARSING
# ---------------------------------------------------------------------------
# e-Stat response shape (JSON):
#   GET_STATS_DATA
#     RESULT { STATUS: 0, ERROR_MSG: "" }
#     STATISTICAL_DATA
#       DATA_INF
#         VALUE = [
#           { "@time": "2024010100", "@cat01": "...", "$": "100.5" },
#           ...
#         ]
# `@time` formats: YYYY010000=annual, YYYYMM0000=monthly, YYYYMMDDDD=daily
# (the trailing zeros / digits encode period-type).

def parse_response(doc: dict, series_id: str) -> list[tuple[date, float]]:
    """Parse e-Stat JSON response → list of (date, value) tuples.

    When the underlying table has multiple dimensions and the `series_id`
    didn't fully filter it down to a single series, this returns observations
    for ALL slices (caller must aggregate / filter further). For our usage
    we expect series_id to include sufficient ``cdCatNN`` filters to yield
    one obs per period.
    """
    obs: list[tuple[date, float]] = []
    if not doc:
        return obs

    try:
        values = (doc["GET_STATS_DATA"]["STATISTICAL_DATA"]
                     ["DATA_INF"]["VALUE"])
    except (KeyError, TypeError):
        print(f"    [e-Stat] unexpected JSON schema for {series_id}")
        return obs

    if isinstance(values, dict):
        values = [values]   # single-obs response is a dict not a list

    for v in values:
        time_raw = str(v.get("@time", "")).strip()
        val_raw = str(v.get("$", "")).strip()
        if not time_raw or not val_raw or val_raw in ("...", "-", "***"):
            continue
        d = _parse_estat_time(time_raw)
        if d is None:
            continue
        try:
            val = float(val_raw)
        except ValueError:
            continue
        obs.append((d, val))

    # Multiple slices may share the same time period; if so, callers should
    # have constrained via cdCatNN. Defensive dedupe — first wins.
    seen = set()
    deduped: list[tuple[date, float]] = []
    for d, v in obs:
        if d in seen:
            continue
        seen.add(d)
        deduped.append((d, v))
    return sorted(deduped)


def _parse_estat_time(t: str) -> date | None:
    """Parse e-Stat @time strings → date.

    e-Stat encodes period type in trailing zeros of a 10-digit string:
        YYYY010000  → annual (year-end mapping)
        YYYYMM0000  → monthly (month-start mapping)
        YYYYQ.0000  → quarterly (handled separately by some tables)
        YYYYMMDDDD  → daily

    Plain ISO formats are also accepted as a fallback.
    """
    t = t.strip()
    if not t:
        return None
    # Try plain ISO first
    for fmt in ("%Y-%m-%d", "%Y-%m", "%Y/%m/%d", "%Y/%m"):
        try:
            return datetime.strptime(t if "-" in t or "/" in t else "", fmt).date()
        except (ValueError, TypeError):
            continue
    # 10-digit e-Stat @time
    if t.isdigit() and len(t) == 10:
        yr = int(t[:4])
        mm = int(t[4:6])
        dd = int(t[6:8])
        # tail = int(t[8:10])
        if mm == 0:
            return None
        if mm == 1 and dd == 0:
            # annual marker (YYYY010000) — return year-end
            return date(yr, 12, 31)
        if dd == 0:
            # monthly marker (YYYYMM0000) — return month-start
            try:
                return date(yr, mm, 1)
            except ValueError:
                return None
        # daily
        try:
            return date(yr, mm, dd)
        except ValueError:
            return None
    # 8-digit (YYYYMMDD) fallback
    if t.isdigit() and len(t) == 8:
        try:
            return datetime.strptime(t, "%Y%m%d").date()
        except ValueError:
            return None
    # 6-digit (YYYYMM) fallback
    if t.isdigit() and len(t) == 6:
        try:
            return datetime.strptime(t + "01", "%Y%m%d").date()
        except ValueError:
            return None
    return None


def fetch_series_as_pandas(
    series_id: str,
    start: str = DEFAULT_HIST_START,
    col_name: str | None = None,
) -> pd.Series | None:
    """Fetch one series and return a date-indexed pd.Series, or None on failure."""
    doc = fetch_series(series_id, start=start)
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
