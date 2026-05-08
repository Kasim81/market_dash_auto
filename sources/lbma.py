"""
sources/lbma.py
================
LBMA (London Bullion Market Association) precious-metal fixings — direct
JSON feed at prices.lbma.org.uk.

LBMA publishes one JSON file per (metal, fix-window) pair, e.g.:
    https://prices.lbma.org.uk/json/gold_pm.json
    https://prices.lbma.org.uk/json/gold_am.json
    https://prices.lbma.org.uk/json/silver.json
    https://prices.lbma.org.uk/json/platinum_pm.json   (LPPM)
    https://prices.lbma.org.uk/json/platinum_am.json
    https://prices.lbma.org.uk/json/palladium_pm.json
    https://prices.lbma.org.uk/json/palladium_am.json

Body shape (canonical):

    [
      {"d": "1968-04-01", "v": [38.0, 15.83, 0]},
      {"d": "1968-04-02", "v": [38.0, 15.83, 0]},
      ...
    ]

`v` is a 3-element array ordered [USD, GBP, EUR]. Pre-Euro dates carry 0
in the EUR slot. Daily series, no API key required, no auth headers needed.

Indicator definitions live in data/macro_library_lbma.csv. Each row carries
a `sub_field` column naming the currency to extract ("USD", "GBP", or
"EUR"); the loader maps that to the array index at fetch time.

Wired §3.9 (2026-05-08 / 2026-05-09 — superseding the brief Nasdaq Data
Link attempt that hit a paid-tier 403) to add a long-run daily gold series
back to 1968 after FRED's GOLDPMGBD228NLBM was discontinued in 2017.
Driven by the regime AA Phase 0c long-run availability requirement.
"""

from __future__ import annotations

import json
import pathlib
import time

import pandas as pd
import requests


_LIBRARY_CSV = pathlib.Path(__file__).parent.parent / "data" / "macro_library_lbma.csv"

# Canonical primary host. We list mirrors in case the primary is rate-
# limited or temporarily redirected; same JSON path on each.
LBMA_HOSTS = [
    "https://prices.lbma.org.uk",
]

# A browser-like UA avoids the occasional 403 some CDNs return for the
# bare python-requests default. The endpoint itself is public / no auth.
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json,text/plain,*/*;q=0.8",
    "Accept-Language": "en-GB,en;q=0.9",
}

# Map sub_field name → index into the JSON `v` array.
_CURRENCY_INDEX = {"USD": 0, "GBP": 1, "EUR": 2}


# ---------------------------------------------------------------------------
# LIBRARY LOADER
# ---------------------------------------------------------------------------

def load_library() -> list[dict]:
    """Load LBMA indicator definitions from macro_library_lbma.csv."""
    if not _LIBRARY_CSV.exists():
        return []
    df = pd.read_csv(_LIBRARY_CSV, dtype=str, keep_default_na=False)
    df["sort_key"] = pd.to_numeric(df["sort_key"], errors="coerce").fillna(0)
    df = df.sort_values("sort_key")
    result = []
    for _, row in df.iterrows():
        result.append({
            "source":       "LBMA",
            "source_id":    row["series_id"].strip(),
            "col":          row["col"].strip(),
            "name":         row["name"].strip(),
            "country":      row.get("country", "").strip() or "GLOBAL",
            "category":     row["category"].strip(),
            "subcategory":  row["subcategory"].strip(),
            "concept":      row.get("concept", "").strip(),
            "cycle_timing": row.get("cycle_timing", "").strip(),
            "units":        row["units"].strip(),
            "frequency":    row["frequency"].strip(),
            "notes":        row.get("notes", "").strip(),
            "sort_key":     float(row["sort_key"]),
            "series_id":    row["series_id"].strip(),
            "sub_field":    row.get("sub_field", "").strip(),
        })
    return result


# ---------------------------------------------------------------------------
# SERIES FETCH
# ---------------------------------------------------------------------------

def _fetch_raw(series_id: str, timeout: int = 30, retries: int = 3) -> list | None:
    """Hit prices.lbma.org.uk for the named series. Returns parsed JSON list."""
    last_exc: Exception | None = None
    for attempt in range(retries):
        for host in LBMA_HOSTS:
            url = f"{host}/json/{series_id}.json"
            try:
                resp = requests.get(url, headers=_HEADERS, timeout=timeout)
                if resp.status_code != 200:
                    print(f"    [LBMA HTTP {resp.status_code}] {series_id} via {host}")
                    continue
                if not resp.text:
                    print(f"    [LBMA] {series_id} via {host}: empty body")
                    continue
                try:
                    return resp.json()
                except json.JSONDecodeError as e:
                    head = resp.text.lstrip()[:120]
                    print(f"    [LBMA] {series_id} via {host}: non-JSON body "
                          f"(first 120: {head!r}) — {e}")
                    continue
            except requests.Timeout:
                print(f"    [LBMA timeout] {series_id} via {host}")
                last_exc = TimeoutError(f"timeout on {url}")
                continue
            except requests.RequestException as e:
                print(f"    [LBMA request error] {series_id} via {host}: {e}")
                last_exc = e
                continue
        # All hosts failed for this attempt — back off before retry.
        wait = 2 ** attempt
        if attempt + 1 < retries:
            print(f"    [LBMA] all hosts failed for {series_id} — backing off {wait}s")
            time.sleep(wait)

    print(f"    [LBMA FAIL] {series_id} — {retries} attempts × {len(LBMA_HOSTS)} host(s) "
          f"exhausted ({last_exc})")
    return None


def fetch_series_as_pandas(
    series_id: str,
    sub_field: str = "USD",
    col_name: str | None = None,
) -> pd.Series | None:
    """Fetch one LBMA fix series and return a date-indexed pd.Series.

    series_id : LBMA JSON file stem, e.g. 'gold_pm', 'gold_am', 'silver'.
    sub_field : 'USD' / 'GBP' / 'EUR'. Defaults to USD.
    col_name  : optional name for the returned Series (default = series_id).

    Returns None on failure (logged to stdout for pipeline.log capture).
    """
    sub = (sub_field or "USD").strip().upper()
    if sub not in _CURRENCY_INDEX:
        print(f"    [LBMA] unknown sub_field {sub_field!r} for {series_id} — "
              f"expected one of {list(_CURRENCY_INDEX)}; defaulting to USD")
        sub = "USD"
    idx = _CURRENCY_INDEX[sub]

    data = _fetch_raw(series_id)
    if not data:
        return None

    # Normalise: each row should look like {"d": "YYYY-MM-DD", "v": [USD, GBP, EUR]}.
    # We tolerate slight key-case variations.
    obs: dict[pd.Timestamp, float] = {}
    for row in data:
        if not isinstance(row, dict):
            continue
        d_raw = row.get("d") or row.get("D") or row.get("date")
        v_raw = row.get("v") or row.get("V") or row.get("values")
        if d_raw is None or v_raw is None:
            continue
        try:
            d = pd.Timestamp(d_raw)
        except (ValueError, TypeError):
            continue
        if not isinstance(v_raw, (list, tuple)) or len(v_raw) <= idx:
            continue
        val = v_raw[idx]
        try:
            f = float(val)
        except (TypeError, ValueError):
            continue
        # LBMA carries 0.0 placeholders for the EUR slot pre-1999 and
        # for any non-fixed dates. Treat exact 0 as a missing observation
        # — gold/silver have never legitimately fixed at 0 USD/GBP/EUR.
        if f == 0.0:
            continue
        obs[d] = f

    if not obs:
        print(f"    [LBMA] {series_id}/{sub} parsed 0 usable observations from "
              f"{len(data)} raw rows")
        return None

    s = pd.Series(obs, name=col_name or series_id).sort_index()
    return s
