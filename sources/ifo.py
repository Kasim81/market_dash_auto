"""
sources/ifo.py
==============
ifo Business Climate (Germany) source module.

The ifo Institute publishes a monthly Excel workbook at ifo.de.  The file
name encodes the release year-month as `gsk-<e|d>-YYYYMM.xlsx` (`e` =
English, `d` = German).

Discovery strategy, in order:
  1. Scrape https://www.ifo.de/en/ifo-time-series with browser-like
     headers; grep for gsk-*.xlsx links.
  2. If the landing page 403s (anti-bot) or returns no matches, fall
     back to direct URL construction: try the canonical `secure/
     timeseries/gsk-d-YYYYMM.xlsx` path and the older `YYYY-MM/gsk-
     e-YYYYMM.xlsx` archive path for the current month and the prior
     three months.

The English workbook stopped being regularly published at some point;
this module now accepts either language and treats German as the
default.  `parse_workbook` reads by positional column so the German
workbook's column order must still match EXCEL_COL_NAMES.

Indicator definitions live in data/macro_library_ifo.csv (series_id is
the Excel column name, `col` is our canonical output column).
"""

from __future__ import annotations

import io
import pathlib
import re
from datetime import date

import pandas as pd
import requests

_LIBRARY_CSV = pathlib.Path(__file__).parent.parent / "data" / "macro_library_ifo.csv"

IFO_BASE    = "https://www.ifo.de"
IFO_LANDING = f"{IFO_BASE}/en/ifo-time-series"

USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)

# Browser-like headers: the ifo landing page has an anti-bot layer that
# 403s a bare UA; a realistic Accept / Accept-Language pair is enough
# to pass the simple checks.
_HTTP_HEADERS = {
    "User-Agent":      USER_AGENT,
    "Accept":          "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9,de;q=0.8",
}

# Match gsk-<e|d>-YYYYMM.xlsx (6 digits).  The `\d{6}` pattern accepts
# both the legacy YYMMDD filenames and the current YYYYMM form.
_HREF_RE = re.compile(
    r'href=[\'"]([^\'"]*gsk-[ed]-\d{6}\.xlsx)[\'"]',
    re.IGNORECASE,
)

# The English workbook's row 9 is the data header; rows 1-8 are titles and
# metadata.  Column A is a "MM/YYYY" label; B-I are the numeric series.
EXCEL_COL_NAMES = [
    "yearmonth",
    "climate_index",
    "situation_index",
    "expectation_index",
    "climate_balance",
    "situation_balance",
    "expectation_balance",
    "uncertainty",
    "economic_expansion",
]


# ---------------------------------------------------------------------------
# LIBRARY LOADER
# ---------------------------------------------------------------------------

def load_library() -> list[dict]:
    """Load ifo indicator definitions from macro_library_ifo.csv."""
    df = pd.read_csv(_LIBRARY_CSV, dtype=str, keep_default_na=False)
    df["sort_key"] = pd.to_numeric(df["sort_key"], errors="coerce").fillna(0)
    df = df.sort_values("sort_key")
    result = []
    for _, row in df.iterrows():
        result.append({
            "source":       "ifo",
            "source_id":    row["series_id"].strip(),  # Excel column name
            "col":          row["col"].strip(),        # our canonical output column
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
            # Legacy alias for existing fetch_macro_ifo callers:
            "series_id":    row["series_id"].strip(),
        })
    return result


# ---------------------------------------------------------------------------
# WORKBOOK DISCOVERY + DOWNLOAD
# ---------------------------------------------------------------------------

def _iter_recent_yyyymm(months_back: int = 3):
    """Yield (YYYY, MM, 'YYYYMM') tuples for the current month and the
    `months_back` preceding months."""
    today = date.today()
    y, m = today.year, today.month
    for _ in range(months_back + 1):
        yield y, m, f"{y:04d}{m:02d}"
        m -= 1
        if m < 1:
            m = 12
            y -= 1


def _try_head(url: str) -> bool:
    """Return True if a HEAD request on `url` returns <400 (or 405 falls
    back to a streamed GET)."""
    try:
        r = requests.head(url, headers=_HTTP_HEADERS, timeout=15, allow_redirects=True)
        if r.status_code < 400:
            return True
        if r.status_code == 405:  # method not allowed; some servers block HEAD
            g = requests.get(url, headers=_HTTP_HEADERS, timeout=15, stream=True)
            g.close()
            return g.status_code == 200
    except requests.exceptions.RequestException:
        return False
    return False


def _candidate_urls():
    """Generate direct workbook URLs for the current + prior 3 months.
    Try the canonical `secure/timeseries/` path first (German, current
    format), then the older `YYYY-MM/` archive path (English, historical)."""
    for y, m, yyyymm in _iter_recent_yyyymm(months_back=3):
        yield f"{IFO_BASE}/sites/default/files/secure/timeseries/gsk-d-{yyyymm}.xlsx"
        yield f"{IFO_BASE}/sites/default/files/{y:04d}-{m:02d}/gsk-e-{yyyymm}.xlsx"


def resolve_workbook_url() -> str:
    """
    Resolve the current ifo Business Climate workbook URL.

    First attempts landing-page scraping (may 403 under anti-bot); on
    failure falls back to direct URL construction using the known path
    conventions and a recent-months window.

    Raises RuntimeError if neither strategy finds a live workbook.
    """
    # Strategy 1: scrape the landing page.
    try:
        resp = requests.get(IFO_LANDING, headers=_HTTP_HEADERS, timeout=30)
        if resp.status_code == 200:
            matches = _HREF_RE.findall(resp.text)
            if matches:
                # Prefer English if still present, otherwise first match.
                href = next(
                    (m for m in matches if "gsk-e-" in m.lower()),
                    matches[0],
                )
                url = href if href.startswith("http") else IFO_BASE + href
                print(f"  [ifo] Landing-page scrape resolved: {url}")
                return url
            print(
                "  [ifo] Landing page returned HTML but no gsk-*.xlsx link; "
                "trying direct URL fallback."
            )
        else:
            print(
                f"  [ifo] Landing page HTTP {resp.status_code}; "
                "trying direct URL fallback."
            )
    except requests.exceptions.RequestException as e:
        print(f"  [ifo] Landing-page scrape raised {type(e).__name__}: {e}")

    # Strategy 2: guess direct URLs for recent months.
    tried = []
    for candidate in _candidate_urls():
        tried.append(candidate)
        if _try_head(candidate):
            print(f"  [ifo] Direct-URL resolve succeeded: {candidate}")
            return candidate

    raise RuntimeError(
        f"Could not resolve ifo workbook URL. Landing page and {len(tried)} "
        f"direct candidates all failed. Last tried: {tried[-1] if tried else '(none)'}"
    )


def download_workbook(url: str) -> bytes:
    """Download the workbook; raises on HTTP error."""
    resp = requests.get(url, headers=_HTTP_HEADERS, timeout=60)
    resp.raise_for_status()
    return resp.content


# ---------------------------------------------------------------------------
# WORKBOOK PARSER
# ---------------------------------------------------------------------------

def parse_workbook(xlsx_bytes: bytes, indicators: list[dict]) -> pd.DataFrame:
    """
    Parse the ifo English workbook into a DataFrame indexed by month-end
    datetime.  Only the columns described in `indicators` are emitted.

    Args:
        xlsx_bytes: the workbook bytes.
        indicators: list of dicts (as returned by load_library()).  Each
            row must carry `series_id` (Excel column name) and `col`
            (output column name).
    """
    df = pd.read_excel(
        io.BytesIO(xlsx_bytes),
        sheet_name=0,
        skiprows=8,
        header=None,
        names=EXCEL_COL_NAMES,
    )
    df = df[df["yearmonth"].notna()].copy()
    df["date"] = pd.to_datetime(
        df["yearmonth"].astype(str), format="%m/%Y", errors="coerce"
    )
    df = df[df["date"].notna()].set_index("date").sort_index()
    # Shift first-of-month → last-of-month to match the period-end convention
    # used by the other sources.
    df.index = df.index + pd.offsets.MonthEnd(0)

    out = pd.DataFrame(index=df.index)
    for indic in indicators:
        out[indic["col"]] = pd.to_numeric(df[indic["series_id"]], errors="coerce")
    # Drop rows where every tracked series is NaN (end-of-file padding).
    return out.dropna(how="all")
