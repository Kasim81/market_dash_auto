"""
sources/equity_pe.py
====================
Equity valuation snapshots (§3.3) — trailing & forward P/E for the major-index
ETF set, accumulated into a dated history at ``data/equity_pe_snapshot.csv``.

Source preference chain (2026-07-16 decision): **FactIQ → yfinance → Alpha
Vantage**. FactIQ was evaluated and dropped — its warehouse is macro/labour/
trade/SEC and carries no equity-index P/E series, and as a session-scoped MCP
tool it is not reachable from the headless daily CI run in any case. So the
runtime chain is:

  1. **yfinance** ``.info`` (``trailingPE`` / ``forwardPE``) — real ETF-level
     P/E, no request quota. Primary.
  2. **Alpha Vantage** ``OVERVIEW`` (``PERatio`` / ``ForwardPE``) via
     ``sources/alpha_vantage.py`` — fallback when yfinance yields neither P/E
     (AV often returns ``None`` for ETF P/E and the free tier is 25 req/day, so
     it is a backstop, not the primary).

yfinance's own ``.info`` path uses Yahoo's crumb-gated ``quoteSummary`` endpoint
which is blocked from the build sandbox, so the live values are validated on the
first CI run (the smoke test skips when the host is unreachable). The
orchestration/merge/upsert logic is dependency-injected and unit-tested offline.

Storage: one row per (``asof_date``, ``ticker``) — re-running on the same day
upserts rather than duplicating, so the file grows into a daily P/E history
(yfinance only exposes a snapshot, so accumulating the daily snapshot is how the
history is built for free). Columns::

    asof_date,ticker,name,pe_ttm,pe_forward,source
"""

from __future__ import annotations

import pathlib

import pandas as pd

from sources import alpha_vantage

_SNAPSHOT_CSV = pathlib.Path(__file__).parent.parent / "data" / "equity_pe_snapshot.csv"
_COLUMNS = ["asof_date", "ticker", "name", "pe_ttm", "pe_forward", "source"]

# The major-index ETF set — broad, liquid, P/E-bearing funds (not leveraged /
# single-country micro slices). Ordered US-broad → US-size → DM → EM → regional.
MAJOR_INDEX_ETFS: list[tuple[str, str]] = [
    ("SPY", "S&P 500"),
    ("QQQ", "Nasdaq 100"),
    ("DIA", "Dow Jones Industrial Average"),
    ("IWM", "Russell 2000"),
    ("MDY", "S&P MidCap 400"),
    ("EFA", "MSCI EAFE (Developed ex-US)"),
    ("EEM", "MSCI Emerging Markets"),
    ("VGK", "FTSE Developed Europe"),
    ("EWJ", "MSCI Japan"),
]


def _coerce_pe(v) -> float | None:
    """Positive finite float, else None (a negative/zero P/E is meaningless as a
    valuation level — treat as missing)."""
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    if f != f or f <= 0 or f > 1e6:   # NaN, non-positive, or absurd
        return None
    return f


# ---------------------------------------------------------------------------
# SOURCE FETCHERS (each returns {"pe_ttm", "pe_forward", "name"} or None)
# ---------------------------------------------------------------------------

def yf_pe(ticker: str) -> dict | None:
    """yfinance ``.info`` trailing/forward P/E. None on any failure or when
    neither P/E is present."""
    try:
        import yfinance as yf
        info = yf.Ticker(ticker).info
    except Exception as e:                       # noqa: BLE001
        print(f"    [equity_pe] yfinance .info failed for {ticker}: {e}")
        return None
    if not isinstance(info, dict) or not info:
        return None
    ttm = _coerce_pe(info.get("trailingPE"))
    fwd = _coerce_pe(info.get("forwardPE"))
    if ttm is None and fwd is None:
        return None
    return {"pe_ttm": ttm, "pe_forward": fwd,
            "name": info.get("shortName") or info.get("longName")}


def av_pe(ticker: str) -> dict | None:
    """Alpha Vantage OVERVIEW P/E fallback. None on miss/no-key/rate-limit."""
    doc = alpha_vantage.get_pe_ratios(ticker)
    if doc is None:
        return None
    ttm = _coerce_pe(doc.get("pe_ttm"))
    fwd = _coerce_pe(doc.get("pe_forward"))
    if ttm is None and fwd is None:
        return None
    return {"pe_ttm": ttm, "pe_forward": fwd, "name": doc.get("name")}


# ---------------------------------------------------------------------------
# ORCHESTRATION (dependency-injected fetchers → offline-testable)
# ---------------------------------------------------------------------------

def fetch_pe_row(ticker: str, label: str, yf_fn=yf_pe, av_fn=av_pe) -> dict | None:
    """Resolve one ticker through the source chain (yfinance → Alpha Vantage).
    Returns a row dict (minus asof_date) or None if every source misses."""
    for source, fn in (("yfinance", yf_fn), ("alpha_vantage", av_fn)):
        got = fn(ticker)
        if got is not None:
            return {
                "ticker":     ticker,
                "name":       (got.get("name") or label),
                "pe_ttm":     got.get("pe_ttm"),
                "pe_forward": got.get("pe_forward"),
                "source":     source,
            }
    return None


def build_snapshot(asof_date: str, tickers=None, yf_fn=yf_pe, av_fn=av_pe) -> list[dict]:
    """Build the full snapshot for ``asof_date``. ``tickers`` is a list of
    (ticker, label) pairs (defaults to MAJOR_INDEX_ETFS). Missing tickers are
    dropped (not written as empty rows)."""
    rows = []
    for ticker, label in (tickers if tickers is not None else MAJOR_INDEX_ETFS):
        row = fetch_pe_row(ticker, label, yf_fn=yf_fn, av_fn=av_fn)
        if row is not None:
            rows.append({"asof_date": asof_date, **row})
    return rows


def upsert_snapshot(rows: list[dict], path: pathlib.Path = _SNAPSHOT_CSV) -> pd.DataFrame:
    """Append/replace rows for their (asof_date, ticker) keys and persist the
    accumulating history. Returns the written frame. No-op (returns the existing
    frame) when ``rows`` is empty, so a total fetch failure never wipes history."""
    existing = (pd.read_csv(path, dtype=str) if path.exists()
                else pd.DataFrame(columns=_COLUMNS))
    if not rows:
        return existing
    new = pd.DataFrame(rows)
    keys = set(zip(new["asof_date"].astype(str), new["ticker"].astype(str)))
    if not existing.empty:
        mask = [ (str(a), str(t)) not in keys
                 for a, t in zip(existing["asof_date"], existing["ticker"]) ]
        existing = existing[mask]
    out = pd.concat([existing, new], ignore_index=True)[_COLUMNS]
    out = out.sort_values(["asof_date", "ticker"]).reset_index(drop=True)
    path.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(path, index=False)
    return out
