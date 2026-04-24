"""
fetch_macro_ifo.py
==================
ifo Business Climate Index — Germany
Market Dashboard Expansion — Phase D surveys

WHAT THIS MODULE DOES
---------------------
Downloads the ifo Institute's monthly "ifo Time Series" Excel file and
extracts the Germany Business Climate Index (2015 = 100, seasonally
adjusted). This is the replacement source for DE_IFO1 after FMP's
economic calendar was paywalled in August 2025.

Outputs (same schema as other survey fetchers):
  data/macro_ifo.csv          — snapshot (latest + prior + change)
  data/macro_ifo_hist.csv     — weekly Friday spine from 2000-01-01
  Google Sheets tab 'macro_ifo'       — snapshot
  Google Sheets tab 'macro_ifo_hist'  — history

COLUMN NAMES
------------
Output CSV columns are: DE_IFO (climate), DE_IFO_SIT (situation),
DE_IFO_EXP (expectations). Only DE_IFO is consumed by Phase E today;
the other two are included because they come from the same Excel file
at zero extra cost and may be useful for future sub-indicators.

DESIGN PRINCIPLES
-----------------
· The download URL is versioned monthly (gsk-e-YYYYMM.xlsx), so we scrape
  the landing page for the current link rather than guessing the filename.
· No API key, no registration. Polite User-Agent header required or
  the server returns HTTP 403 to default Python UA.
· Self-contained. Safe to run standalone or called from fetch_data.py
  via run_phase_d_ifo().
· One error anywhere in the pipeline is non-fatal — existing CSV is kept.

USAGE
-----
Standalone:
    python fetch_macro_ifo.py

Called from fetch_data.py:
    try:
        from fetch_macro_ifo import run_phase_d_ifo
        run_phase_d_ifo()
    except Exception as e:
        print(f"[Phase D ifo] Non-fatal error: {e}")
"""

import io
import os
import re
from datetime import date, datetime, timedelta, timezone

import pandas as pd
import requests

from sources.base import (
    build_friday_spine,
    get_sheets_service,
    push_df_to_sheets,
)


# ---------------------------------------------------------------------------
# CONFIG
# ---------------------------------------------------------------------------

GOOGLE_CREDENTIALS_JSON = os.environ.get("GOOGLE_CREDENTIALS", "")
SHEET_ID = "12nKIUGHz5euDbNQPDTVECsJBNwrceRF1ymsQrIe4_ac"

SNAPSHOT_TAB = "macro_ifo"
HIST_TAB     = "macro_ifo_hist"
SNAPSHOT_CSV = "data/macro_ifo.csv"
HIST_CSV     = "data/macro_ifo_hist.csv"

HIST_START = "2000-01-01"

IFO_BASE = "https://www.ifo.de"
IFO_LANDING = f"{IFO_BASE}/en/ifo-time-series"

USER_AGENT = (
    "Mozilla/5.0 (compatible; market_dash_auto/1.0; "
    "+https://github.com/Kasim81/market_dash_auto)"
)

# ifo English workbook column layout (row 9 is the data header, rows 1-8 are
# metadata). Column A = yearmonth string 'MM/YYYY'. Columns B–I as below.
COLUMNS = [
    ("DE_IFO",      "climate_index",     "ifo Business Climate (Germany, 2015=100, SA)",           "Index (2015 = 100)"),
    ("DE_IFO_SIT",  "situation_index",   "ifo Business Situation sub-index",                       "Index (2015 = 100)"),
    ("DE_IFO_EXP",  "expectation_index", "ifo Business Expectations sub-index",                    "Index (2015 = 100)"),
]
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
# DOWNLOAD — scrape landing page for current workbook URL
# ---------------------------------------------------------------------------

_HREF_RE = re.compile(r'href=[\'"]([^\'"]*gsk-[ed]-\d{6}\.xlsx)[\'"]', re.IGNORECASE)


def _resolve_workbook_url() -> str:
    """Scrape the ifo landing page for the current gsk-*.xlsx URL.
    The file is renamed monthly so hardcoding is fragile. English (gsk-e)
    is preferred; falls back to German (gsk-d) if only that exists."""
    resp = requests.get(IFO_LANDING, headers={"User-Agent": USER_AGENT}, timeout=30)
    resp.raise_for_status()
    matches = _HREF_RE.findall(resp.text)
    if not matches:
        raise RuntimeError(
            f"No gsk-*.xlsx link found on {IFO_LANDING}; ifo page layout may have changed"
        )
    # Prefer the English filename; otherwise take the first match.
    href = next((m for m in matches if "gsk-e-" in m.lower()), matches[0])
    return href if href.startswith("http") else IFO_BASE + href


def _download_workbook(url: str) -> bytes:
    resp = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=60)
    resp.raise_for_status()
    return resp.content


def _parse_workbook(xlsx_bytes: bytes) -> pd.DataFrame:
    """Parse the ifo English workbook. Returns DataFrame indexed by
    month-end datetime with DE_IFO, DE_IFO_SIT, DE_IFO_EXP columns."""
    df = pd.read_excel(
        io.BytesIO(xlsx_bytes),
        sheet_name=0,
        skiprows=8,
        header=None,
        names=EXCEL_COL_NAMES,
    )
    # Parse MM/YYYY → month-end date. Drop rows where yearmonth is blank.
    df = df[df["yearmonth"].notna()].copy()
    df["date"] = pd.to_datetime(df["yearmonth"].astype(str), format="%m/%Y", errors="coerce")
    df = df[df["date"].notna()].set_index("date").sort_index()
    # Shift first-of-month → last-of-month for consistency with period-end
    # convention used elsewhere in the project.
    df.index = df.index + pd.offsets.MonthEnd(0)

    out = pd.DataFrame(index=df.index)
    for out_col, xl_col, _, _ in COLUMNS:
        out[out_col] = pd.to_numeric(df[xl_col], errors="coerce")
    # Drop rows where ALL three values are NaN (end-of-series padding).
    out = out.dropna(how="all")
    return out


# ---------------------------------------------------------------------------
# OUTPUT BUILDERS
# ---------------------------------------------------------------------------

def build_snapshot(monthly_df: pd.DataFrame, source_url: str) -> pd.DataFrame:
    """One row per output column. Matches the column headings used by
    macro_dbnomics.csv so the two snapshots look consistent."""
    fetched_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    rows = []
    for i, (col, _, name, units) in enumerate(COLUMNS, 1):
        s = monthly_df[col].dropna()
        if s.empty:
            latest = prior = change = None
            last_period = ""
        else:
            latest = round(float(s.iloc[-1]), 4)
            prior = round(float(s.iloc[-2]), 4) if len(s) >= 2 else None
            change = round(latest - prior, 4) if prior is not None else None
            last_period = s.index[-1].strftime("%Y-%m")
        rows.append({
            "row_id":       i,
            "Series ID":    col,
            "Col":          col,
            "Indicator":    name,
            "Region":       "DE",
            "Category":     "Survey",
            "Subcategory":  "Business Sentiment",
            "Units":        units,
            "Frequency":    "Monthly",
            "Latest Value": latest,
            "Prior Value":  prior,
            "Change":       change,
            "Last Period":  last_period,
            "Source":       "ifo Institute (ifo.de time series)",
            "Notes":        f"Parsed from {source_url}",
            "Fetched At":   fetched_at,
        })
    return pd.DataFrame(rows)


def build_history(monthly_df: pd.DataFrame) -> pd.DataFrame:
    """Forward-fill monthly observations onto a weekly Friday spine from
    HIST_START. Mirrors the structure produced by fetch_macro_dbnomics."""
    today = date.today()
    spine = build_friday_spine(HIST_START, today)
    hist = pd.DataFrame(index=spine)
    hist.index.name = "Date"
    for col, _, _, _ in COLUMNS:
        if col not in monthly_df.columns:
            continue
        raw = monthly_df[col].dropna()
        if raw.empty:
            continue
        combined = raw.reindex(spine.union(raw.index)).sort_index().ffill().reindex(spine)
        hist[col] = combined
    return hist


# ---------------------------------------------------------------------------
# METADATA PREFIX (mirrors macro_dbnomics_hist layout)
# ---------------------------------------------------------------------------

def _build_hist_metadata(columns: list, source_url: str) -> list[list]:
    rows = {
        "Column ID":    ["Column ID"],
        "Source Code":  ["Source Code"],
        "Source":       ["Source"],
        "Indicator":    ["Indicator"],
        "Region":       ["Region"],
        "Units":        ["Units"],
        "Frequency":    ["Frequency"],
        "Last Updated": ["Last Updated"],
    }
    lookup = {c[0]: c for c in COLUMNS}
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    for col in columns:
        info = lookup.get(col)
        rows["Column ID"].append(col)
        rows["Source Code"].append(source_url)
        rows["Source"].append("ifo Institute")
        rows["Indicator"].append(info[2] if info else col)
        rows["Region"].append("DE")
        rows["Units"].append(info[3] if info else "")
        rows["Frequency"].append("Weekly (from Monthly ffill)")
        rows["Last Updated"].append(ts)
    return list(rows.values())


# ---------------------------------------------------------------------------
# CSV WRITERS
# ---------------------------------------------------------------------------

def write_snapshot_csv(snapshot: pd.DataFrame) -> None:
    os.makedirs(os.path.dirname(SNAPSHOT_CSV), exist_ok=True)
    snapshot.to_csv(SNAPSHOT_CSV, index=False)
    print(f"[ifo] Wrote snapshot → {SNAPSHOT_CSV} ({len(snapshot)} rows)")


def write_hist_csv(hist: pd.DataFrame, source_url: str) -> None:
    os.makedirs(os.path.dirname(HIST_CSV), exist_ok=True)
    meta = _build_hist_metadata(list(hist.columns), source_url)
    with open(HIST_CSV, "w", newline="") as f:
        for row in meta:
            f.write(",".join(str(v) for v in row) + "\n")
        hist_out = hist.copy()
        hist_out.index = hist_out.index.strftime("%Y-%m-%d")
        hist_out.to_csv(f, index=True, index_label="Date")
    print(f"[ifo] Wrote history → {HIST_CSV} ({len(hist)} rows × {len(hist.columns)} cols)")


# ---------------------------------------------------------------------------
# SHEETS PUSH (only if credentials present)
# ---------------------------------------------------------------------------

def push_to_sheets(snapshot: pd.DataFrame, hist: pd.DataFrame, source_url: str) -> None:
    service = get_sheets_service(GOOGLE_CREDENTIALS_JSON)
    if service is None:
        print("[ifo] Skipping Sheets push (no GOOGLE_CREDENTIALS)")
        return

    push_df_to_sheets(service, SHEET_ID, SNAPSHOT_TAB, snapshot, label="ifo")

    meta_rows = _build_hist_metadata(list(hist.columns), source_url)
    hist_out = hist.reset_index()
    hist_out.rename(columns={hist_out.columns[0]: "Date"}, inplace=True)
    hist_out["Date"] = hist_out["Date"].dt.strftime("%Y-%m-%d")
    push_df_to_sheets(
        service, SHEET_ID, HIST_TAB, hist_out,
        label="ifo", prefix_rows=meta_rows,
    )


# ---------------------------------------------------------------------------
# ENTRY POINT
# ---------------------------------------------------------------------------

def run_phase_d_ifo() -> None:
    print("\n" + "=" * 60)
    print("Phase D — ifo Business Climate (Germany)")
    print("=" * 60)
    url = _resolve_workbook_url()
    print(f"[ifo] Resolved workbook: {url}")
    xlsx_bytes = _download_workbook(url)
    monthly_df = _parse_workbook(xlsx_bytes)
    print(f"[ifo] Parsed {len(monthly_df)} monthly observations "
          f"({monthly_df.index.min().date()} → {monthly_df.index.max().date()})")
    snapshot = build_snapshot(monthly_df, url)
    hist = build_history(monthly_df)
    write_snapshot_csv(snapshot)
    write_hist_csv(hist, url)
    push_to_sheets(snapshot, hist, url)


if __name__ == "__main__":
    run_phase_d_ifo()
