"""
sources/ifo.py
==============
ifo Business Climate (Germany) source module.

The ifo Institute publishes a monthly Excel workbook at ifo.de.  The file
name rotates monthly (gsk-e-YYMMDD.xlsx), so we scrape the landing page to
discover the current URL, download the workbook, and parse the English
sheet into a month-end-indexed DataFrame.

Indicator definitions live in data/macro_library_ifo.csv (series_id is
the Excel column name, `col` is our canonical output column).
"""

from __future__ import annotations

import io
import pathlib
import re

import pandas as pd
import requests

_LIBRARY_CSV = pathlib.Path(__file__).parent.parent / "data" / "macro_library_ifo.csv"

IFO_BASE    = "https://www.ifo.de"
IFO_LANDING = f"{IFO_BASE}/en/ifo-time-series"

USER_AGENT = (
    "Mozilla/5.0 (compatible; market_dash_auto/1.0; "
    "+https://github.com/Kasim81/market_dash_auto)"
)

# The ifo landing page links to a file named gsk-<e|d>-YYMMDD.xlsx; the
# prefix flips between English ("e") and German ("d") variants.
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

def resolve_workbook_url() -> str:
    """Scrape ifo.de for the current gsk-*.xlsx URL.

    English (gsk-e-*) is preferred; falls back to the German (gsk-d-*)
    variant if no English link exists.  Raises RuntimeError if neither is
    found — the landing-page layout probably changed.
    """
    resp = requests.get(IFO_LANDING, headers={"User-Agent": USER_AGENT}, timeout=30)
    resp.raise_for_status()
    matches = _HREF_RE.findall(resp.text)
    if not matches:
        raise RuntimeError(
            f"No gsk-*.xlsx link found on {IFO_LANDING}; "
            "ifo page layout may have changed"
        )
    href = next((m for m in matches if "gsk-e-" in m.lower()), matches[0])
    return href if href.startswith("http") else IFO_BASE + href


def download_workbook(url: str) -> bytes:
    """Download the workbook; raises on HTTP error."""
    resp = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=60)
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
