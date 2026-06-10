"""
sources/alpha_vantage.py
========================
Alpha Vantage REST source module — snapshot fundamentals (PE / forward PE
/ PEG / dividend yield / EPS / book value) for major index ETFs and
individual equities via the OVERVIEW function.

    https://www.alphavantage.co/query?function=OVERVIEW&symbol=SPY&apikey=<key>

Wired §3.3 (2026-06-10) — module + library schema only. The free tier
allows 25 requests/day so the daily pipeline cannot poll a large set
of tickers without burning the budget; we only smoke-test a single
symbol (SPY) per run, and decide separately when/how to materialise
the snapshots into a per-ticker `data/equity_pe_snapshot.csv` (which
shape and refresh cadence the consumer wants is undecided).

Auth: register at alphavantage.co for a free Client API key, set as
``ALPHAVANTAGE_API_KEY`` env var (GitHub Secret of the same name in
this repo). Without a key the module no-ops gracefully — same posture
as sources/bdf.py.

Rate-limit detection: Alpha Vantage replies to over-quota requests with
a JSON body containing a ``Note`` field. We treat any response with
``Note`` (or an empty ``Symbol``) as a non-data response and surface it
through the audit channel.
"""

from __future__ import annotations

import os
import pathlib
import time

import pandas as pd
import requests


_LIBRARY_CSV = pathlib.Path(__file__).parent.parent / "data" / "macro_library_alpha_vantage.csv"
AV_BASE = "https://www.alphavantage.co/query"

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; market_dash_auto/1.0)",
    "Accept": "application/json",
}


# ---------------------------------------------------------------------------
# LIBRARY LOADER
# ---------------------------------------------------------------------------

def load_library() -> list[dict]:
    """Load Alpha Vantage indicator definitions from
    macro_library_alpha_vantage.csv.

    Returns [] when the library is empty/absent (scaffold state today).
    Populate the CSV once the storage shape for PE snapshots is decided."""
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
            "source":       "Alpha Vantage",
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
# OVERVIEW FETCH
# ---------------------------------------------------------------------------

def fetch_overview(
    symbol: str,
    api_key: str | None = None,
    timeout: int = 30,
    retries: int = 2,
) -> dict | None:
    """Fetch the OVERVIEW (snapshot fundamentals) for a symbol.

    Returns the parsed JSON dict on success — keys include ``Symbol``,
    ``Name``, ``PERatio``, ``ForwardPE``, ``PEGRatio``, ``DividendYield``,
    ``EPS``, ``BookValue``, ``MarketCapitalization``, ``Sector``,
    ``Industry``, etc.

    Returns None when:
      - ALPHAVANTAGE_API_KEY is unset (graceful no-op);
      - the response is empty / missing ``Symbol``;
      - the response carries a rate-limit ``Note`` field;
      - the HTTP call fails after retries.
    """
    key = (api_key or os.environ.get("ALPHAVANTAGE_API_KEY", "")).strip()
    if not key:
        print(f"    [AV] no ALPHAVANTAGE_API_KEY — skipping OVERVIEW for {symbol}")
        return None

    params = {"function": "OVERVIEW", "symbol": symbol, "apikey": key}
    last_err: Exception | str | None = None
    for attempt in range(retries + 1):
        try:
            resp = requests.get(AV_BASE, params=params, headers=_HEADERS, timeout=timeout)
        except requests.RequestException as e:
            last_err = e
            wait = 2 ** attempt
            print(f"    [AV] {symbol} request error: {e} — backing off {wait}s")
            time.sleep(wait)
            continue
        if resp.status_code != 200:
            last_err = f"HTTP {resp.status_code}"
            wait = 2 ** attempt
            print(f"    [AV HTTP {resp.status_code}] {symbol} — backing off {wait}s")
            time.sleep(wait)
            continue
        try:
            doc = resp.json()
        except ValueError as e:
            print(f"    [AV] {symbol} non-JSON body: {e}")
            return None
        if not isinstance(doc, dict) or not doc:
            print(f"    [AV] {symbol} empty response — symbol unknown or coverage gap")
            return None
        if "Note" in doc or "Information" in doc:
            note = (doc.get("Note") or doc.get("Information") or "").strip()
            print(f"    [AV RATE-LIMIT] {symbol} — {note[:200]}")
            return None
        if not doc.get("Symbol"):
            print(f"    [AV] {symbol} response missing Symbol field — assume coverage gap")
            return None
        return doc

    print(f"    [AV FAIL] {symbol} — last err: {last_err}")
    return None


def get_pe_ratios(symbol: str, api_key: str | None = None) -> dict | None:
    """Convenience: return just the PE-family floats from an OVERVIEW
    response, or None on miss. Output keys: ``pe_ttm`` (PERatio),
    ``pe_forward`` (ForwardPE), ``peg`` (PEGRatio), ``dividend_yield``,
    ``eps``, ``book_value``. Each value is float or None."""
    doc = fetch_overview(symbol, api_key=api_key)
    if doc is None:
        return None

    def _maybe_float(v):
        try:
            f = float(v)
        except (TypeError, ValueError):
            return None
        # Alpha Vantage encodes "missing" as the literal string "None" → NaN
        if f != f:  # NaN
            return None
        return f

    return {
        "symbol":        doc.get("Symbol"),
        "pe_ttm":        _maybe_float(doc.get("PERatio")),
        "pe_forward":    _maybe_float(doc.get("ForwardPE")),
        "peg":           _maybe_float(doc.get("PEGRatio")),
        "dividend_yield": _maybe_float(doc.get("DividendYield")),
        "eps":           _maybe_float(doc.get("EPS")),
        "book_value":    _maybe_float(doc.get("BookValue")),
        "name":          doc.get("Name"),
        "asset_type":    doc.get("AssetType"),
    }
