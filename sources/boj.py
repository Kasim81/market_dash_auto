"""
sources/boj.py
==============
Bank of Japan Time-Series Data Search source module
(stat-search.boj.or.jp).

The BoJ launched a programmatic API in February 2026 (per the G20
catalogue). Free, no API key, returns JSON or CSV.

Documented API spec (from manuals/BOJ_api_manual_en.pdf, Feb 2026):

  Endpoint:  https://www.stat-search.boj.or.jp/api/v1/getDataCode?<params>
  Required:  db=<DB Name>           e.g. FM01 (call rate), CO (Tankan), ...
             code=<series_code>     e.g. STRDCLUCON  (apostrophe-prefixed
                                    DB-code shown in the search screen
                                    must NOT be passed; strip the prefix)
  Optional:  format=json|csv        default json
             lang=en|jp             default jp
             startDate=YYYYMM       (or YYYY for annual, YYYYQQ for quarterly)
             endDate=YYYYMM
             startPosition=N        for pagination

  Limits per request:
    - 250 series codes per request
    - 60,000 data points per request (codes × periods)
    - Pagination via NEXTPOSITION in response → STARTPOSITION in next call

  Series-code format note:
    The interactive search screen presents codes as "<DB>'<series_code>"
    (e.g. "FM01'STRDCLUCON"). The API wants those split: db=FM01,
    code=STRDCLUCON. Our registry stores them in the search-screen format
    (DB'series) for human readability; we split inside fetch_series.

Indicator definitions live in ``data/macro_library_boj.csv``.

Wired §3.1 Stage D.3 (2026-04-30):
  - As a T2 backup for ``JPN_POLICY_RATE`` via FM01'STRDCLUCON
    (Daily Uncollateralized Overnight Call Rate; T1 = DB.nomics IMF IFS).
  - As the future primary path for ``JP_PMI1`` (Tankan Large Manufacturers
    DI) once the canonical CO-database series code is identified.
"""

from __future__ import annotations

import io
import pathlib
import time
from datetime import date, datetime

import pandas as pd
import requests


_LIBRARY_CSV = pathlib.Path(__file__).parent.parent / "data" / "macro_library_boj.csv"
BOJ_BASE = "https://www.stat-search.boj.or.jp/api/v1/getDataCode"
BOJ_META = "https://www.stat-search.boj.or.jp/api/v1/getMetadata"
DEFAULT_HIST_START = "199001"   # YYYYMM per BoJ API spec

# BoJ may apply WAF rules — pre-emptively send a browser-like User-Agent.
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/csv,application/json,*/*;q=0.8",
    "Accept-Language": "en;q=0.9",
    "Accept-Encoding": "gzip",   # BoJ docs note gzip support
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


def _split_series_id(series_id: str) -> tuple[str, str]:
    """Split a search-screen-format BoJ code 'DB\\'series' into (db, code)."""
    s = series_id.strip()
    if "'" in s:
        db, code = s.split("'", 1)
        return db.strip(), code.strip()
    return "", s


# ---------------------------------------------------------------------------
# SERIES FETCH
# ---------------------------------------------------------------------------

def fetch_series(
    series_id: str,
    start: str = DEFAULT_HIST_START,
    timeout: int = 30,
    retries: int = 3,
) -> str | None:
    """Fetch a single BoJ series via getDataCode.

    series_id: search-screen format e.g. "FM01'STRDCLUCON". The DB prefix
               + apostrophe is split out; the API takes db + code separately.
    Returns response body (CSV, possibly UTF-8) or None on failure.
    """
    db, code = _split_series_id(series_id)
    if not db or not code:
        print(f"    [BoJ] invalid series_id {series_id!r} (expected 'DB\\'CODE')")
        return None

    params = {
        "format": "csv",
        "lang": "en",
        "db": db,
        "code": code,
        "startDate": start,
    }

    for attempt in range(retries):
        try:
            resp = requests.get(BOJ_BASE, params=params, headers=_HEADERS, timeout=timeout)
            if resp.status_code == 200 and resp.text.strip():
                head = resp.text.lstrip()[:200].lower()
                if head.startswith("<!doctype html") or head.startswith("<html"):
                    print(f"    [BoJ] {series_id} returned HTML (not CSV) — skipping")
                    return None
                return resp.text
            if 500 <= resp.status_code < 600:
                wait = 2 ** attempt
                print(f"    [BoJ HTTP {resp.status_code}] {series_id} — backing off {wait}s")
                time.sleep(wait)
                continue
            print(f"    [BoJ HTTP {resp.status_code}] {series_id} — skipping")
            return None
        except requests.Timeout:
            wait = 2 ** attempt
            print(f"    [BoJ timeout] {series_id} — backing off {wait}s")
            time.sleep(wait)
        except requests.RequestException as e:
            print(f"    [BoJ request error] {series_id}: {e} — skipping")
            return None

    print(f"    [BoJ FAIL] {series_id} — {retries} attempts exhausted")
    return None


# ---------------------------------------------------------------------------
# CSV PARSING
# ---------------------------------------------------------------------------
# BoJ getDataCode CSV (lang=en, format=csv) — verified shape from a live
# fetch (May 2026):
#
#   STATUS,200
#   MESSAGEID,M181000I
#   MESSAGE,Successfully completed
#   DATE,2026-05-01T05:17:59.466+09:00
#   PARAMETER,FORMAT,CSV
#   PARAMETER,LANG,EN
#   PARAMETER,DB,FM01
#   PARAMETER,STARTDATE,199001
#   PARAMETER,ENDDATE,
#   PARAMETER,STARTPOSITION,
#   NEXTPOSITION,
#   SERIES_CODE,NAME_OF_TIME_SERIES,UNIT,FREQUENCY,CATEGORY,LAST_UPDATE,SURVEY_DATES,VALUES
#   STRDCLUCON,"Call Rate, Uncollateralized Overnight, Average (Daily)",percent per annum,DAILY,Call Rate,20260430,19900101,
#   ...
#
# Each observation is a single CSV row with 8 columns; columns 0-5 echo
# the series metadata on every row, column 6 (SURVEY_DATES) is the date
# in YYYYMMDD format, column 7 (VALUES) is the observation. We locate
# the header row by matching first-token == "SERIES_CODE" and then parse
# from there.

def parse_csv(text: str, series_id: str) -> list[tuple[date, float]]:
    """Parse BoJ getDataCode CSV → list of (date, value) tuples (None values dropped)."""
    obs: list[tuple[date, float]] = []
    if not text or not text.strip():
        return obs

    lines = text.splitlines()
    header_idx = None
    for i, line in enumerate(lines):
        first_token = line.split(",", 1)[0].strip().strip('"')
        if first_token == "SERIES_CODE":
            header_idx = i
            break
    if header_idx is None:
        print(f"    [BoJ] no SERIES_CODE header row found for {series_id} "
              f"(first line: {lines[0][:80] if lines else '<empty>'!r})")
        for i, line in enumerate(lines[:15]):
            print(f"      line {i}: {line[:120]!r}")
        return obs

    try:
        df = pd.read_csv(io.StringIO(text), skiprows=header_idx)
    except Exception as e:
        print(f"    [BoJ] CSV parse failed for {series_id}: {e}")
        for i, line in enumerate(lines[:15]):
            print(f"      line {i}: {line[:120]!r}")
        return obs

    # Required columns from the documented BoJ schema.
    if "SURVEY_DATES" not in df.columns or "VALUES" not in df.columns:
        print(f"    [BoJ] unexpected schema for {series_id}: {list(df.columns)[:8]}")
        return obs

    for _, row in df.iterrows():
        d_raw = row["SURVEY_DATES"]
        v_raw = row["VALUES"]
        if pd.isna(d_raw) or pd.isna(v_raw):
            continue
        d_str = str(d_raw).strip()
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
    """Parse BoJ SURVEY_DATES strings.

    The most common form is YYYYMMDD (daily). Quarterly tables often use
    YYYYQQ (e.g. 202003 for Q3 2020) and monthly tables YYYYMM. Half-year
    encoded as YYYYHN. Falls through to ISO/slash variants for safety.
    """
    p = str(p).strip()
    if not p:
        return None
    # YYYYMMDD daily (8 digits)
    if p.isdigit() and len(p) == 8:
        try:
            return datetime.strptime(p, "%Y%m%d").date()
        except ValueError:
            pass
    # YYYYMM monthly (6 digits) or YYYYQQ quarterly (6 digits where last two
    # are 03/06/09/12 — quarter-end month). Treat ambiguously: parse as
    # month-start; for quarterly callers, this still gives a unique date
    # per quarter.
    if p.isdigit() and len(p) == 6:
        try:
            return datetime.strptime(p + "01", "%Y%m%d").date()
        except ValueError:
            pass
    # YYYYHN half-year (5 digits — e.g. 20251 for H1)
    if len(p) == 5 and p[:4].isdigit() and p[4] in ("1", "2"):
        try:
            yr = int(p[:4])
            h = int(p[4])
            return date(yr, 6 if h == 1 else 12, 30 if h == 1 else 31)
        except ValueError:
            pass
    # ISO date / slash / quarter forms
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y.%m.%d", "%Y-%m", "%Y/%m"):
        try:
            return datetime.strptime(p, fmt).date()
        except ValueError:
            continue
    for sep in ("/Q", "-Q", "Q"):
        if sep in p:
            try:
                yr_part, q_part = p.split(sep, 1)
                yr = int(yr_part.strip())
                q = int(q_part.strip()[0])
                return date(yr, q * 3, 1)
            except (ValueError, IndexError):
                pass
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
