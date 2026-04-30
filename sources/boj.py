"""
sources/boj.py
==============
Bank of Japan Time-Series Data Search source module
(stat-search.boj.or.jp).

The BoJ launched a new programmatic API in February 2026 (per the G20
catalogue) exposing ~200,000 series including the BoJ policy rate
trajectory, JGB yields, JPY money market rates, monetary base, Tankan
DI, BoP, flow of funds, and CGPI/SPPI. No registration, no API key,
JSON/CSV.

Indicator definitions live in ``data/macro_library_boj.csv``.

Wired §3.1 Stage D.3 (2026-04-30):
  - As a T2 backup for ``JPN_POLICY_RATE`` (already T1-resolved via
    DB.nomics IMF/IFS in Stage B; BoJ direct is the canonical source
    and gives us a redundant fresh feed).
  - As the primary path for ``JP_PMI1`` (Tankan Large Manufacturers
    DI), which has been "Insufficient Data" since the original Phase D
    rebuild — the au Jibun Bank PMI is S&P Global proprietary; BoJ
    Tankan is the canonical free Japan business-survey signal.

API base / formats: per BoJ docs at
https://www.stat-search.boj.or.jp/info/api_manual_en.pdf
"""

from __future__ import annotations

import io
import pathlib
import time
from datetime import date, datetime

import pandas as pd
import requests


_LIBRARY_CSV = pathlib.Path(__file__).parent.parent / "data" / "macro_library_boj.csv"
BOJ_BASE = "https://www.stat-search.boj.or.jp/ssi/mtshtml"
DEFAULT_HIST_START = "1990-01-01"

# BoJ may apply WAF / anti-bot rules similar to BoE — pre-emptively send a
# browser-like User-Agent so we don't have to chase HTTP 403 in CI.
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/csv,text/plain,application/json,*/*;q=0.8",
    "Accept-Language": "en;q=0.9",
}


# ---------------------------------------------------------------------------
# LIBRARY LOADER
# ---------------------------------------------------------------------------

def load_library() -> list[dict]:
    """Load BoJ Time-Series Data Search indicator definitions."""
    if not _LIBRARY_CSV.exists():
        return []
    df = pd.read_csv(_LIBRARY_CSV, dtype=str, keep_default_na=False)
    df["sort_key"] = pd.to_numeric(df["sort_key"], errors="coerce").fillna(0)
    df = df.sort_values("sort_key")
    result = []
    for _, row in df.iterrows():
        result.append({
            "source":       "BoJ",
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

def fetch_series(
    series_id: str,
    start: str = DEFAULT_HIST_START,
    timeout: int = 30,
    retries: int = 3,
) -> str | None:
    """Fetch a single BoJ series as raw CSV text.

    series_id: BoJ series code, e.g. 'IR01\\'CDABNBP@D' for the policy rate
               or 'TK\\'TKLLDIM@Q' for Tankan Large Manufacturers DI. Note
               the apostrophe in BoJ codes — encode as '%27' if used in URL.
    Returns CSV body (UTF-8) or None on failure.
    """
    # BoJ API endpoint (approx — may need adjustment per the api_manual PDF):
    #   GET /ssi/mtshtml/getSearchData
    # with query string: series=...&format=CSV&start=...
    # Multiple URL shapes are tried defensively given the API is new
    # (launched Feb 2026) and shape conventions may shift.
    candidate_urls = [
        f"{BOJ_BASE}/getSearchData",
        f"{BOJ_BASE}/data",
        BOJ_BASE,
    ]
    params = {
        "series": series_id,
        "format": "CSV",
        "start": start,
    }

    for attempt in range(retries):
        for url in candidate_urls:
            try:
                resp = requests.get(url, params=params, headers=_HEADERS, timeout=timeout)
                if resp.status_code != 200 or not resp.text:
                    if resp.status_code == 404:
                        continue  # try next candidate URL
                    print(f"    [BoJ HTTP {resp.status_code}] {series_id} via {url.rsplit('/', 1)[-1]}")
                    continue
                head = resp.text.lstrip()[:200].lower()
                if head.startswith("<!doctype html") or head.startswith("<html"):
                    print(f"    [BoJ] {url.rsplit('/', 1)[-1]} returned HTML — trying alt")
                    continue
                return resp.text
            except requests.Timeout:
                print(f"    [BoJ timeout] {series_id} via {url.rsplit('/', 1)[-1]}")
                continue
            except requests.RequestException as e:
                print(f"    [BoJ request error] {series_id} via {url.rsplit('/', 1)[-1]}: {e}")
                continue
        wait = 2 ** attempt
        print(f"    [BoJ] all URLs failed for {series_id} — backing off {wait}s")
        time.sleep(wait)

    print(f"    [BoJ FAIL] {series_id} — {retries} attempts × {len(candidate_urls)} URLs exhausted")
    return None


# ---------------------------------------------------------------------------
# CSV PARSING
# ---------------------------------------------------------------------------
# BoJ CSV exports typically include a multi-line header preamble (series
# name, units, source URL) followed by a Date,<series> table. We use the
# same dynamic-header-detection approach as sources/boe.py: scan for the
# first line whose first token is "Date" / "DATE" / "日付".

def parse_csv(text: str, series_id: str) -> list[tuple[date, float]]:
    """Parse BoJ CSV response → list of (date, value) tuples (None values dropped)."""
    obs: list[tuple[date, float]] = []
    if not text or not text.strip():
        return obs

    lines = text.splitlines()
    header_idx = None
    for i, line in enumerate(lines):
        first_token = line.split(",", 1)[0].strip().strip('"').lower()
        if first_token in ("date", "日付", "time"):
            header_idx = i
            break
    if header_idx is None:
        print(f"    [BoJ] no Date header row found in {series_id} response "
              f"(first line: {lines[0][:80] if lines else '<empty>'!r})")
        return obs

    try:
        df = pd.read_csv(io.StringIO(text), skiprows=header_idx)
    except Exception as e:
        print(f"    [BoJ] CSV parse failed for {series_id}: {e}")
        return obs

    if df.empty or df.shape[1] < 2:
        return obs

    # Column 0 = date; column 1 = value (BoJ exports usually one series per CSV)
    date_col = df.columns[0]
    val_col = df.columns[1]

    for _, row in df.iterrows():
        d_str = str(row[date_col]).strip().strip('"')
        v_raw = row[val_col]
        if pd.isna(v_raw):
            continue
        v_str = str(v_raw).strip().strip('"')
        if not d_str or not v_str or v_str.lower() in ("nan", "n/a", "", "-"):
            continue
        d = _parse_period(d_str)
        if d is None:
            continue
        try:
            v = float(v_str)
        except ValueError:
            continue
        obs.append((d, v))

    return obs


def _parse_period(p: str) -> date | None:
    """Parse BoJ period strings — daily, monthly, or quarterly."""
    p = p.strip()
    if not p:
        return None
    # Daily ISO
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y.%m.%d"):
        try:
            return datetime.strptime(p, fmt).date()
        except ValueError:
            continue
    # Monthly ISO / slash / dot
    for fmt in ("%Y-%m", "%Y/%m", "%Y.%m"):
        try:
            return datetime.strptime(p + "-01" if "-" in p else p, fmt).date()
        except ValueError:
            continue
    # Quarterly: YYYY/Q? or YYYY-Q? or YYYYQ?
    for sep in ("/Q", "-Q", "Q"):
        if sep in p:
            try:
                yr_part, q_part = p.split(sep, 1)
                yr = int(yr_part.strip())
                q = int(q_part.strip())
                month = q * 3
                return date(yr, month, 1)
            except (ValueError, IndexError):
                pass
    # Year only
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
