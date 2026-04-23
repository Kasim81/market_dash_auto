"""
fetch_macro_fmp.py
==================
Phase D (Tier 3) — Proprietary PMI / Survey Data via FMP Economic Calendar
Market Dashboard Expansion

WHAT THIS MODULE DOES
---------------------
Fetches S&P Global proprietary PMIs and institute-published surveys that
are not available on DB.nomics or FRED.  Uses the FMP economic calendar
endpoint, which redistributes these releases as calendar events with
actual / previous / estimate values.

  S&P Global / HCOB:
    · Eurozone Manufacturing PMI
    · Eurozone Services PMI

  Institute surveys:
    · ZEW Economic Sentiment (Germany)
    · IFO Business Climate (Germany)

  S&P Global country PMIs:
    · UK Manufacturing PMI
    · Jibun Bank Japan Manufacturing PMI
    · NBS China Manufacturing PMI
    · Caixin China Manufacturing PMI

CALENDAR → TIME SERIES TRANSFORMATION
--------------------------------------
The FMP economic calendar returns one JSON object per release event.
This module transforms them into a monthly time series by:
  1. Fetching the calendar over a rolling lookback window (5+ years)
  2. Matching events by name patterns from macro_library_fmp.csv
  3. Extracting the 'actual' value from each matched event
  4. Deduplicating to one reading per calendar month (latest wins —
     handles flash vs. final PMI releases in the same month)
  5. Indexing by end-of-month date for the Friday-spine history builder

Outputs:
  data/macro_fmp.csv          — snapshot (latest + prior + change)
  data/macro_fmp_hist.csv     — history on weekly Friday spine
  Google Sheets: 'macro_fmp'      — snapshot tab
  Google Sheets: 'macro_fmp_hist' — history tab

DESIGN PRINCIPLES
-----------------
· Library-driven: event patterns defined in data/macro_library_fmp.csv.
  Update event names there if FMP renames them — no Python changes needed.
· Self-contained. Safe to run standalone or from fetch_data.py.
· Per-event try/except so one failure never kills the whole run.
· FMP free tier: 250 calls/day. This module makes ~10 calls per run
  (5 years ÷ 6-month chunks), well within budget.

USAGE
-----
Standalone:
    export FMP_API_KEY=your_key_here
    python fetch_macro_fmp.py

Called from fetch_data.py:
    try:
        from fetch_macro_fmp import run_phase_d_fmp
        run_phase_d_fmp()
    except Exception as e:
        print(f"[Phase D FMP] Non-fatal error: {e}")
"""

import csv as csv_module
import json
import os
import pathlib
import time
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone

import numpy as np
import pandas as pd
import requests

from library_utils import SHEETS_PROTECTED_TABS

from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build


# ---------------------------------------------------------------------------
# CONFIG
# ---------------------------------------------------------------------------

FMP_API_KEY = os.environ.get("FMP_API_KEY", "")
FMP_BASE = "https://financialmodelingprep.com/stable/economic-calendar"

GOOGLE_CREDENTIALS_JSON = os.environ.get("GOOGLE_CREDENTIALS", "")
SHEET_ID = "12nKIUGHz5euDbNQPDTVECsJBNwrceRF1ymsQrIe4_ac"

SNAPSHOT_TAB = "macro_fmp"
HIST_TAB     = "macro_fmp_hist"
SNAPSHOT_CSV = "data/macro_fmp.csv"
HIST_CSV     = "data/macro_fmp_hist.csv"

HIST_START = "2015-01-01"

# Calendar fetch settings
LOOKBACK_YEARS = 6
CHUNK_MONTHS = 6
REQUEST_DELAY = 0.5

# Exponential backoff
BACKOFF_BASE = 2
BACKOFF_MAX_RETRIES = 4

_LIBRARY_CSV = pathlib.Path(__file__).parent / "data" / "macro_library_fmp.csv"


# ---------------------------------------------------------------------------
# LIBRARY LOADER
# ---------------------------------------------------------------------------

def _load_library() -> list[dict]:
    """
    Load FMP event definitions from macro_library_fmp.csv.
    The event_patterns column contains pipe-delimited substrings for
    case-insensitive matching against FMP event names.
    """
    df = pd.read_csv(_LIBRARY_CSV, dtype=str, keep_default_na=False)
    df["sort_key"] = pd.to_numeric(df["sort_key"], errors="coerce").fillna(0)
    df = df.sort_values("sort_key")
    result = []
    for _, row in df.iterrows():
        patterns = [p.strip().lower() for p in row["event_patterns"].split("|") if p.strip()]
        result.append({
            "col":        row["col"].strip(),
            "name":       row["name"].strip(),
            "category":   row["category"].strip(),
            "subcategory": row["subcategory"].strip(),
            "units":      row["units"].strip(),
            "frequency":  row["frequency"].strip(),
            "region":     row["region"].strip(),
            "patterns":   patterns,
            "notes":      row["notes"].strip(),
        })
    return result


INDICATORS = _load_library()


# ---------------------------------------------------------------------------
# FMP API — CALENDAR FETCH WITH BACKOFF
# ---------------------------------------------------------------------------

def _fetch_calendar_chunk(start_date: str, end_date: str) -> list[dict]:
    """Fetch one chunk of the FMP economic calendar."""
    if not FMP_API_KEY:
        return []

    params = {
        "from": start_date,
        "to": end_date,
        "apikey": FMP_API_KEY,
    }

    for attempt in range(BACKOFF_MAX_RETRIES):
        try:
            resp = requests.get(FMP_BASE, params=params, timeout=30)

            if resp.status_code == 200:
                data = resp.json()
                if isinstance(data, list):
                    return data
                if isinstance(data, dict) and "Error Message" in data:
                    print(f"    [API error] {data['Error Message']}")
                    return []
                print(f"    [Unexpected response type] {type(data).__name__}: "
                      f"{str(data)[:300]}")
                return []

            elif resp.status_code == 429:
                wait = BACKOFF_BASE ** (attempt + 1)
                print(f"    [Rate limit] backing off {wait}s "
                      f"(attempt {attempt + 1}/{BACKOFF_MAX_RETRIES})")
                time.sleep(wait)

            elif resp.status_code >= 500:
                wait = BACKOFF_BASE ** (attempt + 1)
                print(f"    [Server error {resp.status_code}] backing off {wait}s")
                time.sleep(wait)

            else:
                print(f"    [HTTP {resp.status_code}] {start_date}→{end_date} — skipping")
                return []

        except requests.exceptions.Timeout:
            wait = BACKOFF_BASE ** (attempt + 1)
            print(f"    [Timeout] backing off {wait}s")
            time.sleep(wait)

        except requests.exceptions.RequestException as e:
            print(f"    [Request error] {e} — skipping chunk")
            return []

    print(f"    [FAIL] All {BACKOFF_MAX_RETRIES} attempts failed for {start_date}→{end_date}")
    return []


def _fetch_full_calendar() -> list[dict]:
    """Fetch the full calendar over the lookback window in chunks."""
    all_events = []
    end = datetime.now()
    start = end - timedelta(days=LOOKBACK_YEARS * 365)

    cursor = start
    chunk_num = 0
    while cursor < end:
        chunk_end = min(cursor + timedelta(days=CHUNK_MONTHS * 30), end)
        s = cursor.strftime("%Y-%m-%d")
        e = chunk_end.strftime("%Y-%m-%d")
        chunk_num += 1
        print(f"    Chunk {chunk_num}: {s} → {e} ...", end=" ", flush=True)

        events = _fetch_calendar_chunk(s, e)
        print(f"{len(events)} events")
        all_events.extend(events)

        cursor = chunk_end + timedelta(days=1)
        time.sleep(REQUEST_DELAY)

    return all_events


# ---------------------------------------------------------------------------
# EVENT MATCHING + TIME SERIES TRANSFORMATION
# ---------------------------------------------------------------------------

def _match_event(event_name: str, patterns: list[str]) -> bool:
    """Check if an event name matches any pattern (case-insensitive substring)."""
    name_lower = event_name.lower().strip()
    return any(p in name_lower for p in patterns)


def _events_to_monthly(events: list[dict]) -> list[tuple[str, float]]:
    """
    Transform matched calendar events into a monthly time series.

    Deduplication: if multiple events match in the same month (flash vs final),
    keep the one with the latest date (final reading supersedes flash).

    Returns [(YYYY-MM, actual_value), ...] sorted ascending.
    """
    by_month: dict[str, tuple[str, float]] = {}

    for event in events:
        actual = event.get("actual")
        if actual is None or str(actual).strip() in ("", "None"):
            continue

        try:
            val = float(actual)
        except (ValueError, TypeError):
            continue

        event_date = str(event.get("date", ""))[:10]
        if len(event_date) < 7:
            continue

        month_key = event_date[:7]  # YYYY-MM

        existing = by_month.get(month_key)
        if existing is None or event_date > existing[0]:
            by_month[month_key] = (event_date, val)

    return sorted([(m, v) for m, (_, v) in by_month.items()])


def _build_all_series(all_events: list[dict]) -> dict[str, list[tuple[str, float]]]:
    """
    Match all calendar events against library indicators and build
    monthly time series for each.
    Returns {col: [(YYYY-MM, value), ...]} sorted ascending.
    """
    result = {}

    for indic in INDICATORS:
        col = indic["col"]
        patterns = indic["patterns"]

        matched = [
            e for e in all_events
            if _match_event(e.get("event", ""), patterns)
        ]

        monthly = _events_to_monthly(matched)
        result[col] = monthly

        if monthly:
            print(f"    {col:15s}: {len(matched):>4} events → {len(monthly):>3} months  "
                  f"({monthly[0][0]} → {monthly[-1][0]})")
        else:
            print(f"    {col:15s}: {len(matched):>4} events → NO actual values")

    return result


# ---------------------------------------------------------------------------
# SNAPSHOT BUILDER
# ---------------------------------------------------------------------------

def _build_snapshot(series_data: dict[str, list]) -> pd.DataFrame:
    """Build snapshot DataFrame from monthly series data."""
    rows = []

    for indic in INDICATORS:
        col = indic["col"]
        monthly = series_data.get(col, [])

        if not monthly:
            rows.append(_snapshot_row(indic, None, None, None, ""))
            continue

        last_period, latest_val = monthly[-1]
        prior_val = monthly[-2][1] if len(monthly) >= 2 else None
        change = round(latest_val - prior_val, 4) if prior_val is not None else None

        rows.append(_snapshot_row(indic, latest_val, prior_val, change, last_period))

    return pd.DataFrame(rows)


def _snapshot_row(indic: dict, latest, prior, change, last_period: str) -> dict:
    return {
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
        "Source":       "FMP",
        "Notes":        indic["notes"],
        "Fetched At":   datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
    }


# ---------------------------------------------------------------------------
# HISTORY BUILDER
# ---------------------------------------------------------------------------

def _last_friday_on_or_before(d: date) -> date:
    weekday = d.weekday()
    days_since_friday = (weekday - 4) % 7
    return d - timedelta(days=days_since_friday)


def _build_friday_spine(start: str, end: date) -> pd.DatetimeIndex:
    first_friday = _last_friday_on_or_before(
        datetime.strptime(start, "%Y-%m-%d").date()
    )
    return pd.date_range(start=first_friday, end=end, freq="W-FRI")


def _monthly_to_series(obs: list[tuple[str, float]], col_name: str) -> pd.Series:
    """Convert (YYYY-MM, value) pairs to a Series indexed by end-of-month."""
    dates, vals = [], []
    for period, val in obs:
        try:
            dt = datetime.strptime(period + "-01", "%Y-%m-%d")
            if dt.month == 12:
                eom = dt.replace(day=31)
            else:
                eom = dt.replace(month=dt.month + 1, day=1) - timedelta(days=1)
            dates.append(eom)
            vals.append(val)
        except ValueError:
            continue
    if not dates:
        return pd.Series(dtype=float)
    return pd.Series(vals, index=pd.DatetimeIndex(dates), name=col_name)


def build_history(series_data: dict[str, list]) -> pd.DataFrame:
    """Build weekly Friday-spine history from monthly series data."""
    today = date.today()
    spine = _build_friday_spine(HIST_START, today)
    hist = pd.DataFrame(index=spine)
    hist.index.name = "Date"

    for indic in INDICATORS:
        col = indic["col"]
        obs = series_data.get(col, [])
        if not obs:
            continue
        raw = _monthly_to_series(obs, col)
        if raw.empty:
            continue
        combined = raw.reindex(spine.union(raw.index)).sort_index()
        combined = combined.ffill().reindex(spine)
        hist[col] = combined

    print(f"\n[Phase D FMP] History: {len(hist)} rows × {len(hist.columns)} data columns")
    return hist


# ---------------------------------------------------------------------------
# METADATA ROWS FOR HISTORY TAB
# ---------------------------------------------------------------------------

def _build_hist_metadata(columns: list) -> list[list]:
    indic_map = {i["col"]: i for i in INDICATORS}
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    row_colid = ["Column ID"]
    row_source = ["Source Code"]
    row_src = ["Source"]
    row_name = ["Indicator"]
    row_region = ["Region"]
    row_units = ["Units"]
    row_freq = ["Frequency"]
    row_updated = ["Last Updated"]

    for col in columns:
        indic = indic_map.get(col, {})
        row_colid.append(col)
        row_source.append("|".join(indic.get("patterns", [])))
        row_src.append("FMP")
        row_name.append(indic.get("name", col))
        row_region.append(indic.get("region", ""))
        row_units.append(indic.get("units", ""))
        row_freq.append(f"Weekly (from {indic.get('frequency', 'Monthly')} ffill)")
        row_updated.append(ts)

    return [row_colid, row_source, row_src, row_name, row_region,
            row_units, row_freq, row_updated]


# ---------------------------------------------------------------------------
# CSV I/O
# ---------------------------------------------------------------------------

def save_snapshot_csv(df: pd.DataFrame) -> None:
    os.makedirs("data", exist_ok=True)
    if os.path.exists(SNAPSHOT_CSV):
        try:
            existing = pd.read_csv(SNAPSHOT_CSV)
            cols = ["Col", "Latest Value", "Prior Value", "Change", "Last Period"]
            if existing[cols].equals(df[cols]):
                print(f"[Phase D FMP] Snapshot CSV unchanged — skipping write")
                return
        except Exception:
            pass
    df.to_csv(SNAPSHOT_CSV, index=False)
    print(f"[Phase D FMP] Written {len(df)} rows to {SNAPSHOT_CSV}")


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
    print(f"[Phase D FMP] Written {len(df)} rows + {len(meta_rows)} metadata rows to {HIST_CSV}")


# ---------------------------------------------------------------------------
# GOOGLE SHEETS
# ---------------------------------------------------------------------------

def _get_sheets_service():
    if not GOOGLE_CREDENTIALS_JSON:
        return None
    creds_dict = json.loads(GOOGLE_CREDENTIALS_JSON)
    creds = Credentials.from_service_account_info(
        creds_dict,
        scopes=["https://www.googleapis.com/auth/spreadsheets"],
    )
    return build("sheets", "v4", credentials=creds)


def _ensure_tab(service, tab_name: str) -> None:
    meta = service.spreadsheets().get(spreadsheetId=SHEET_ID).execute()
    existing = [s["properties"]["title"] for s in meta.get("sheets", [])]
    if tab_name not in existing:
        body = {"requests": [{"addSheet": {"properties": {"title": tab_name}}}]}
        service.spreadsheets().batchUpdate(spreadsheetId=SHEET_ID, body=body).execute()
        print(f"[Phase D FMP] Created tab '{tab_name}'")


def _sv(v):
    if v is None:
        return ""
    try:
        if pd.isna(v):
            return ""
    except (TypeError, ValueError):
        pass
    if isinstance(v, (int, float)):
        return float(v)
    return str(v)


def push_snapshot_to_sheets(df: pd.DataFrame) -> None:
    if not GOOGLE_CREDENTIALS_JSON:
        print("[Phase D FMP] GOOGLE_CREDENTIALS not set — skipping Sheets push")
        return
    if df.empty:
        return
    if SNAPSHOT_TAB in SHEETS_PROTECTED_TABS:
        print(f"[Phase D FMP] REFUSED: '{SNAPSHOT_TAB}' is a protected tab")
        return

    try:
        service = _get_sheets_service()
        _ensure_tab(service, SNAPSHOT_TAB)
        sheets = service.spreadsheets()

        header = list(df.columns)
        data_rows = [[_sv(v) for v in row] for row in df.itertuples(index=False)]
        values = [header] + data_rows

        sheets.values().clear(spreadsheetId=SHEET_ID, range=f"{SNAPSHOT_TAB}!A:ZZ").execute()
        sheets.values().update(
            spreadsheetId=SHEET_ID,
            range=f"{SNAPSHOT_TAB}!A1",
            valueInputOption="USER_ENTERED",
            body={"values": values},
        ).execute()
        print(f"[Phase D FMP] Written {len(df)} rows to '{SNAPSHOT_TAB}' tab")

    except Exception as e:
        print(f"[Phase D FMP] Sheets push error (snapshot): {e}")


def push_hist_to_sheets(df: pd.DataFrame) -> None:
    if not GOOGLE_CREDENTIALS_JSON:
        print("[Phase D FMP] GOOGLE_CREDENTIALS not set ��� skipping Sheets push")
        return
    if df.empty:
        return
    if HIST_TAB in SHEETS_PROTECTED_TABS:
        print(f"[Phase D FMP] REFUSED: '{HIST_TAB}' is a protected tab")
        return

    try:
        service = _get_sheets_service()
        _ensure_tab(service, HIST_TAB)
        sheets = service.spreadsheets()

        meta_rows = _build_hist_metadata(list(df.columns))
        header = ["Date"] + list(df.columns)
        data_rows = []
        for idx, row in df.iterrows():
            data_rows.append([idx.strftime("%Y-%m-%d")] + [_sv(v) for v in row])

        values = meta_rows + [header] + data_rows

        sheets.values().clear(spreadsheetId=SHEET_ID, range=f"{HIST_TAB}!A:ZZ").execute()
        sheets.values().update(
            spreadsheetId=SHEET_ID,
            range=f"{HIST_TAB}!A1",
            valueInputOption="USER_ENTERED",
            body={"values": values},
        ).execute()
        print(f"[Phase D FMP] Written {len(df)} data rows + metadata to '{HIST_TAB}' tab")

    except Exception as e:
        print(f"[Phase D FMP] Sheets push error (history): {e}")


# ---------------------------------------------------------------------------
# ENTRY POINT
# ---------------------------------------------------------------------------

def run_phase_d_fmp() -> None:
    """
    DISABLED — FMP free tier no longer includes economic calendar access.

    Both /api/v3/economic_calendar (HTTP 403 "Legacy Endpoint") and
    /stable/economic-calendar (HTTP 402 "Restricted Endpoint: not available
    under your current subscription") are paywalled as of August 2025.

    The fetch logic below (_fetch_full_calendar, _build_all_series, snapshot
    + history builders) is preserved in case we later find a drop-in free
    calendar source or upgrade the FMP subscription. Currently unused.

    See manuals/forward_plan.md §3.7 for the alternative-source plan.
    """
    print("\n" + "=" * 60)
    print("Phase D (Tier 3) — PMI / Survey Data (FMP Calendar)")
    print("=" * 60)
    print("[Phase D FMP] DISABLED — FMP free tier no longer includes "
          "economic calendar (both /v3 and /stable paywalled as of Aug 2025).")
    print("[Phase D FMP] See manuals/forward_plan.md §3.7 for replacement plan.")
    return


if __name__ == "__main__":
    run_phase_d_fmp()
