"""
sources/bdf.py
==============
Banque de France (Webstat) time-series source module.

Banque de France is the ultimate (primary) source for French monetary,
financial and balance-of-payments series that aggregators (ECB SDW, OECD, IMF,
DB.nomics) republish — so it ranks as a PRIMARY source and wins ties.

REST returning SDMX-JSON.

    https://api.webstat.banque-france.fr/webstat-fr/v1/data/<dataset>/<key>

Auth: register on the Webstat developer portal
(https://developer.webstat.banque-france.fr/), create an application, and set
its Client Id in the ``BDF_API_KEY`` env var. The Webstat gateway is IBM API
Connect, so the key is sent as the ``X-IBM-Client-Id`` header. Without a key the
module no-ops gracefully; the gap surfaces in the daily audit.

Series ID convention: ``<dataset>/<key>``, e.g.
``IR/M.FR.EUR.RT.MIR.A2A.AAAAAAA`` (the dataset code + the dot-separated SDMX
dimension key).

SDMX-JSON parsing: the time dimension lives in
``structure.dimensions.observation`` and each series' ``observations`` map is
keyed by the time-dimension index → ``[value, ...]``.
"""

from __future__ import annotations

import os
import pathlib
import time
from datetime import date, datetime

import pandas as pd
import requests


_LIBRARY_CSV = pathlib.Path(__file__).parent.parent / "data" / "macro_library_bdf.csv"
BDF_BASE = "https://api.webstat.banque-france.fr/webstat-fr/v1/data"
DEFAULT_HIST_START = "1970-01-01"

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; market_dash_auto/1.0)",
    "Accept": "application/json",
}


# ---------------------------------------------------------------------------
# LIBRARY LOADER
# ---------------------------------------------------------------------------

def load_library() -> list[dict]:
    """Load Banque de France indicator definitions from macro_library_bdf.csv.

    Returns [] when the library is empty/absent (scaffold state)."""
    if not _LIBRARY_CSV.exists():
        return []
    df = pd.read_csv(_LIBRARY_CSV, dtype=str, keep_default_na=False)
    if df.empty:
        return []
    df["sort_key"] = pd.to_numeric(df["sort_key"], errors="coerce").fillna(0)
    df = df.sort_values("sort_key")
    result = []
    for _, row in df.iterrows():
        result.append({
            "source":       "Banque de France",
            "source_id":    row["series_id"].strip(),
            "col":          row["col"].strip(),
            "name":         row["name"].strip(),
            "country":      row.get("country", "").strip() or "FRA",
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
    timeout: int = 60,
    retries: int = 3,
) -> dict | None:
    """Fetch a single Webstat series as parsed SDMX-JSON, or None.

    series_id: '<dataset>/<key>'. Reads BDF_API_KEY from env; without it the
    call is skipped gracefully (returns None).
    """
    key = os.environ.get("BDF_API_KEY", "").strip()
    if not key:
        print(f"    [BdF] no BDF_API_KEY env var — skipping {series_id}")
        return None
    if "/" not in series_id:
        print(f"    [BdF] invalid series_id {series_id!r} (expected '<DATASET>/<KEY>')")
        return None

    url = f"{BDF_BASE}/{series_id}"
    # Webstat sits behind an IBM API Connect gateway: client id (+ optional
    # secret) sent as X-IBM-Client-* headers. The 401 body distinguishes
    # "Invalid client id or secret", so we forward a secret when one is set.
    headers = {**_HEADERS, "X-IBM-Client-Id": key}
    secret = os.environ.get("BDF_API_SECRET", "").strip()
    if secret:
        headers["X-IBM-Client-Secret"] = secret
    params = {"format": "sdmx-json"}
    for attempt in range(retries):
        try:
            resp = requests.get(url, headers=headers, params=params, timeout=timeout)
            if resp.status_code == 200 and resp.text.strip():
                try:
                    return resp.json()
                except ValueError as e:
                    print(f"    [BdF] JSON decode failed for {series_id}: {e}")
                    return None
            if resp.status_code in (401, 403):
                print(f"    [BdF HTTP {resp.status_code}] {series_id} — check BDF_API_KEY")
                return None
            if 500 <= resp.status_code < 600:
                wait = 2 ** attempt
                print(f"    [BdF HTTP {resp.status_code}] {series_id} — backing off {wait}s")
                time.sleep(wait)
                continue
            print(f"    [BdF HTTP {resp.status_code}] {series_id} — skipping")
            return None
        except requests.Timeout:
            wait = 2 ** attempt
            print(f"    [BdF timeout] {series_id} — backing off {wait}s")
            time.sleep(wait)
        except requests.RequestException as e:
            print(f"    [BdF request error] {series_id}: {e} — skipping")
            return None

    print(f"    [BdF FAIL] {series_id} — {retries} attempts exhausted")
    return None


# ---------------------------------------------------------------------------
# SDMX-JSON PARSING
# ---------------------------------------------------------------------------

def parse_json(doc: dict, series_id: str) -> list[tuple[date, float]]:
    """Parse an SDMX-JSON document → list of (date, value) tuples.

    The time periods come from the observation-level time dimension; each
    series' observation map is keyed by that dimension's index."""
    obs: list[tuple[date, float]] = []
    if not doc:
        return obs
    data = doc.get("data", doc)
    try:
        structure = data["structure"]
        time_dim = structure["dimensions"]["observation"][0]
        periods = [v["id"] for v in time_dim["values"]]
        series_map = data["dataSets"][0]["series"]
    except (KeyError, IndexError, TypeError):
        print(f"    [BdF] unexpected SDMX-JSON shape for {series_id}")
        return obs

    merged: dict[date, float] = {}
    for series in series_map.values():
        for idx_str, vals in series.get("observations", {}).items():
            try:
                d = _parse_period(periods[int(idx_str)])
            except (ValueError, IndexError):
                continue
            if d is None or not vals:
                continue
            try:
                merged[d] = float(vals[0])
            except (ValueError, TypeError):
                continue
    return sorted(merged.items())


def _parse_period(p: str) -> date | None:
    """Parse an SDMX TIME_PERIOD string to a calendar date."""
    p = (p or "").strip()
    if not p:
        return None
    try:
        return datetime.strptime(p, "%Y-%m-%d").date()
    except ValueError:
        pass
    try:
        return datetime.strptime(p + "-01", "%Y-%m-%d").date()
    except ValueError:
        pass
    if "-Q" in p:
        try:
            yr, q = p.split("-Q")
            return date(int(yr), int(q) * 3, 1)
        except (ValueError, IndexError):
            pass
    if len(p) == 4 and p.isdigit():
        return date(int(p), 12, 31)
    return None


def fetch_series_as_pandas(
    series_id: str,
    col_name: str | None = None,
) -> pd.Series | None:
    """Fetch one series and return a date-indexed pd.Series, or None on failure."""
    doc = fetch_series(series_id)
    if doc is None:
        return None
    obs = parse_json(doc, series_id)
    if not obs:
        return None
    s = pd.Series(
        {pd.Timestamp(d): v for d, v in obs},
        name=col_name or series_id,
    )
    return s.sort_index()
