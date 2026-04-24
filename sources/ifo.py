"""
sources/ifo.py
==============
ifo Business Climate (Germany) source module.

The ifo Institute publishes a monthly Excel workbook at ifo.de.  The file
name rotates monthly (gsk-e-YYMMDD.xlsx), so we scrape the landing page to
discover the current URL, download the workbook, and parse the English
sheet into a month-end-indexed DataFrame.

Indicator metadata currently lives in the coordinator's COLUMNS tuple.
The audit's H1 item will migrate it to data/macro_library_ifo.csv in
Stage 2; the parse_workbook() function already takes the column spec as
a parameter so that migration won't change this file.
"""

from __future__ import annotations

import io
import re

import pandas as pd
import requests

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

def parse_workbook(xlsx_bytes: bytes, columns_spec: list) -> pd.DataFrame:
    """
    Parse the ifo English workbook into a DataFrame indexed by month-end
    datetime.  Only columns listed in `columns_spec` are emitted.

    Args:
        xlsx_bytes: the workbook bytes.
        columns_spec: list of (output_column, excel_column, *_rest).
            Only the first two tuple entries are read here; the rest are
            metadata consumed elsewhere (display name, units, etc.).
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
    for spec in columns_spec:
        out_col, xl_col = spec[0], spec[1]
        out[out_col] = pd.to_numeric(df[xl_col], errors="coerce")
    # Drop rows where every tracked series is NaN (end-of-file padding).
    return out.dropna(how="all")
