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
            # Workbook layout (new in Stage 2 follow-up): which sheet to
            # read from, and which 1-indexed column holds this series.
            "sheet":        row["sheet"].strip(),
            "excel_col":    int(row["excel_col"]),
            # Legacy alias for any lingering caller:
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
    Parse the ifo workbook.  Each indicator dict specifies a `sheet` name
    and a 1-indexed `excel_col` position; the parser reads strictly by
    position so it doesn't depend on the workbook's German/English
    header strings.

    Workbook layout assumptions (as of the 2026-04 release, confirmed
    against gsk-e-202604.xlsx):
      - Row 1-8: title + merged headers.
      - Row 9:   blank spacer row.
      - Row 10+: data rows.  Column A (1-indexed) is the month label
                 " MM/YYYY" (with a leading space — this is ifo's
                 formatting choice; we strip it before parsing).

    Each sheet is read once, even if multiple indicators pull columns
    from it.  Series that live in different sheets are outer-joined on
    the month-end date index.
    """
    from collections import defaultdict

    xf = pd.ExcelFile(io.BytesIO(xlsx_bytes))
    by_sheet: dict[str, list[dict]] = defaultdict(list)
    for indic in indicators:
        by_sheet[indic["sheet"]].append(indic)

    frames: list[pd.DataFrame] = []
    for sheet_name, sheet_indicators in by_sheet.items():
        if sheet_name not in xf.sheet_names:
            print(f"  [ifo] WARNING: sheet {sheet_name!r} not in workbook; skipping")
            continue

        # skiprows=9 drops the 8 title/header rows plus the blank spacer
        # on row 9.  Row 10 (01/1991 for "Sectors", 01/2005 for "ifo
        # Business Climate") becomes the first row of the DataFrame.
        df = pd.read_excel(xf, sheet_name=sheet_name, skiprows=9, header=None)

        if df.empty or df.shape[1] < 2:
            print(f"  [ifo] WARNING: sheet {sheet_name!r} returned no usable data")
            continue

        # Column A (1-indexed) → 0-indexed first column.  Strings have a
        # leading space (" 01/2005") so .str.strip() before parsing.
        date_raw = df.iloc[:, 0].astype(str).str.strip()
        dates = pd.to_datetime(date_raw, format="%m/%Y", errors="coerce")
        valid = dates.notna()
        df = df.loc[valid].copy()
        df.index = dates.loc[valid] + pd.offsets.MonthEnd(0)

        sheet_out = pd.DataFrame(index=df.index)
        for indic in sheet_indicators:
            col_idx = indic["excel_col"] - 1  # 1-indexed → 0-indexed
            if col_idx >= df.shape[1]:
                print(
                    f"  [ifo] WARNING: column {indic['excel_col']} out of range "
                    f"({df.shape[1]} cols) on sheet {sheet_name!r} for {indic['col']}"
                )
                sheet_out[indic["col"]] = pd.NA
                continue
            sheet_out[indic["col"]] = pd.to_numeric(df.iloc[:, col_idx], errors="coerce")
        frames.append(sheet_out)

    if not frames:
        return pd.DataFrame()

    merged = pd.concat(frames, axis=1).sort_index()
    # A month might appear in more than one sheet (same Industry+Trade
    # headline lives in both sheets); collapse to the first non-null.
    merged = merged.groupby(level=0).first()
    return merged.dropna(how="all")
