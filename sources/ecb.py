"""
sources/ecb.py
==============
ECB Data Portal source module (data-api.ecb.europa.eu).

SDMX 2.1 over REST. No registration, no API key, CSV/JSON/XML.
Series addressed by ``<dataset>/<key>`` where the key is a dot-separated
SDMX dimension tuple, e.g. ``FM/D.U2.EUR.4F.KR.DFR.LEV`` (Daily, Euro
area, EUR, Financial market data, Key interest rate, Deposit Facility
Rate, level).

Per G20 catalogue: same-day on press release for most headline series.

Indicator definitions live in ``data/macro_library_ecb.csv``.

Wired §3.1 Stage D.2 (2026-04-30) to resolve ``EA_DEPOSIT_RATE`` (FRED
ECBDFR frozen at 2025-06-13; T1 candidates via DB.nomics ECB-mirror were
themselves stale at 2025-02 so T0 was actually fresher than T1; T2 = ECB
direct is the only fresh path).

The legacy ``fetch_ecb_euro_ig_spread()`` inline call in
``compute_macro_market.py`` uses the same base URL but is not refactored
through this module yet — that's a future cleanup. New work should add
rows to ``macro_library_ecb.csv`` and route via ``fetch_series``.
"""

from __future__ import annotations

import io
import pathlib
import time
from datetime import date, datetime

import pandas as pd
import requests


_LIBRARY_CSV = pathlib.Path(__file__).parent.parent / "data" / "macro_library_ecb.csv"
ECB_BASE = "https://data-api.ecb.europa.eu/service/data"
DEFAULT_HIST_START = "2000-01-01"


# ---------------------------------------------------------------------------
# LIBRARY LOADER
# ---------------------------------------------------------------------------

def load_library() -> list[dict]:
    """Load ECB Data Portal indicator definitions from macro_library_ecb.csv."""
    if not _LIBRARY_CSV.exists():
        return []
    df = pd.read_csv(_LIBRARY_CSV, dtype=str, keep_default_na=False)
    df["sort_key"] = pd.to_numeric(df["sort_key"], errors="coerce").fillna(0)
    df = df.sort_values("sort_key")
    result = []
    for _, row in df.iterrows():
        result.append({
            "source":       "ECB",
            "source_id":    row["series_id"].strip(),
            "col":          row["col"].strip(),
            "name":         row["name"].strip(),
            "country":      row.get("country", "").strip() or "EA19",
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
    timeout: int = 30,
    retries: int = 3,
) -> str | None:
    """Fetch a single ECB series as raw CSV text.

    series_id: '<dataset>/<key>' format, e.g. 'FM/D.U2.EUR.4F.KR.DFR.LEV'.
    Returns CSV body (UTF-8) or None on failure.
    """
    if "/" not in series_id:
        print(f"    [ECB] invalid series_id {series_id!r} (expected '<DATASET>/<KEY>')")
        return None

    url = f"{ECB_BASE}/{series_id}?format=csvdata&startPeriod={start}&detail=dataonly"
    headers = {"Accept": "text/csv"}

    for attempt in range(retries):
        try:
            resp = requests.get(url, headers=headers, timeout=timeout)
            if resp.status_code == 200 and resp.text.strip():
                return resp.text
            if 500 <= resp.status_code < 600:
                wait = 2 ** attempt
                print(f"    [ECB HTTP {resp.status_code}] {series_id} — backing off {wait}s")
                time.sleep(wait)
                continue
            print(f"    [ECB HTTP {resp.status_code}] {series_id} — skipping")
            return None
        except requests.Timeout:
            wait = 2 ** attempt
            print(f"    [ECB timeout] {series_id} — backing off {wait}s")
            time.sleep(wait)
        except requests.RequestException as e:
            print(f"    [ECB request error] {series_id}: {e} — skipping")
            return None

    print(f"    [ECB FAIL] {series_id} — {retries} attempts exhausted")
    return None


# ---------------------------------------------------------------------------
# CSV PARSING
# ---------------------------------------------------------------------------
# ECB SDMX CSV (csvdata flavour):
#   KEY,FREQ,...dimension cols...,TIME_PERIOD,OBS_VALUE,OBS_STATUS,...
# We only care about TIME_PERIOD + OBS_VALUE; the rest are dimension echoes
# we ignore.

def parse_csv(text: str, series_id: str) -> list[tuple[date, float]]:
    """Parse ECB CSV response → list of (date, value) tuples (None values dropped)."""
    obs: list[tuple[date, float]] = []
    if not text or not text.strip():
        return obs

    try:
        df = pd.read_csv(io.StringIO(text))
    except Exception as e:
        print(f"    [ECB] CSV parse failed for {series_id}: {e}")
        return obs

    if "TIME_PERIOD" not in df.columns or "OBS_VALUE" not in df.columns:
        print(f"    [ECB] unexpected CSV schema for {series_id}: {list(df.columns)[:8]}")
        return obs

    for _, row in df.iterrows():
        d_str = str(row["TIME_PERIOD"]).strip()
        v_raw = row["OBS_VALUE"]
        if pd.isna(v_raw) or not d_str or d_str.lower() in ("nan", ""):
            continue
        # ECB cadence: YYYY-MM-DD (daily), YYYY-MM (monthly), YYYY-Qn (quarterly), YYYY (annual)
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
    """Parse ECB period strings to a calendar date (period-end conventions match
    OECD/IMF — quarterly maps to last day of last month; annual to year-end)."""
    p = p.strip()
    if not p:
        return None
    # Daily
    try:
        return datetime.strptime(p, "%Y-%m-%d").date()
    except ValueError:
        pass
    # Monthly
    try:
        return datetime.strptime(p + "-01", "%Y-%m-%d").date()
    except ValueError:
        pass
    # Quarterly: YYYY-Qn
    if "-Q" in p:
        try:
            yr, q = p.split("-Q")
            month = int(q) * 3
            return date(int(yr), month, 1)
        except (ValueError, IndexError):
            pass
    # Annual
    if len(p) == 4 and p.isdigit():
        return date(int(p), 12, 31)
    return None


def fetch_series_as_pandas(
    series_id: str,
    start: str = DEFAULT_HIST_START,
    col_name: str | None = None,
) -> pd.Series | None:
    """Fetch one series and return a date-indexed pd.Series, or None on failure."""
    text = fetch_series(series_id, start=start)
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
