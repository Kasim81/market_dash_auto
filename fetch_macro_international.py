"""
fetch_macro_international.py
============================
Phase C — International Macro Indicators
Market Dashboard Expansion

WHAT THIS MODULE DOES
---------------------
Fetches macro indicators for 11 major economies from two free public APIs:

  OECD Statistics SDMX-JSON API (stats.oecd.org — no key required):
    · Composite Leading Indicator (CLI)   — monthly
    · CPI Headline YoY %                  — monthly
    · Unemployment Rate                   — monthly
    · Short-term Interest Rate (3M)       — monthly

  IMF DataMapper REST API (imf.org — no key required):
    · Real GDP Growth % (annual WEO)      — annual

Countries: AUS, CAN, CHE, CHN, DEU, EA19, FRA, GBR, ITA, JPN, USA
  Note: EA19 = Eurozone 19-country aggregate (OECD code).
  Note: CHN is included in OECD CLI/CPI where available; IMF covers all indicators.

Outputs:
  data/macro_intl.csv          — snapshot (latest + prior + change per country×indicator)
  data/macro_intl_hist.csv     — history on weekly Friday spine (from 2000)
  Google Sheets: 'macro_intl'      — snapshot tab
  Google Sheets: 'macro_intl_hist' — history tab

DESIGN PRINCIPLES
-----------------
· Completely self-contained. Zero imports from fetch_data.py or other modules.
· Safe to call from fetch_data.py at end via run_phase_c().
· All errors caught internally — existing pipeline tabs never touched on failure.
· Per-indicator try/except so one API failure doesn't kill the rest.
· Conservative rate limiting: 1.5s between OECD calls, 1.0s between IMF calls.
· Exponential backoff on 429 / 5xx: 2s → 4s → 8s → 16s → 32s.
· History reuses snapshot OECD call data for most-recent values (no duplicate fetch).

USAGE
-----
Standalone:
    python fetch_macro_international.py

Called from fetch_data.py (add at the very end, after existing Phase blocks):
    try:
        from fetch_macro_international import run_phase_c
        run_phase_c()
    except Exception as e:
        print(f"[Phase C] Non-fatal error: {e}")

OECD API NOTES
--------------
Base URL:  https://stats.oecd.org/SDMX-JSON/data/{dataset}/{key}/OECD
Format:    sdmx-json (SDMX-JSON 1.0)
Rate limit: Not officially published. 1.5s delay is conservative and safe.
Datasets used:
  MEI_CLI  — Main Economic Indicators: Composite Leading Indicators
  MEI      — Main Economic Indicators (CPI, Unemployment, Short-term rates)
  MEI_FIN  — Main Economic Indicators: Financial (fallback for rates)

IMF DataMapper API NOTES
------------------------
Base URL: https://www.imf.org/external/datamapper/api/v1/{indicator}
Returns:  All countries, all years in a single JSON response (annual WEO data).
No authentication required. Includes forward projections for current/next year.
"""

import csv
import os
import time
import json
import requests
import numpy as np
import pandas as pd
from datetime import date, datetime, timedelta

from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build


# ---------------------------------------------------------------------------
# CONFIG
# ---------------------------------------------------------------------------

GOOGLE_CREDENTIALS_JSON = os.environ.get("GOOGLE_CREDENTIALS", "")
SHEET_ID     = "12nKIUGHz5euDbNQPDTVECsJBNwrceRF1ymsQrIe4_ac"

SNAPSHOT_TAB = "macro_intl"
HIST_TAB     = "macro_intl_hist"
SNAPSHOT_CSV = "data/macro_intl.csv"
HIST_CSV     = "data/macro_intl_hist.csv"

# History start floor (Friday spine begins here)
HIST_START   = "2000-01-01"

# API base URLs
OECD_BASE = "https://stats.oecd.org/SDMX-JSON/data"
IMF_BASE  = "https://www.imf.org/external/datamapper/api/v1"

# Rate limiting
OECD_DELAY      = 1.5   # seconds between OECD requests
IMF_DELAY       = 1.0   # seconds between IMF requests
BACKOFF_BASE    = 2     # seconds for first backoff wait
BACKOFF_RETRIES = 5


# ---------------------------------------------------------------------------
# COUNTRY DEFINITIONS
# ---------------------------------------------------------------------------

# OECD statistics country codes → (display name, region)
COUNTRY_META = {
    "AUS":  ("Australia",       "Asia-Pacific"),
    "CAN":  ("Canada",          "North America"),
    "CHE":  ("Switzerland",     "Europe"),
    "CHN":  ("China",           "Asia"),
    "DEU":  ("Germany",         "Europe"),
    "EA19": ("Eurozone",        "Europe"),
    "FRA":  ("France",          "Europe"),
    "GBR":  ("United Kingdom",  "Europe"),
    "ITA":  ("Italy",           "Europe"),
    "JPN":  ("Japan",           "Asia"),
    "USA":  ("United States",   "North America"),
}

# Joined with "+" for OECD API key strings (order matches dict insertion order)
OECD_COUNTRY_STR = "+".join(COUNTRY_META.keys())

# IMF DataMapper country codes → our OECD-aligned codes
IMF_CODE_MAP = {
    "AU": "AUS",
    "CA": "CAN",
    "CH": "CHE",
    "CN": "CHN",
    "DE": "DEU",
    "XM": "EA19",   # Euro Area in IMF DataMapper
    "FR": "FRA",
    "GB": "GBR",
    "IT": "ITA",
    "JP": "JPN",
    "US": "USA",
}


# ---------------------------------------------------------------------------
# OECD INDICATOR DEFINITIONS
# ---------------------------------------------------------------------------
# Each entry: col (short column suffix used in CSV headers), name (display),
#             category, units, notes, dataset (OECD dataset ID), key (series key).
# Key format: {SUBJECT}.{LOCATION_LIST}.{[MEASURE.]FREQUENCY}
# The exact dimension count varies by dataset; LOCATION is always present.

OECD_INDICATORS = [
    {
        "col":      "CLI",
        "name":     "Composite Leading Indicator (CLI)",
        "category": "Leading Indicators",
        "units":    "Index (amplitude adjusted; long-run avg = 100)",
        "notes":    (
            "Above 100 and rising = above-trend expansion; "
            "below 100 and falling = below-trend slowdown"
        ),
        "dataset":  "MEI_CLI",
        "key":      f"LOLITOAA.{OECD_COUNTRY_STR}.M",
    },
    {
        "col":      "CPI",
        "name":     "CPI Headline YoY %",
        "category": "Inflation",
        "units":    "% change year-on-year (SA)",
        "notes":    (
            "All-items CPI, annual growth rate. "
            ">2% = above DM central bank targets; >5% = high-inflation regime"
        ),
        "dataset":  "MEI",
        "key":      f"CPALTT01.{OECD_COUNTRY_STR}.GY.M",
    },
    {
        "col":      "UNEMPLOYMENT",
        "name":     "Unemployment Rate",
        "category": "Labour Market",
        "units":    "% of labour force (SA)",
        "notes":    (
            "Seasonally adjusted total unemployment rate. "
            "Sustained rise = labour market deterioration signal"
        ),
        "dataset":  "MEI",
        "key":      f"UNRTOT.{OECD_COUNTRY_STR}.STSA.M",
    },
    {
        "col":      "RATE_3M",
        "name":     "Short-term Interest Rate (3M)",
        "category": "Monetary Policy",
        "units":    "% per annum",
        "notes":    (
            "3-month interbank rate; proxy for central bank policy rate trajectory. "
            "Rising = tightening cycle; falling = easing"
        ),
        "dataset":  "MEI",
        "key":      f"IR3TIB01.{OECD_COUNTRY_STR}.ST.M",
    },
]


# ---------------------------------------------------------------------------
# IMF INDICATOR DEFINITIONS
# ---------------------------------------------------------------------------
# IMF DataMapper returns all countries and all years in a single API call,
# so one fetch covers both snapshot and full history.

IMF_INDICATORS = [
    {
        "col":      "GDP_GROWTH",
        "name":     "Real GDP Growth (Annual %)",
        "category": "Growth",
        "units":    "% change year-on-year, constant prices",
        "notes":    (
            "IMF World Economic Outlook projections. "
            "Includes forward estimates for current and next year. "
            "Negative = recession-year contraction"
        ),
        "series":   "NGDP_RPCH",
    },
]


# ---------------------------------------------------------------------------
# HTTP HELPER
# ---------------------------------------------------------------------------

def _fetch_with_backoff(url: str, params: dict = None, label: str = "") -> dict | None:
    """
    Generic HTTP GET with exponential backoff on 429 / 5xx responses.
    Returns parsed JSON dict on success, or None on failure.
    """
    for attempt in range(BACKOFF_RETRIES):
        try:
            resp = requests.get(url, params=params, timeout=30)

            if resp.status_code == 200:
                return resp.json()

            elif resp.status_code in (429, 503):
                wait = BACKOFF_BASE ** (attempt + 1)
                print(
                    f"  [{label}] Rate limited (HTTP {resp.status_code}). "
                    f"Backing off {wait}s (attempt {attempt + 1}/{BACKOFF_RETRIES})"
                )
                time.sleep(wait)

            elif resp.status_code >= 500:
                wait = BACKOFF_BASE ** (attempt + 1)
                print(
                    f"  [{label}] Server error {resp.status_code}. "
                    f"Backing off {wait}s (attempt {attempt + 1}/{BACKOFF_RETRIES})"
                )
                time.sleep(wait)

            else:
                print(f"  [{label}] HTTP {resp.status_code} — skipping")
                return None

        except requests.exceptions.Timeout:
            wait = BACKOFF_BASE ** (attempt + 1)
            print(f"  [{label}] Timeout. Backing off {wait}s (attempt {attempt + 1}/{BACKOFF_RETRIES})")
            time.sleep(wait)

        except requests.exceptions.RequestException as e:
            print(f"  [{label}] Request error: {e} — skipping")
            return None

    print(f"  [{label}] All {BACKOFF_RETRIES} attempts failed — skipping")
    return None


# ---------------------------------------------------------------------------
# OECD SDMX-JSON PARSER
# ---------------------------------------------------------------------------

def _parse_oecd_sdmx(data: dict) -> dict:
    """
    Parse an OECD SDMX-JSON response (stats.oecd.org format).

    Locates the LOCATION dimension dynamically, so it handles any dataset
    regardless of how many series dimensions it has (MEI_CLI has 3,
    MEI has 4, etc.).

    Returns:
        {location_code: [(period_str, float_value), ...]}
        Each list is sorted ascending by period string.
    """
    results = {}

    if not data or "dataSets" not in data or not data["dataSets"]:
        return results

    structure   = data.get("structure", {})
    dims        = structure.get("dimensions", {})
    series_dims = dims.get("series", [])
    obs_dims    = dims.get("observation", [])

    # Find the LOCATION dimension's position in the series dimensions list
    loc_dim_pos = None
    loc_id_list = []
    for i, dim in enumerate(series_dims):
        if dim.get("id") == "LOCATION":
            loc_dim_pos = i
            loc_id_list = [v["id"] for v in dim.get("values", [])]
            break

    if loc_dim_pos is None:
        print("  [OECD parser] LOCATION dimension not found in response")
        return results

    # Build list of time period strings from observation dimensions
    time_ids = []
    for dim in obs_dims:
        if dim.get("id") == "TIME_PERIOD":
            time_ids = [v["id"] for v in dim.get("values", [])]
            break

    # Iterate series, accumulate observations per location
    dataset = data["dataSets"][0]
    for series_key, series_obj in dataset.get("series", {}).items():
        parts = series_key.split(":")
        if len(parts) <= loc_dim_pos:
            continue

        loc_idx = int(parts[loc_dim_pos])
        if loc_idx >= len(loc_id_list):
            continue
        loc_code = loc_id_list[loc_idx]

        for obs_idx_str, obs_vals in series_obj.get("observations", {}).items():
            val = obs_vals[0] if obs_vals else None
            if val is None:
                continue
            obs_idx = int(obs_idx_str)
            period  = time_ids[obs_idx] if obs_idx < len(time_ids) else None
            if not period:
                continue
            results.setdefault(loc_code, []).append((period, float(val)))

    # Sort each location's series ascending by period string
    for loc in results:
        results[loc].sort(key=lambda x: x[0])

    return results


# ---------------------------------------------------------------------------
# IMF DATAMAPPER PARSER
# ---------------------------------------------------------------------------

def _parse_imf_datamapper(data: dict, indicator: str) -> dict:
    """
    Parse an IMF DataMapper response.

    Returns:
        {our_country_code: [(year_str, float_value), ...]}
        Each list is sorted ascending by year string.
    """
    results = {}
    values  = data.get("values", {}).get(indicator, {})

    for imf_code, year_data in values.items():
        our_code = IMF_CODE_MAP.get(imf_code)
        if not our_code or not year_data:
            continue

        obs_list = []
        for yr, val in year_data.items():
            try:
                obs_list.append((str(yr), float(val)))
            except (TypeError, ValueError):
                pass

        obs_list.sort(key=lambda x: x[0])
        results[our_code] = obs_list

    return results


# ---------------------------------------------------------------------------
# OECD DATA FETCHERS
# ---------------------------------------------------------------------------

def fetch_oecd_snapshot(indic: dict) -> dict:
    """
    Fetch the last 3 observations for an OECD indicator (all countries).

    Returns:
        {country_code: [(period_str, value), ...]} or {} on failure.
    """
    url    = f"{OECD_BASE}/{indic['dataset']}/{indic['key']}/OECD"
    params = {"format": "sdmx-json", "lastNObservations": 3}
    label  = f"OECD/{indic['col']}"

    print(f"  Fetching {label} (dataset: {indic['dataset']})...")
    data   = _fetch_with_backoff(url, params=params, label=label)

    if data is None:
        print(f"    → No response for {label}")
        return {}

    parsed = _parse_oecd_sdmx(data)
    print(f"    → {len(parsed)} countries returned for {indic['col']}")
    return parsed


def fetch_oecd_history(indic: dict) -> dict:
    """
    Fetch full history (from HIST_START) for an OECD indicator (all countries).

    Returns:
        {country_code: [(period_str, value), ...]} or {} on failure.
    """
    url    = f"{OECD_BASE}/{indic['dataset']}/{indic['key']}/OECD"
    params = {"format": "sdmx-json", "startPeriod": HIST_START[:4]}  # e.g. "2000"
    label  = f"OECD/{indic['col']}/hist"

    print(f"  Fetching {label} (from {HIST_START[:4]})...")
    data   = _fetch_with_backoff(url, params=params, label=label)

    if data is None:
        print(f"    → No response for {label}")
        return {}

    parsed = _parse_oecd_sdmx(data)
    print(f"    → {len(parsed)} countries returned for {indic['col']} history")
    return parsed


# ---------------------------------------------------------------------------
# IMF DATA FETCHER
# ---------------------------------------------------------------------------

def fetch_imf_indicator(indic: dict) -> dict:
    """
    Fetch all years for an IMF DataMapper indicator.
    One call returns the complete time series for all countries.

    Returns:
        {country_code: [(year_str, value), ...]} or {} on failure.
    """
    url   = f"{IMF_BASE}/{indic['series']}"
    label = f"IMF/{indic['col']}"

    print(f"  Fetching {label} (series: {indic['series']})...")
    data  = _fetch_with_backoff(url, label=label)

    if data is None:
        print(f"    → No response for {label}")
        return {}

    parsed = _parse_imf_datamapper(data, indic["series"])
    print(f"    → {len(parsed)} countries returned for {indic['col']}")
    return parsed


# ---------------------------------------------------------------------------
# BUILD SNAPSHOT DATAFRAME
# ---------------------------------------------------------------------------

def build_snapshot(
    oecd_results: dict,   # {col: {country_code: [(period, val), ...]}}
    imf_results:  dict,   # {col: {country_code: [(year, val), ...]}}
) -> pd.DataFrame:
    """
    Build the snapshot DataFrame: one row per country × indicator.

    Columns:
        Country | Country Name | Region | Indicator | Series | Category |
        Units | Latest Value | Prior Value | Change | Last Period |
        Frequency | Source | Notes | Fetched At
    """
    fetched_at = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    rows = []

    def _add_rows(indicator_list, results_dict, source, frequency):
        for indic in indicator_list:
            col        = indic["col"]
            indic_data = results_dict.get(col, {})

            for country_code, (cname, region) in COUNTRY_META.items():
                series     = indic_data.get(country_code, [])
                latest_val = prior_val = last_period = None

                if series:
                    latest_val  = series[-1][1]
                    last_period = series[-1][0]
                    prior_val   = series[-2][1] if len(series) >= 2 else None

                change = None
                if latest_val is not None and prior_val is not None:
                    change = round(latest_val - prior_val, 4)

                rows.append({
                    "Country":      country_code,
                    "Country Name": cname,
                    "Region":       region,
                    "Indicator":    indic["name"],
                    "Series":       col,
                    "Category":     indic["category"],
                    "Units":        indic["units"],
                    "Latest Value": round(latest_val, 4) if latest_val is not None else None,
                    "Prior Value":  round(prior_val, 4)  if prior_val  is not None else None,
                    "Change":       change,
                    "Last Period":  last_period,
                    "Frequency":    frequency,
                    "Source":       source,
                    "Notes":        indic["notes"],
                    "Fetched At":   fetched_at,
                })

    _add_rows(OECD_INDICATORS, oecd_results, "OECD", "Monthly")
    _add_rows(IMF_INDICATORS,  imf_results,  "IMF",  "Annual")

    df = pd.DataFrame(rows)
    n_with_data = int(df["Latest Value"].notna().sum())
    print(f"\n[Phase C] Snapshot: {len(df)} rows total, {n_with_data} with data")
    return df


# ---------------------------------------------------------------------------
# BUILD HISTORY DATAFRAME
# ---------------------------------------------------------------------------

def _last_friday_on_or_before(d: date) -> date:
    """Return the most recent Friday on or before date d."""
    # weekday(): Mon=0 … Fri=4 … Sun=6
    offset = (d.weekday() - 4) % 7   # days since last Friday (0 if d IS Friday)
    return d - timedelta(days=offset)


def _build_friday_spine(start: str, end: date) -> pd.DatetimeIndex:
    """DatetimeIndex of every Friday from start to end (inclusive)."""
    first_friday = _last_friday_on_or_before(
        datetime.strptime(start, "%Y-%m-%d").date()
    )
    return pd.date_range(start=first_friday, end=end, freq="W-FRI")


def _monthly_to_frame(series_dict: dict, col_prefix: str) -> pd.DataFrame:
    """
    Convert OECD monthly series {country: [(period_str, val), ...]} to a DataFrame.
    Period strings are "YYYY-MM"; each is mapped to the last day of that month.
    Returns a DataFrame indexed by date, columns = f"{country}_{col_prefix}".
    """
    frames = []
    for country, obs in series_dict.items():
        if not obs:
            continue
        dates, vals = [], []
        for period, val in obs:
            try:
                # "YYYY-MM" → last day of month
                dt = datetime.strptime(period[:7] + "-01", "%Y-%m-%d")
                if dt.month == 12:
                    eom = dt.replace(day=31)
                else:
                    eom = dt.replace(month=dt.month + 1, day=1) - timedelta(days=1)
                dates.append(eom)
                vals.append(val)
            except ValueError:
                continue
        if dates:
            s = pd.Series(vals, index=pd.DatetimeIndex(dates),
                          name=f"{country}_{col_prefix}")
            frames.append(s)
    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, axis=1)


def _annual_to_frame(series_dict: dict, col_prefix: str) -> pd.DataFrame:
    """
    Convert IMF annual series {country: [(year_str, val), ...]} to a DataFrame.
    Each year is mapped to Dec 31 of that year.
    Returns a DataFrame indexed by date, columns = f"{country}_{col_prefix}".
    """
    frames = []
    for country, obs in series_dict.items():
        if not obs:
            continue
        dates, vals = [], []
        for yr_str, val in obs:
            try:
                dates.append(datetime(int(yr_str), 12, 31))
                vals.append(val)
            except (ValueError, TypeError):
                continue
        if dates:
            s = pd.Series(vals, index=pd.DatetimeIndex(dates),
                          name=f"{country}_{col_prefix}")
            frames.append(s)
    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, axis=1)


def build_history(
    oecd_hist: dict,   # {col: {country_code: [(period, val), ...]}}
    imf_hist:  dict,   # {col: {country_code: [(year, val), ...]}}
) -> pd.DataFrame:
    """
    Build the weekly Friday-spine history DataFrame.

    Rows:    Every Friday from HIST_START to today.
    Columns: {country}_{indicator_col} for all indicators and countries.

    Monthly OECD data is forward-filled to cover all Fridays until the next
    data point arrives. Annual IMF data is forward-filled across all Fridays
    within each calendar year.
    """
    today = date.today()
    spine = _build_friday_spine(HIST_START, today)
    hist  = pd.DataFrame(index=spine)
    hist.index.name = "Date"

    def _merge(raw_df: pd.DataFrame) -> None:
        if raw_df.empty:
            return
        # Combine spine and data dates, forward-fill, reindex back to spine only
        combined = raw_df.reindex(spine.union(raw_df.index)).sort_index()
        combined = combined.ffill().reindex(spine)
        for col in combined.columns:
            hist[col] = combined[col]

    for indic in OECD_INDICATORS:
        col = indic["col"]
        _merge(_monthly_to_frame(oecd_hist.get(col, {}), col))

    for indic in IMF_INDICATORS:
        col = indic["col"]
        _merge(_annual_to_frame(imf_hist.get(col, {}), col))

    print(f"\n[Phase C] History: {len(hist)} rows × {len(hist.columns)} data columns")
    return hist


# ---------------------------------------------------------------------------
# METADATA ROWS FOR HISTORY TAB
# ---------------------------------------------------------------------------

def _build_hist_metadata(columns: list) -> list:
    """
    Build 2 metadata prefix rows for macro_intl_hist (matches macro_us_hist pattern):
      Row 0: Indicator full name
      Row 1: Country name

    columns: list of column names like "AUS_CLI", "EA19_RATE_3M", "CHN_GDP_GROWTH"
    """
    col_name_map     = {i["col"]: i["name"] for i in OECD_INDICATORS + IMF_INDICATORS}
    country_name_map = {k: v[0] for k, v in COUNTRY_META.items()}

    row_indicator = ["Indicator"]
    row_country   = ["Country"]

    for col in columns:
        # Split on first "_" only: "EA19_GDP_GROWTH" → ["EA19", "GDP_GROWTH"]
        parts = col.split("_", 1)
        if len(parts) == 2:
            row_indicator.append(col_name_map.get(parts[1], parts[1]))
            row_country.append(country_name_map.get(parts[0], parts[0]))
        else:
            row_indicator.append(col)
            row_country.append(col)

    return [row_indicator, row_country]


# ---------------------------------------------------------------------------
# SAVE TO CSV
# ---------------------------------------------------------------------------

def save_snapshot_csv(df: pd.DataFrame) -> None:
    """Save snapshot DataFrame to data/macro_intl.csv."""
    os.makedirs("data", exist_ok=True)

    if os.path.exists(SNAPSHOT_CSV):
        try:
            existing = pd.read_csv(SNAPSHOT_CSV)
            cols = ["Country", "Indicator", "Latest Value", "Prior Value", "Change", "Last Period"]
            if existing[cols].equals(df[cols]):
                print(f"[Phase C] Snapshot CSV unchanged — skipping write")
                return
        except Exception:
            pass  # On any comparison error just overwrite

    df.to_csv(SNAPSHOT_CSV, index=False)
    print(f"[Phase C] Written {len(df)} rows to {SNAPSHOT_CSV}")


def save_hist_csv(df: pd.DataFrame) -> None:
    """
    Save history DataFrame to data/macro_intl_hist.csv.
    Writes 2 metadata prefix rows before the header + data rows
    (matches the macro_us_hist.csv format).
    """
    os.makedirs("data", exist_ok=True)

    columns   = list(df.columns)
    meta_rows = _build_hist_metadata(columns)

    # Write metadata rows using csv module (handles commas in indicator names)
    with open(HIST_CSV, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerows(meta_rows)

    # Append pandas data (header + rows) — index is the Date column
    df.to_csv(HIST_CSV, mode="a", date_format="%Y-%m-%d",
              float_format="%.4f", na_rep="")

    print(f"[Phase C] Written {len(df)} rows + {len(meta_rows)} metadata rows to {HIST_CSV}")


# ---------------------------------------------------------------------------
# GOOGLE SHEETS HELPERS
# ---------------------------------------------------------------------------

def _get_sheets_service():
    """Build and return an authenticated Google Sheets service object."""
    creds_dict = json.loads(GOOGLE_CREDENTIALS_JSON)
    creds = Credentials.from_service_account_info(
        creds_dict,
        scopes=["https://www.googleapis.com/auth/spreadsheets"]
    )
    return build("sheets", "v4", credentials=creds)


def _ensure_tab(sheets, tab_name: str) -> None:
    """Create the named tab if it doesn't already exist."""
    meta     = sheets.spreadsheets().get(spreadsheetId=SHEET_ID).execute()
    existing = [s["properties"]["title"] for s in meta.get("sheets", [])]
    if tab_name not in existing:
        body = {"requests": [{"addSheet": {"properties": {"title": tab_name}}}]}
        sheets.spreadsheets().batchUpdate(spreadsheetId=SHEET_ID, body=body).execute()
        print(f"[Phase C] Created tab '{tab_name}'")
    else:
        print(f"[Phase C] Tab '{tab_name}' exists — will overwrite")


def _write_tab(sheets, tab_name: str, values: list) -> None:
    """Clear existing content and write new values to a tab."""
    sheets.spreadsheets().values().clear(
        spreadsheetId=SHEET_ID,
        range=f"{tab_name}!A:ZZ"
    ).execute()
    sheets.spreadsheets().values().update(
        spreadsheetId=SHEET_ID,
        range=f"{tab_name}!A1",
        valueInputOption="RAW",
        body={"values": values}
    ).execute()
    print(f"[Phase C] Written {len(values)} rows to '{tab_name}' tab")


# ---------------------------------------------------------------------------
# PUSH TO GOOGLE SHEETS
# ---------------------------------------------------------------------------

def push_snapshot_to_sheets(df: pd.DataFrame) -> None:
    """Push snapshot DataFrame to the 'macro_intl' Google Sheets tab."""
    if not GOOGLE_CREDENTIALS_JSON:
        print("[Phase C] GOOGLE_CREDENTIALS not set — skipping snapshot Sheets push")
        return
    if df.empty:
        return
    try:
        service   = _get_sheets_service()
        sheets    = service.spreadsheets()
        _ensure_tab(sheets, SNAPSHOT_TAB)
        header    = list(df.columns)
        data_rows = df.fillna("").astype(str).values.tolist()
        _write_tab(sheets, SNAPSHOT_TAB, [header] + data_rows)
    except json.JSONDecodeError as e:
        print(f"[Phase C] GOOGLE_CREDENTIALS parse error: {e} — skipping snapshot push")
    except Exception as e:
        print(f"[Phase C] Snapshot Sheets push failed: {e} — skipping")


def push_hist_to_sheets(df: pd.DataFrame) -> None:
    """Push history DataFrame to the 'macro_intl_hist' Google Sheets tab."""
    if not GOOGLE_CREDENTIALS_JSON:
        print("[Phase C] GOOGLE_CREDENTIALS not set — skipping hist Sheets push")
        return
    if df.empty:
        return
    try:
        service  = _get_sheets_service()
        sheets   = service.spreadsheets()
        _ensure_tab(sheets, HIST_TAB)

        columns   = list(df.columns)
        meta_rows = _build_hist_metadata(columns)
        header    = ["Date"] + columns

        data_rows = []
        for idx, row in df.iterrows():
            date_str = idx.strftime("%Y-%m-%d")
            vals = []
            for v in row.values:
                if isinstance(v, float) and np.isnan(v):
                    vals.append("")
                elif isinstance(v, float):
                    vals.append(str(round(v, 4)))
                else:
                    vals.append(str(v))
            data_rows.append([date_str] + vals)

        _write_tab(sheets, HIST_TAB, meta_rows + [header] + data_rows)

    except json.JSONDecodeError as e:
        print(f"[Phase C] GOOGLE_CREDENTIALS parse error: {e} — skipping hist push")
    except Exception as e:
        print(f"[Phase C] Hist Sheets push failed: {e} — skipping")


# ---------------------------------------------------------------------------
# MAIN ENTRY POINT
# ---------------------------------------------------------------------------

def run_phase_c() -> None:
    """
    Full Phase C run. Safe to call from fetch_data.py or as a standalone script.
    All errors are caught internally — the existing pipeline is never affected.
    """
    print("\n" + "=" * 60)
    print("Phase C — International Macro Indicators")
    print("=" * 60)

    start_time = time.time()

    try:
        # ------------------------------------------------------------------
        # SNAPSHOT: fetch last 3 observations per OECD indicator
        # ------------------------------------------------------------------
        print("\n[Snapshot] Fetching OECD indicators...")
        oecd_snap = {}
        for i, indic in enumerate(OECD_INDICATORS):
            try:
                oecd_snap[indic["col"]] = fetch_oecd_snapshot(indic)
            except Exception as e:
                print(f"  [Phase C] OECD {indic['col']} snapshot failed: {e}")
                oecd_snap[indic["col"]] = {}
            if i < len(OECD_INDICATORS) - 1:
                time.sleep(OECD_DELAY)

        # ------------------------------------------------------------------
        # SNAPSHOT: fetch IMF indicators (each call returns full history,
        #           so this doubles as the history fetch for IMF series)
        # ------------------------------------------------------------------
        print("\n[Snapshot] Fetching IMF indicators...")
        imf_data = {}
        for i, indic in enumerate(IMF_INDICATORS):
            try:
                time.sleep(IMF_DELAY)
                imf_data[indic["col"]] = fetch_imf_indicator(indic)
            except Exception as e:
                print(f"  [Phase C] IMF {indic['col']} fetch failed: {e}")
                imf_data[indic["col"]] = {}

        # ------------------------------------------------------------------
        # Build and save snapshot
        # ------------------------------------------------------------------
        snap_df = build_snapshot(oecd_snap, imf_data)
        if not snap_df.empty:
            save_snapshot_csv(snap_df)
            push_snapshot_to_sheets(snap_df)

        # ------------------------------------------------------------------
        # HISTORY: fetch full OECD history (separate calls with startPeriod)
        # ------------------------------------------------------------------
        print("\n[History] Fetching OECD full history (from 2000)...")
        oecd_hist = {}
        for i, indic in enumerate(OECD_INDICATORS):
            try:
                oecd_hist[indic["col"]] = fetch_oecd_history(indic)
            except Exception as e:
                print(f"  [Phase C] OECD {indic['col']} history failed: {e}")
                oecd_hist[indic["col"]] = {}
            if i < len(OECD_INDICATORS) - 1:
                time.sleep(OECD_DELAY)

        # IMF DataMapper already returned the full history in the snapshot call
        print("\n[History] Reusing IMF data (DataMapper returns all years in one call)...")
        imf_hist = imf_data

        # ------------------------------------------------------------------
        # Build and save history
        # ------------------------------------------------------------------
        hist_df = build_history(oecd_hist, imf_hist)
        if not hist_df.empty:
            save_hist_csv(hist_df)
            push_hist_to_sheets(hist_df)

        elapsed = round(time.time() - start_time, 1)
        print(f"\n[Phase C] Completed in {elapsed}s")

    except Exception as e:
        elapsed = round(time.time() - start_time, 1)
        print(f"\n[Phase C] Unexpected error after {elapsed}s: {e}")
        print("[Phase C] Existing pipeline data is unaffected")


if __name__ == "__main__":
    run_phase_c()
