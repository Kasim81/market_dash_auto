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

def _opt_float(row, key: str) -> float | None:
    """Parse an optional numeric library cell; blank / unparseable -> None."""
    raw = (row.get(key, "") or "").strip()
    if raw == "":
        return None
    try:
        return float(raw)
    except ValueError:
        return None


def load_library() -> list[dict]:
    """Load DB.nomics indicator definitions from macro_library_dbnomics.csv."""
    df = pd.read_csv(_LIBRARY_CSV, dtype=str, keep_default_na=False)
    df["sort_key"] = pd.to_numeric(df["sort_key"], errors="coerce").fillna(0)
    df = df.sort_values("sort_key")
    result = []
    for _, row in df.iterrows():
        result.append({
            "source":       "DB.nomics",
            "source_id":    row["series_id"].strip(),
            "col":          row["col"].strip(),
            "name":         row["name"].strip(),
            "country":      row["country"].strip(),
            "category":     row["category"].strip(),
            "subcategory":  row["subcategory"].strip(),
            "concept":      row.get("concept", "").strip(),
            "cycle_timing": row.get("cycle_timing", "").strip(),
            "units":        row["units"].strip(),
            "frequency":    row["frequency"].strip(),
            "notes":        row["notes"].strip(),
            "sort_key":     float(row["sort_key"]),
            # Optional plausibility band (blank unless declared). Drives the
            # fetch-time guard in fetch_macro_economic._fetch_dbnomics_* and
            # mirrors the same columns data_audit Section E reads for the
            # committed-value backstop.
            "plausible_min": _opt_float(row, "plausible_min"),
            "plausible_max": _opt_float(row, "plausible_max"),
            # Legacy alias for existing fetch_macro_dbnomics callers:
            "series_id":    row["series_id"].strip(),
        })
    return result


# ---------------------------------------------------------------------------
# SERIES FETCH
# ---------------------------------------------------------------------------

# Circuit breaker: DB.nomics carries 13 series fetched in both the snapshot
# and history passes (26 calls). When the API is unresponsive, each call
# burns retries × timeout + backoff, so a full outage would otherwise stall
# the daily pipeline for ~an hour (the failure mode seen 2026-05-27). After
# _BREAKER_THRESHOLD consecutive hard failures we assume the API is down and
# short-circuit every remaining call this process, capping total wasted time
# at ~1-2 min. A successful (or merely server-responding) call resets the
# counter, so isolated blips never trip it — only a sustained outage does.
_CONSEC_FAILURES = 0
_BREAKER_TRIPPED = False
_BREAKER_THRESHOLD = 3


def _register_failure(series_id: str) -> None:
    global _CONSEC_FAILURES, _BREAKER_TRIPPED
    _CONSEC_FAILURES += 1
    if _CONSEC_FAILURES >= _BREAKER_THRESHOLD and not _BREAKER_TRIPPED:
        _BREAKER_TRIPPED = True
        print(f"    [DB.nomics BREAKER OPEN] {_CONSEC_FAILURES} consecutive failures — "
              f"skipping remaining DB.nomics fetches this run (API appears unreachable)")


def _reset_failures() -> None:
    global _CONSEC_FAILURES
    _CONSEC_FAILURES = 0


def fetch_series(
    series_id: str,
    retries: int = 2,
    backoff_base: int = 2,
    timeout: int = 12,
) -> dict | None:
    """
    Fetch a single series document (including observations) from DB.nomics.
    series_id format: "PROVIDER/DATASET/SERIES_CODE".  Returns the first
    docs[] entry or None on failure.

    Bounded for fail-fast: tight timeout + few retries, plus a process-level
    circuit breaker (see above) so a DB.nomics outage degrades the 13 series
    to last-known/blank within ~1-2 min instead of stalling the pipeline.
    """
    global _BREAKER_TRIPPED
    if _BREAKER_TRIPPED:
        print(f"    [DB.nomics SKIP] {series_id} — circuit breaker open (API unresponsive this run)")
        return None

    url = f"{DBNOMICS_BASE}/series"
    params = {"observations": "1", "series_ids": series_id, "limit": 1}

    for attempt in range(retries):
        try:
            resp = requests.get(url, params=params, timeout=timeout)

            if resp.status_code == 200:
                _reset_failures()  # server is up
                data = resp.json()
                docs = data.get("series", {}).get("docs", [])
                return docs[0] if docs else None

            if resp.status_code == 429 or resp.status_code >= 500:
                if attempt + 1 < retries:
                    wait = backoff_base ** (attempt + 1)
                    print(
                        f"    [DB.nomics HTTP {resp.status_code}] {series_id} — "
                        f"backing off {wait}s (attempt {attempt + 1}/{retries})"
                    )
                    time.sleep(wait)
                continue

            # Other 4xx: the server responded — a series-specific miss, not an
            # outage. Reset the breaker counter and skip just this series.
            _reset_failures()
            print(f"    [DB.nomics HTTP {resp.status_code}] {series_id} — skipping")
            return None

        except requests.exceptions.Timeout:
            if attempt + 1 < retries:
                wait = backoff_base ** (attempt + 1)
                print(f"    [DB.nomics timeout] {series_id} — backing off {wait}s")
                time.sleep(wait)

        except requests.exceptions.RequestException as e:
            print(f"    [DB.nomics request error] {series_id}: {e} — skipping")
            _register_failure(series_id)
            return None

    print(f"    [DB.nomics FAIL] {series_id} — {retries} attempts exhausted")
    _register_failure(series_id)
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


def filter_plausible(
    obs: list[tuple[str, float]],
    lo: float | None,
    hi: float | None,
    col: str = "",
) -> list[tuple[str, float]]:
    """Drop observations whose value falls outside [lo, hi] (inclusive).

    A plausibility guard for the fetch layer: some DB.nomics mirrors publish
    physically impossible values when their upstream scrape breaks (e.g. the
    ISM Manufacturing PMI mirror returned ~10 for a 0-100 diffusion index in
    late 2025 where the real prints were ~48-53). Filtering rather than failing
    means one corrupted tail can't poison the series — the pipeline degrades to
    the last plausible observation, exactly as it does for a missing point.

    Bounds are optional; a None bound disables that side. Dropped observations
    are logged so a persistent upstream break is visible in pipeline.log.
    """
    if lo is None and hi is None:
        return obs
    kept: list[tuple[str, float]] = []
    dropped: list[tuple[str, float]] = []
    for p, v in obs:
        if (lo is not None and v < lo) or (hi is not None and v > hi):
            dropped.append((p, v))
        else:
            kept.append((p, v))
    if dropped:
        band = f"[{lo}, {hi}]"
        preview = ", ".join(f"{p}={v}" for p, v in dropped[-6:])
        print(
            f"    [DB.nomics PLAUSIBILITY] {col or '?'}: dropped "
            f"{len(dropped)} obs outside {band} (most recent: {preview})",
            flush=True,
        )
    return kept


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
