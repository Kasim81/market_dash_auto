"""
sources/sec_edgar.py
====================
SEC EDGAR ``companyfacts`` source module — multi-year company fundamentals
(revenue and diluted-EPS history) for US filers, straight from the SEC's
structured XBRL financial-statement API.

    https://www.sec.gov/files/company_tickers.json          (ticker → CIK map)
    https://data.sec.gov/api/xbrl/companyfacts/CIK{cik:010d}.json

Keyless and free — EDGAR requires no API key. The ONLY access requirement is
the SEC's fair-access policy: every request MUST carry a descriptive
``User-Agent`` header naming the caller and a contact email, and traffic must
stay under 10 requests/second. Both are enforced here (``_HEADERS`` +
``_throttle()``). Without these the SEC returns HTTP 403. Same graceful-no-op
posture as sources/alpha_vantage.py and sources/bdf.py: an empty/absent
library, an unreachable endpoint, or a missing tag all degrade to an empty
result rather than raising.

Why a dedicated equity-fundamentals output (data/equity_fundamentals.csv) and
NOT the unified macro_economic feed: these are per-company financial-statement
facts on a fiscal-quarter / fiscal-year cadence (10-Q / 10-K), not a
Friday-spine macro time series, so they live in their own long/tidy table
keyed by (ticker, metric, period_end, period_type). The coordinator that
writes that CSV lives in fetch_data.py, keeping this module side-effect-free
(library loader + fetchers only) like every other sources/ submodule.

Library: data/macro_library_sec_edgar.csv. Columns:
    ticker     — US-listed symbol (e.g. NVDA)
    cik        — optional; resolved from company_tickers.json when blank
    metric     — ``revenue`` or ``eps``
    gaap_tags  — pipe-separated us-gaap tag priority list, e.g.
                 ``RevenueFromContractWithCustomerExcludingAssessedTax|Revenues|SalesRevenueNet``
    col        — short column id (e.g. NVDA_REVENUE)
    name       — human-readable label (e.g. "NVIDIA — Revenue")
    sort_key   — numeric display order

Tag handling: companies switch us-gaap concepts over time (e.g. SalesRevenueNet
pre-ASC-606, RevenueFromContractWithCustomerExcludingAssessedTax after), so we
UNION every listed tag to recover the longest history, but where the same
fiscal period is reported under more than one tag the higher-priority tag wins.
Within a single tag, a restated period (same period reported in a later filing)
keeps the LATEST-FILED value.

Period typing: each XBRL duration fact carries start+end dates. We classify by
duration — ~3 months → quarterly (``Q``), ~12 months → annual (``A``) — and drop
the 6-/9-month year-to-date cumulative stubs that are neither.

Wired 2026-06-15 — module + library + data/equity_fundamentals.csv writer in
fetch_data.py. The library load is a no-op when the CSV is empty, matching the
sources/alpha_vantage.py precedent.
"""

from __future__ import annotations

import json
import os
import pathlib
import time
from datetime import date, datetime

import pandas as pd

from sources.base import fetch_with_backoff

_DATA_DIR = pathlib.Path(__file__).parent.parent / "data"
_LIBRARY_CSV = _DATA_DIR / "macro_library_sec_edgar.csv"
_CACHE_DIR = _DATA_DIR / ".sec_edgar_cache"
_TICKERS_CACHE = _CACHE_DIR / "company_tickers.json"

TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
COMPANYFACTS_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik:010d}.json"

SOURCE_NAME = "SEC EDGAR"

# MANDATORY (SEC fair-access): a descriptive User-Agent naming the caller and a
# reachable contact email. The SEC 403s requests without it. Override the
# contact via the SEC_EDGAR_CONTACT env var; the default is the repo owner.
_CONTACT = os.environ.get("SEC_EDGAR_CONTACT", "kasimzafar@gmail.com").strip() \
    or "kasimzafar@gmail.com"
_HEADERS = {
    "User-Agent": f"market_dash_auto/1.0 ({_CONTACT})",
    "Accept": "application/json",
    "Accept-Encoding": "gzip, deflate",
}

# Fair-access throttle. The SEC caps traffic at 10 requests/second; we keep a
# comfortable >=0.15s gap between any two EDGAR calls (process-wide). The daily
# library is a dozen tickers so this is a formality, but it guarantees we never
# trip the limit regardless of how many rows the library grows to.
_MIN_INTERVAL = 0.15
_last_request_ts: float = 0.0

# Day-of-the-cache lifetime for company_tickers.json — the map changes rarely
# (new listings / symbol changes), so a 7-day disk cache avoids re-fetching it
# on every run while still picking up additions within a week.
_TICKERS_TTL_SECONDS = 7 * 24 * 3600

# Duration windows (in days) used to classify a fiscal period as quarterly or
# annual. The bands are deliberately wide to tolerate 13-week fiscal quarters,
# 52/53-week fiscal years, and a few days of filing-calendar drift.
_Q_MIN, _Q_MAX = 60, 100
_A_MIN, _A_MAX = 330, 400

# Process-level cache of the parsed ticker→CIK map (read once, resolve many).
_TICKER_MAP_CACHE: dict[str, int] | None = None


# ---------------------------------------------------------------------------
# LIBRARY LOADER
# ---------------------------------------------------------------------------

def load_library() -> list[dict]:
    """Load SEC EDGAR fundamentals definitions from
    macro_library_sec_edgar.csv.

    Returns [] when the library is empty/absent (graceful no-op — same posture
    as sources/alpha_vantage.py). Each returned dict carries:
        source, ticker, cik (str, '' if to-resolve), metric ('revenue'|'eps'),
        gaap_tags (list[str], priority order), col, name, sort_key (float).
    Rows with an unknown metric or no gaap_tags are skipped with a warning."""
    if not _LIBRARY_CSV.exists():
        return []
    df = pd.read_csv(_LIBRARY_CSV, dtype=str, keep_default_na=False)
    if df.empty:
        return []
    df["sort_key"] = pd.to_numeric(df["sort_key"], errors="coerce").fillna(0)
    df = df.sort_values("sort_key")
    result: list[dict] = []
    for _, row in df.iterrows():
        metric = row["metric"].strip().lower()
        if metric not in ("revenue", "eps"):
            print(f"    [SEC EDGAR] skipping row with bad metric {metric!r} "
                  f"(ticker={row.get('ticker', '')!r})")
            continue
        gaap_tags = [t.strip() for t in row["gaap_tags"].split("|") if t.strip()]
        if not gaap_tags:
            print(f"    [SEC EDGAR] skipping {row.get('ticker', '')!r}/{metric} "
                  f"— no gaap_tags")
            continue
        result.append({
            "source":    SOURCE_NAME,
            "ticker":    row["ticker"].strip().upper(),
            "cik":       row.get("cik", "").strip(),
            "metric":    metric,
            "gaap_tags": gaap_tags,
            "col":       row["col"].strip(),
            "name":      row["name"].strip(),
            "sort_key":  float(row["sort_key"]),
        })
    return result


# ---------------------------------------------------------------------------
# HTTP (fair-access throttled, base.fetch_with_backoff for retries)
# ---------------------------------------------------------------------------

def _throttle() -> None:
    """Block until at least _MIN_INTERVAL has elapsed since the last EDGAR
    request, keeping process-wide traffic comfortably under the SEC's
    10 req/s fair-access ceiling."""
    global _last_request_ts
    wait = _MIN_INTERVAL - (time.monotonic() - _last_request_ts)
    if wait > 0:
        time.sleep(wait)
    _last_request_ts = time.monotonic()


def _get_json(url: str, label: str, timeout: int = 60) -> dict | None:
    """Throttled GET → parsed JSON, with the mandatory fair-access headers and
    base.fetch_with_backoff retry/backoff on 429/5xx. Returns None on any
    failure (including the sandbox-egress 403 and a non-JSON body)."""
    _throttle()
    try:
        doc = fetch_with_backoff(
            url, label=label, headers=_HEADERS, timeout=timeout, retries=4
        )
    except Exception as e:  # e.g. JSONDecodeError on a 200 HTML body
        print(f"    [SEC EDGAR] {label}: fetch raised {type(e).__name__}: {e}")
        return None
    if doc is None:
        return None
    if not isinstance(doc, dict):
        print(f"    [SEC EDGAR] {label}: unexpected payload type {type(doc).__name__}")
        return None
    return doc


# ---------------------------------------------------------------------------
# TICKER → CIK RESOLUTION
# ---------------------------------------------------------------------------

def _load_ticker_map() -> dict[str, int] | None:
    """Return the {TICKER: cik_int} map from company_tickers.json.

    Cached process-wide and on disk (data/.sec_edgar_cache/, gitignored) with a
    7-day TTL. Returns None only when the map is neither cached nor fetchable."""
    global _TICKER_MAP_CACHE
    if _TICKER_MAP_CACHE is not None:
        return _TICKER_MAP_CACHE

    raw = _read_tickers_cache()
    if raw is None:
        raw = _get_json(TICKERS_URL, "company_tickers", timeout=30)
        if raw is not None:
            _write_tickers_cache(raw)
    if raw is None:
        return None

    # company_tickers.json is keyed by row index: {"0": {"cik_str":.., "ticker":.., "title":..}, ...}
    mapping: dict[str, int] = {}
    for rec in raw.values():
        try:
            tk = str(rec["ticker"]).strip().upper()
            cik = int(rec["cik_str"])
        except (KeyError, TypeError, ValueError):
            continue
        if tk:
            mapping.setdefault(tk, cik)
    if not mapping:
        print("    [SEC EDGAR] company_tickers.json parsed but produced no entries")
        return None
    _TICKER_MAP_CACHE = mapping
    return mapping


def _read_tickers_cache() -> dict | None:
    """Read the on-disk company_tickers.json cache if present and fresh."""
    try:
        if not _TICKERS_CACHE.exists():
            return None
        age = time.time() - _TICKERS_CACHE.stat().st_mtime
        if age > _TICKERS_TTL_SECONDS:
            return None
        with _TICKERS_CACHE.open(encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError) as e:
        print(f"    [SEC EDGAR] ticker cache read failed ({e}) — will refetch")
        return None


def _write_tickers_cache(raw: dict) -> None:
    """Persist company_tickers.json to the local cache (best-effort)."""
    try:
        _CACHE_DIR.mkdir(parents=True, exist_ok=True)
        with _TICKERS_CACHE.open("w", encoding="utf-8") as f:
            json.dump(raw, f)
    except OSError as e:
        print(f"    [SEC EDGAR] ticker cache write failed ({e}) — continuing")


def resolve_cik(ticker: str) -> int | None:
    """Resolve a ticker symbol to its integer CIK via company_tickers.json.

    Returns None when the map is unavailable or the ticker is not US-listed in
    EDGAR (e.g. a foreign private issuer that files 20-F under a different
    symbol, or a non-US name out of EDGAR scope)."""
    ticker = (ticker or "").strip().upper()
    if not ticker:
        return None
    mapping = _load_ticker_map()
    if mapping is None:
        return None
    cik = mapping.get(ticker)
    if cik is None:
        print(f"    [SEC EDGAR] ticker {ticker!r} not found in company_tickers.json "
              f"(not a US filer / symbol mismatch?)")
    return cik


# ---------------------------------------------------------------------------
# COMPANYFACTS FETCH
# ---------------------------------------------------------------------------

def fetch_companyfacts(cik: int) -> dict | None:
    """Fetch the full companyfacts document for an integer CIK, or None."""
    url = COMPANYFACTS_URL.format(cik=int(cik))
    return _get_json(url, f"companyfacts/CIK{int(cik):010d}", timeout=60)


# ---------------------------------------------------------------------------
# FACT EXTRACTION
# ---------------------------------------------------------------------------

def _parse_iso(d: str | None) -> date | None:
    if not d:
        return None
    try:
        return datetime.strptime(d, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return None


def _classify_period(start: date | None, end: date | None) -> str | None:
    """Classify a duration fact as 'Q' (~quarter) or 'A' (~year) by its length,
    or None for YTD 6-/9-month cumulative stubs and instant facts."""
    if start is None or end is None:
        return None
    days = (end - start).days
    if _Q_MIN <= days <= _Q_MAX:
        return "Q"
    if _A_MIN <= days <= _A_MAX:
        return "A"
    return None


def extract_metric(facts: dict, gaap_tags: list[str]) -> list[dict]:
    """Extract quarterly + annual points for one metric from a companyfacts doc.

    ``gaap_tags`` is the priority-ordered us-gaap concept list. Every tag is
    unioned to recover the longest history; where a fiscal period appears under
    more than one tag the higher-priority (earlier-listed) tag wins, and within
    a tag a restated period keeps the latest-filed value.

    Returns a list of dicts: period_end (date), period_type ('Q'|'A'),
    value (float), unit (str), fy (str), fp (str), form (str). Empty when the
    document carries none of the tags."""
    gaap = (facts.get("facts", {}) or {}).get("us-gaap", {}) or {}

    # best[(period_type, period_end)] = (tag_priority, filed_date, point_dict)
    best: dict[tuple[str, date], tuple[int, date, dict]] = {}

    for priority, tag in enumerate(gaap_tags):
        concept = gaap.get(tag)
        if not concept:
            continue
        units = concept.get("units", {}) or {}
        for unit_name, points in units.items():
            for pt in points or []:
                start = _parse_iso(pt.get("start"))
                end = _parse_iso(pt.get("end"))
                ptype = _classify_period(start, end)
                if ptype is None or end is None:
                    continue
                val = pt.get("val")
                if val is None:
                    continue
                try:
                    val = float(val)
                except (TypeError, ValueError):
                    continue
                filed = _parse_iso(pt.get("filed")) or date.min
                key = (ptype, end)
                row = {
                    "period_end":  end,
                    "period_type": ptype,
                    "value":       val,
                    "unit":        unit_name,
                    "fy":          str(pt.get("fy") or "").strip(),
                    "fp":          str(pt.get("fp") or "").strip(),
                    "form":        str(pt.get("form") or "").strip(),
                }
                prev = best.get(key)
                # Lower priority index wins; within the same tag, tie-break to
                # the later filing (restatement → latest-filed value).
                if (prev is None
                        or priority < prev[0]
                        or (priority == prev[0] and filed > prev[1])):
                    best[key] = (priority, filed, row)

    rows = [v[2] for v in best.values()]
    rows.sort(key=lambda r: (r["period_end"], r["period_type"]))
    return rows


# ---------------------------------------------------------------------------
# HIGH-LEVEL: TIDY DATAFRAME BUILDER
# ---------------------------------------------------------------------------

def build_fundamentals_df(rows: list[dict] | None = None) -> pd.DataFrame:
    """Materialise the long/tidy equity-fundamentals table for the library.

    ``rows`` defaults to load_library(). One companyfacts fetch per distinct
    CIK (cached within the call) feeds every metric for that company. Returns a
    DataFrame with columns:
        ticker, metric, period_end, period_type, value, unit, fy, fp, form,
        source, retrieved
    Empty (with the right columns) when the library is empty or EDGAR is
    unreachable — a graceful no-op the caller can merge as a zero-row update."""
    cols = ["ticker", "metric", "period_end", "period_type", "value", "unit",
            "fy", "fp", "form", "source", "retrieved"]
    if rows is None:
        rows = load_library()
    if not rows:
        return pd.DataFrame(columns=cols)

    retrieved = datetime.utcnow().strftime("%Y-%m-%d")
    facts_cache: dict[int, dict | None] = {}
    out_rows: list[dict] = []

    for row in rows:
        ticker = row["ticker"]
        cik = _resolve_row_cik(row)
        if cik is None:
            continue
        if cik not in facts_cache:
            facts_cache[cik] = fetch_companyfacts(cik)
        facts = facts_cache[cik]
        if facts is None:
            continue
        points = extract_metric(facts, row["gaap_tags"])
        if not points:
            print(f"    [SEC EDGAR] {ticker}/{row['metric']}: no points for tags "
                  f"{row['gaap_tags']}")
            continue
        for pt in points:
            out_rows.append({
                "ticker":      ticker,
                "metric":      row["metric"],
                "period_end":  pt["period_end"].strftime("%Y-%m-%d"),
                "period_type": pt["period_type"],
                "value":       pt["value"],
                "unit":        pt["unit"],
                "fy":          pt["fy"],
                "fp":          pt["fp"],
                "form":        pt["form"],
                "source":      SOURCE_NAME,
                "retrieved":   retrieved,
            })
        print(f"    [SEC EDGAR] {ticker}/{row['metric']}: {len(points)} points "
              f"(CIK {cik})")

    if not out_rows:
        return pd.DataFrame(columns=cols)
    df = pd.DataFrame(out_rows, columns=cols)
    return df.sort_values(
        ["ticker", "metric", "period_end", "period_type"]
    ).reset_index(drop=True)


def _resolve_row_cik(row: dict) -> int | None:
    """Resolve a library row's CIK: use the prefilled value if present,
    otherwise resolve the ticker via company_tickers.json."""
    cik_str = (row.get("cik") or "").strip()
    if cik_str:
        try:
            return int(cik_str)
        except ValueError:
            print(f"    [SEC EDGAR] bad cik {cik_str!r} for {row['ticker']} "
                  f"— resolving from ticker")
    return resolve_cik(row["ticker"])
