"""
fetch_macro_dbnomics.py
=======================
Phase D (Tier 2) — Business Survey Data via DB.nomics REST API
Market Dashboard Expansion

WHAT THIS MODULE DOES
---------------------
Fetches macro survey indicators from the DB.nomics public API:

  Eurostat (Euro Area):
    · Economic Sentiment Indicator (EA)  — ei_bssi_m_r2
    · Industry Confidence (EA)           — ei_bssi_m_r2
    · Services Confidence (EA)           — ei_bssi_m_r2

  ISM (US):
    · Manufacturing PMI                   — ISM/pmi
    · Manufacturing New Orders            — ISM/neword
    · Services PMI (Non-Manufacturing)    — ISM/nm-pmi

  Note: ISM mirror may lag 4-8 months (known DB.nomics staleness).
  ECB BLS dataset absent from DB.nomics (HTTP 404).
  BOJ Tankan absent from DB.nomics.

Outputs:
  data/macro_dbnomics.csv          — snapshot (latest + prior + change)
  data/macro_dbnomics_hist.csv     — history on weekly Friday spine
  Google Sheets: 'macro_dbnomics'      — snapshot tab
  Google Sheets: 'macro_dbnomics_hist' — history tab

DESIGN PRINCIPLES
-----------------
· Library-driven: all series defined in data/macro_library_dbnomics.csv.
  Add/remove series by editing the CSV — no Python changes needed.
· Self-contained. Safe to run standalone or called from fetch_data.py
  via run_phase_d().
· All errors caught per-series so one failure never kills the whole run.
· DB.nomics API: free, no key, no documented rate limit.
  Polite delay (0.5s) between requests as courtesy.

USAGE
-----
Standalone:
    python fetch_macro_dbnomics.py

Called from fetch_data.py:
    try:
        from fetch_macro_dbnomics import run_phase_d
        run_phase_d()
    except Exception as e:
        print(f"[Phase D] Non-fatal error: {e}")
"""

import csv as csv_module
import json
import os
import pathlib
import time
import requests
import pandas as pd
from datetime import date, datetime, timedelta, timezone

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

SNAPSHOT_TAB = "macro_dbnomics"
HIST_TAB     = "macro_dbnomics_hist"
SNAPSHOT_CSV = "data/macro_dbnomics.csv"
HIST_CSV     = "data/macro_dbnomics_hist.csv"

HIST_START = "2000-01-01"

DBNOMICS_BASE = "https://api.db.nomics.world/v22"
REQUEST_DELAY = 0.5  # seconds between API requests (courtesy)

# Exponential backoff
BACKOFF_BASE = 2
BACKOFF_MAX_RETRIES = 4

_LIBRARY_CSV = pathlib.Path(__file__).parent / "data" / "macro_library_dbnomics.csv"


# ---------------------------------------------------------------------------
# LIBRARY LOADER
# ---------------------------------------------------------------------------

def _load_library() -> list[dict]:
    """
    Load DB.nomics indicator definitions from macro_library_dbnomics.csv.
    Returns a list of dicts, one per series.
    """
    df = pd.read_csv(_LIBRARY_CSV, dtype=str, keep_default_na=False)
    df["sort_key"] = pd.to_numeric(df["sort_key"], errors="coerce").fillna(0)
    df = df.sort_values("sort_key")
    result = []
    for _, row in df.iterrows():
        result.append({
            "series_id":  row["series_id"].strip(),
            "col":        row["col"].strip(),
            "name":       row["name"].strip(),
            "category":   row["category"].strip(),
            "subcategory": row["subcategory"].strip(),
            "units":      row["units"].strip(),
            "frequency":  row["frequency"].strip(),
            "region":     row["region"].strip(),
            "notes":      row["notes"].strip(),
        })
    return result


INDICATORS = _load_library()


# ---------------------------------------------------------------------------
# DB.NOMICS API — FETCH WITH BACKOFF
# ---------------------------------------------------------------------------

def _dbnomics_fetch(series_id: str) -> dict | None:
    """
    Fetch a single series from DB.nomics with observations.
    series_id format: "PROVIDER/DATASET/SERIES_CODE"
    Returns the series document dict or None on failure.
    """
    url = f"{DBNOMICS_BASE}/series"
    params = {
        "observations": "1",
        "series_ids": series_id,
        "limit": 1,
    }

    for attempt in range(BACKOFF_MAX_RETRIES):
        try:
            resp = requests.get(url, params=params, timeout=30)

            if resp.status_code == 200:
                data = resp.json()
                docs = data.get("series", {}).get("docs", [])
                if docs:
                    return docs[0]
                return None

            elif resp.status_code == 429:
                wait = BACKOFF_BASE ** (attempt + 1)
                print(f"    [Rate limit] {series_id} — backing off {wait}s "
                      f"(attempt {attempt + 1}/{BACKOFF_MAX_RETRIES})")
                time.sleep(wait)

            elif resp.status_code >= 500:
                wait = BACKOFF_BASE ** (attempt + 1)
                print(f"    [Server error {resp.status_code}] {series_id} — backing off {wait}s")
                time.sleep(wait)

            else:
                print(f"    [HTTP {resp.status_code}] {series_id} — skipping")
                return None

        except requests.exceptions.Timeout:
            wait = BACKOFF_BASE ** (attempt + 1)
            print(f"    [Timeout] {series_id} — backing off {wait}s")
            time.sleep(wait)

        except requests.exceptions.RequestException as e:
            print(f"    [Request error] {series_id}: {e} — skipping")
            return None

    print(f"    [FAIL] All {BACKOFF_MAX_RETRIES} attempts failed for {series_id}")
    return None


def _parse_observations(doc: dict) -> list[tuple[str, float]]:
    """
    Extract (period_str, value) pairs from a DB.nomics series document.
    Filters out nulls/NAs. Returns sorted ascending by period.
    """
    periods = doc.get("period", [])
    values = doc.get("value", [])
    pairs = []
    for p, v in zip(periods, values):
        if v is None or str(v).lower() in ("na", "nan", ""):
            continue
        try:
            pairs.append((str(p), float(v)))
        except (ValueError, TypeError):
            continue
    pairs.sort(key=lambda x: x[0])
    return pairs


# ---------------------------------------------------------------------------
# SNAPSHOT BUILDER
# ---------------------------------------------------------------------------

def fetch_snapshot() -> pd.DataFrame:
    """
    Fetch all DB.nomics indicators and return a snapshot DataFrame.
    Each row = one indicator with latest + prior values.
    """
    rows = []
    total = len(INDICATORS)
    print(f"\nFetching {total} DB.nomics series...")

    for i, indic in enumerate(INDICATORS, 1):
        sid = indic["series_id"]
        print(f"  [{i}/{total}] {sid} ({indic['name']})...")

        doc = _dbnomics_fetch(sid)
        if not doc:
            print(f"    → No data returned")
            rows.append(_snapshot_row(indic, None, None, None, ""))
            if i < total:
                time.sleep(REQUEST_DELAY)
            continue

        obs = _parse_observations(doc)
        if not obs:
            print(f"    → No valid observations")
            rows.append(_snapshot_row(indic, None, None, None, ""))
            if i < total:
                time.sleep(REQUEST_DELAY)
            continue

        latest_period, latest_val = obs[-1]
        prior_val = obs[-2][1] if len(obs) >= 2 else None
        change = round(latest_val - prior_val, 4) if prior_val is not None else None

        print(f"    → Latest: {latest_val}  Prior: {prior_val}  "
              f"Period: {latest_period}  ({len(obs)} obs total)")

        rows.append(_snapshot_row(indic, latest_val, prior_val, change, latest_period))

        if i < total:
            time.sleep(REQUEST_DELAY)

    df = pd.DataFrame(rows)
    print(f"\n[Phase D] Fetched {len(df)} DB.nomics indicators")
    return df


def _snapshot_row(indic: dict, latest, prior, change, last_period: str) -> dict:
    return {
        "Series ID":    indic["series_id"],
        "Col":          indic["col"],
        "Indicator":    indic["name"],
        "Region":       indic["region"],
        "Category":     indic["category"],
        "Subcategory":  indic["subcategory"],
        "Units":        indic["units"],
        "Frequency":    indic["frequency"],
        "Latest Value": latest,
        "Prior Value":  prior,
        "Change":       change,
        "Last Period":  last_period,
        "Source":       "DB.nomics",
        "Notes":        indic["notes"],
        "Fetched At":   datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
    }


# ---------------------------------------------------------------------------
# HISTORY BUILDER
# ---------------------------------------------------------------------------

def _obs_to_series(obs: list[tuple[str, float]], col_name: str) -> pd.Series:
    """
    Convert observation pairs to a pandas Series indexed by end-of-month/quarter dates.
    Handles YYYY-MM, YYYY-MM-DD, and YYYY-QN period formats.
    """
    dates, vals = [], []
    for period, val in obs:
        try:
            dt = _parse_period_to_date(period)
            if dt:
                dates.append(dt)
                vals.append(val)
        except (ValueError, TypeError):
            continue

    if not dates:
        return pd.Series(dtype=float)
    return pd.Series(vals, index=pd.DatetimeIndex(dates), name=col_name)


def _parse_period_to_date(period: str) -> datetime | None:
    """Parse a DB.nomics period string to a datetime (end of period)."""
    p = str(period).strip()

    # YYYY-MM-DD
    if len(p) == 10 and p[4] == "-" and p[7] == "-":
        return datetime.strptime(p, "%Y-%m-%d")

    # YYYY-QN (quarterly) — check before YYYY-MM since both are length 7
    if len(p) == 7 and p[4] == "-" and p[5] == "Q":
        year = int(p[:4])
        q = int(p[6])
        month = q * 3
        if month == 12:
            return datetime(year, 12, 31)
        return datetime(year, month + 1, 1) - timedelta(days=1)

    # YYYY-MM
    if len(p) == 7 and p[4] == "-":
        dt = datetime.strptime(p + "-01", "%Y-%m-%d")
        if dt.month == 12:
            return dt.replace(day=31)
        return dt.replace(month=dt.month + 1, day=1) - timedelta(days=1)

    # YYYY (annual)
    if len(p) == 4 and p.isdigit():
        return datetime(int(p), 12, 31)

    return None


def fetch_history() -> dict[str, list[tuple[str, float]]]:
    """
    Fetch full history for all indicators.
    Returns {col: [(period, value), ...]} sorted ascending.
    """
    result = {}
    total = len(INDICATORS)
    print(f"\nFetching history for {total} DB.nomics series...")

    for i, indic in enumerate(INDICATORS, 1):
        sid = indic["series_id"]
        col = indic["col"]
        print(f"  [{i}/{total}] {sid} ...")

        doc = _dbnomics_fetch(sid)
        if doc:
            obs = _parse_observations(doc)
            result[col] = obs
            print(f"    → {len(obs)} observations")
        else:
            result[col] = []
            print(f"    → No data")

        if i < total:
            time.sleep(REQUEST_DELAY)

    return result


def build_history(hist_data: dict[str, list]) -> pd.DataFrame:
    """
    Build weekly Friday-spine history DataFrame from fetched data.
    Monthly/quarterly data is forward-filled onto the weekly spine.
    """
    today = date.today()
    spine = build_friday_spine(HIST_START, today)
    hist = pd.DataFrame(index=spine)
    hist.index.name = "Date"

    for indic in INDICATORS:
        col = indic["col"]
        obs = hist_data.get(col, [])
        if not obs:
            continue
        raw = _obs_to_series(obs, col)
        if raw.empty:
            continue
        combined = raw.reindex(spine.union(raw.index)).sort_index()
        combined = combined.ffill().reindex(spine)
        hist[col] = combined

    print(f"\n[Phase D] History: {len(hist)} rows × {len(hist.columns)} data columns")
    return hist


# ---------------------------------------------------------------------------
# METADATA ROWS FOR HISTORY TAB
# ---------------------------------------------------------------------------

def _build_hist_metadata(columns: list) -> list[list]:
    """
    Build metadata prefix rows for macro_dbnomics_hist.  Format matches
    macro_intl_hist and macro_us_hist.
    """
    indic_map = {i["col"]: i for i in INDICATORS}

    row_colid = ["Column ID"]
    row_source = ["Source Code"]
    row_src = ["Source"]
    row_name = ["Indicator"]
    row_region = ["Region"]
    row_units = ["Units"]
    row_freq = ["Frequency"]
    row_updated = ["Last Updated"]
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    for col in columns:
        indic = indic_map.get(col, {})
        row_colid.append(col)
        row_source.append(indic.get("series_id", ""))
        row_src.append("DB.nomics")
        row_name.append(indic.get("name", col))
        row_region.append(indic.get("region", ""))
        row_units.append(indic.get("units", ""))
        row_freq.append(f"Weekly (from {indic.get('frequency', 'Unknown')} ffill)")
        row_updated.append(ts)

    return [row_colid, row_source, row_src, row_name, row_region, row_units, row_freq, row_updated]


# ---------------------------------------------------------------------------
# CSV I/O
# ---------------------------------------------------------------------------

def save_snapshot_csv(df: pd.DataFrame) -> None:
    os.makedirs("data", exist_ok=True)
    if os.path.exists(SNAPSHOT_CSV):
        try:
            existing = pd.read_csv(SNAPSHOT_CSV)
            cols = ["Series ID", "Latest Value", "Prior Value", "Change", "Last Period"]
            if existing[cols].equals(df[cols]):
                print(f"[Phase D] Snapshot CSV unchanged — skipping write")
                return
        except Exception:
            pass
    df.to_csv(SNAPSHOT_CSV, index=False)
    print(f"[Phase D] Written {len(df)} rows to {SNAPSHOT_CSV}")


def save_hist_csv(df: pd.DataFrame) -> None:
    os.makedirs("data", exist_ok=True)
    meta_rows = _build_hist_metadata(list(df.columns))
    df_out = df.copy()
    df_out.index = df_out.index.strftime("%Y-%m-%d")

    with open(HIST_CSV, "w", newline="") as f:
        writer = csv_module.writer(f)
        writer.writerows(meta_rows)

    df_out.to_csv(HIST_CSV, mode="a", date_format="%Y-%m-%d",
                  float_format="%.4f", na_rep="", index=True)
    print(f"[Phase D] Written {len(df)} rows + {len(meta_rows)} metadata rows to {HIST_CSV}")


# ---------------------------------------------------------------------------
# GOOGLE SHEETS
# ---------------------------------------------------------------------------

def push_snapshot_to_sheets(df: pd.DataFrame) -> None:
    try:
        push_df_to_sheets(
            get_sheets_service(GOOGLE_CREDENTIALS_JSON),
            SHEET_ID,
            SNAPSHOT_TAB,
            df,
            label="Phase D",
        )
    except Exception as e:
        print(f"[Phase D] Sheets push error (snapshot): {e}")


def push_hist_to_sheets(df: pd.DataFrame) -> None:
    if df.empty:
        return
    try:
        meta_rows = _build_hist_metadata(list(df.columns))
        df_out = df.reset_index()
        df_out.rename(columns={df_out.columns[0]: "Date"}, inplace=True)
        df_out["Date"] = df_out["Date"].dt.strftime("%Y-%m-%d")

        push_df_to_sheets(
            get_sheets_service(GOOGLE_CREDENTIALS_JSON),
            SHEET_ID,
            HIST_TAB,
            df_out,
            label="Phase D",
            prefix_rows=meta_rows,
        )
    except Exception as e:
        print(f"[Phase D] Sheets push error (history): {e}")


# ---------------------------------------------------------------------------
# ENTRY POINT
# ---------------------------------------------------------------------------

def run_phase_d() -> None:
    """
    Full Phase D (Tier 2) run.  Safe to call from fetch_data.py or standalone.
    """
    print("\n" + "=" * 60)
    print("Phase D (Tier 2) — Business Survey Data (DB.nomics)")
    print("=" * 60)

    start = time.time()

    try:
        # Snapshot
        snap_df = fetch_snapshot()
        if snap_df.empty:
            print("[Phase D] No data fetched — exiting cleanly")
            return

        snap_df.insert(0, "row_id", range(1, len(snap_df) + 1))
        save_snapshot_csv(snap_df)
        push_snapshot_to_sheets(snap_df)

        # History
        print("\n--- History Build ---")
        hist_data = fetch_history()
        hist_df = build_history(hist_data)

        if not hist_df.empty:
            save_hist_csv(hist_df)
            push_hist_to_sheets(hist_df)

        elapsed = round(time.time() - start, 1)
        print(f"\n[Phase D] Complete in {elapsed}s — "
              f"{len(snap_df)} snapshot rows, "
              f"{len(hist_df)} history rows × {len(hist_df.columns)} columns")

    except Exception as e:
        print(f"[Phase D] Fatal error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    run_phase_d()
