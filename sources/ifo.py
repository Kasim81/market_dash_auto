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

# Browser-like headers for the landing-page scrape.  The ifo anti-bot
# layer serves stripped-down HTML (or challenge pages) to bare UAs.
_HTTP_HEADERS = {
    "User-Agent":      USER_AGENT,
    "Accept":          "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9,de;q=0.8",
    "Accept-Encoding": "gzip, deflate, br",
    "DNT":             "1",
    "Upgrade-Insecure-Requests": "1",
}

# Separate headers for the workbook download — declare we want the xlsx
# MIME type and set a Referer so the request looks like it came from the
# landing page.  Some anti-bot layers check Referer.
_XLSX_HEADERS = {
    "User-Agent":      USER_AGENT,
    "Accept":          (
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet,"
        "application/vnd.ms-excel,application/octet-stream,*/*;q=0.8"
    ),
    "Accept-Language": "en-US,en;q=0.9,de;q=0.8",
    "Accept-Encoding": "gzip, deflate, br",
    "Referer":         IFO_LANDING,
}

# First bytes of a valid .xlsx (ZIP archive) file.
_XLSX_MAGIC = b"PK\x03\x04"

# Match gsk-<e|d>-YYYYMM.xlsx (6 digits).
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


def _candidate_urls():
    """Generate direct workbook URLs for the current + prior 3 months.
    Try the canonical `secure/timeseries/` path first (German, current
    format), then the older `YYYY-MM/` archive path (English, historical)."""
    for y, m, yyyymm in _iter_recent_yyyymm(months_back=3):
        yield f"{IFO_BASE}/sites/default/files/secure/timeseries/gsk-d-{yyyymm}.xlsx"
        yield f"{IFO_BASE}/sites/default/files/{y:04d}-{m:02d}/gsk-e-{yyyymm}.xlsx"


def _try_download_xlsx(session: requests.Session, url: str) -> bytes | None:
    """
    GET `url` through `session` and return the body only if it looks like
    a real xlsx (starts with PK\\x03\\x04).  Returns None otherwise —
    anti-bot challenges and HTML error pages both fail this check.
    """
    try:
        r = session.get(url, headers=_XLSX_HEADERS, timeout=60)
    except requests.exceptions.RequestException as e:
        print(f"  [ifo] GET {url} raised {type(e).__name__}: {e}")
        return None
    if r.status_code != 200:
        print(f"  [ifo] GET {url} HTTP {r.status_code}; skipping")
        return None
    if not r.content.startswith(_XLSX_MAGIC):
        ct = r.headers.get("Content-Type", "")
        head = r.content[:120].replace(b"\n", b" ")
        print(
            f"  [ifo] GET {url} returned {len(r.content)} bytes with "
            f"Content-Type={ct!r} but body doesn't start with xlsx magic. "
            f"First 120 bytes: {head!r}"
        )
        return None
    return r.content


def resolve_workbook() -> tuple[str, bytes]:
    """
    Find AND download the ifo workbook in a single pass through a shared
    requests.Session.  Returns (url, xlsx_bytes) on success.

    Discovery order:
      1. Scrape the landing page (sets session cookies).  For every
         gsk-*.xlsx link returned, try to download; keep the first one
         whose body is a real xlsx.
      2. Direct URL construction for the current + prior 3 months.

    Raises RuntimeError if nothing succeeds.
    """
    session = requests.Session()
    session.headers.update(_HTTP_HEADERS)
    tried: list[str] = []

    # Strategy 1: hit landing page (sets cookies) and scrape link(s).
    try:
        resp = session.get(IFO_LANDING, timeout=30)
        if resp.status_code == 200:
            matches = _HREF_RE.findall(resp.text)
            # Prefer English when it's present, else keep the encounter order.
            ordered = sorted(set(matches), key=lambda m: "gsk-e-" not in m.lower())
            for href in ordered:
                url = href if href.startswith("http") else IFO_BASE + href
                tried.append(url)
                content = _try_download_xlsx(session, url)
                if content is not None:
                    print(f"  [ifo] Landing-page scrape resolved + validated: {url}")
                    return url, content
            if not matches:
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

    # Strategy 2: direct URL construction, validated per candidate.
    for candidate in _candidate_urls():
        tried.append(candidate)
        content = _try_download_xlsx(session, candidate)
        if content is not None:
            print(f"  [ifo] Direct-URL resolve + validated: {candidate}")
            return candidate, content

    raise RuntimeError(
        f"Could not resolve a valid ifo workbook.  Tried {len(tried)} URL(s); "
        f"landing-page scrape either returned no link or served an anti-bot "
        f"challenge page for every candidate.  Last tried: "
        f"{tried[-1] if tried else '(none)'}"
    )


def resolve_workbook_url() -> str:
    """Backward-compatible shim — callers that don't need the bytes."""
    url, _ = resolve_workbook()
    return url


def download_workbook(url: str) -> bytes:
    """
    Download the workbook from `url` and verify it's a real xlsx.
    Kept for callers that already have a URL in hand; new code should
    prefer `resolve_workbook()` which combines both steps.
    """
    session = requests.Session()
    session.headers.update(_HTTP_HEADERS)
    content = _try_download_xlsx(session, url)
    if content is None:
        raise RuntimeError(f"Download of {url} did not return a valid xlsx")
    return content


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

    xf = pd.ExcelFile(io.BytesIO(xlsx_bytes), engine="openpyxl")
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
        df = pd.read_excel(xf, sheet_name=sheet_name, skiprows=9, header=None, engine="openpyxl")

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
