"""
fetch_macro_international.py
============================
Phase C — International Macro Indicators
Market Dashboard Expansion

WHAT THIS MODULE DOES
---------------------
Fetches macro indicators for 11 major economies from three free public APIs:

  OECD Data Explorer REST API (sdmx.oecd.org — no key required, CSV format):
    · Composite Leading Indicator (CLI)   — monthly, DF_CLI dataflow
    · Unemployment Rate                   — monthly, DF_IALFS_UNE_M dataflow
    · Short-term Interest Rate (3M)       — monthly, DF_FINMARK dataflow

  World Bank Open Data API (api.worldbank.org — no key required):
    · CPI Headline YoY %                  — annual (FP.CPI.TOTL.ZG)

  IMF DataMapper REST API (imf.org — no key required):
    · Real GDP Growth % (annual WEO)      — annual, includes projections

Countries: AUS, CAN, CHE, CHN, DEU, EA19, FRA, GBR, ITA, JPN, USA
  Note: CHN and EA19 have partial coverage (absent from OECD LFS unemployment).
  Note: EA19 = Eurozone. Equivalent codes on other sources:
        World Bank → EMU; IMF DataMapper → EURO.

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
· OECD rate limit: 20 calls/hour. Module makes at most 6 OECD calls per run
  (3 snapshot + 3 history), well within budget.
· Exponential backoff on 429 / 5xx: 2s → 4s → 8s → 16s → 32s.
· IMF DataMapper returns full history in one call (snapshot = history).

API MIGRATION NOTE (OECD)
--------------------------
The legacy stats.oecd.org SDMX-JSON API was deprecated in June/July 2024.
This module uses the new sdmx.oecd.org REST API with format=csv.
New dataflow IDs:
  CLI:          OECD.SDD.STES,DSD_STES@DF_CLI,4.1
  Unemployment: OECD.SDD.TPS,DSD_LFS@DF_IALFS_UNE_M,1.0
  Rates:        OECD.SDD.STES,DSD_STES@DF_FINMARK,4.0

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
"""

import csv as csv_module
import os
import time
import json
import requests
import pandas as pd
from datetime import date, datetime, timedelta, timezone

from sources.base import (
    build_friday_spine,
    fetch_with_backoff,
    get_sheets_service,
    last_friday_on_or_before,
    push_df_to_sheets,
)
from sources import fred as fred_src
from sources import oecd as oecd_src


# ---------------------------------------------------------------------------
# CONFIG
# ---------------------------------------------------------------------------

GOOGLE_CREDENTIALS_JSON = os.environ.get("GOOGLE_CREDENTIALS", "")
FRED_API_KEY = os.environ.get("FRED_API_KEY", "")
SHEET_ID     = "12nKIUGHz5euDbNQPDTVECsJBNwrceRF1ymsQrIe4_ac"

SNAPSHOT_TAB = "macro_intl"
HIST_TAB     = "macro_intl_hist"
SNAPSHOT_CSV = "data/macro_intl.csv"
HIST_CSV     = "data/macro_intl_hist.csv"

HIST_START   = "1960-01-01"   # history floor — OECD CLI/rates back to ~1960s; maximise range

# API base URLs
WB_BASE   = "https://api.worldbank.org/v2/country"
IMF_BASE  = "https://www.imf.org/external/datamapper/api/v1"

# Rate limits / delays
OECD_DELAY      = 4.0   # seconds between OECD calls (max 20/hour = 1 per 3min; 4s is safe)
WB_DELAY        = 1.0   # seconds between World Bank calls
IMF_DELAY       = 1.0   # seconds between IMF calls
BACKOFF_BASE    = 2     # seconds for first backoff
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

# IMF DataMapper country codes → our OECD-aligned codes
# IMF uses 3-letter ISO codes for countries; "EURO" for Euro Area (entity code
# visible at https://www.imf.org/external/datamapper/profile/EURO). The legacy
# "XM" code returns no data from the v1 DataMapper API.
IMF_CODE_MAP = {
    "AUS":  "AUS",
    "CAN":  "CAN",
    "CHE":  "CHE",
    "CHN":  "CHN",
    "DEU":  "DEU",
    "EURO": "EA19",   # IMF DataMapper uses "EURO" for Euro Area
    "FRA":  "FRA",
    "GBR":  "GBR",
    "ITA":  "ITA",
    "JPN":  "JPN",
    "USA":  "USA",
}

# World Bank country codes → our codes
# World Bank uses ISO Alpha-3; EMU for Euro Area
WB_CODE_MAP = {
    "AUS": "AUS",
    "CAN": "CAN",
    "CHE": "CHE",
    "CHN": "CHN",
    "DEU": "DEU",
    "EMU": "EA19",   # World Bank EMU = Euro Area
    "FRA": "FRA",
    "GBR": "GBR",
    "ITA": "ITA",
    "JPN": "JPN",
    "USA": "USA",
}
# Semicolon-separated for World Bank URL
WB_COUNTRIES = "AUS;CAN;CHE;CHN;DEU;EMU;FRA;GBR;ITA;JPN;USA"


# ---------------------------------------------------------------------------
# LIBRARY LOADERS
# ---------------------------------------------------------------------------
# Indicator definitions are in four CSV files:
#   macro_library_oecd.csv       → OECD_INDICATORS
#   macro_library_worldbank.csv  → WB_INDICATORS
#   macro_library_imf.csv        → IMF_INDICATORS
#   macro_library_fred.csv       → FRED_INTL_INDICATORS (rows where country != "")
#
# Add new indicators by editing the relevant CSV — no Python changes required.
# Adding a new data source: create a new macro_library_<source>.csv file,
# write a loader function, and add fetch/validation logic below.

import pathlib as _pl

_WB_CSV   = _pl.Path(__file__).parent / "data" / "macro_library_worldbank.csv"
_IMF_CSV  = _pl.Path(__file__).parent / "data" / "macro_library_imf.csv"




def _load_wb_indicators() -> list:
    """Load World Bank indicators from macro_library_worldbank.csv."""
    df = pd.read_csv(_WB_CSV, dtype=str, keep_default_na=False)
    df["sort_key"] = pd.to_numeric(df["sort_key"], errors="coerce").fillna(0)
    result = []
    for _, row in df.sort_values("sort_key").iterrows():
        col = row["col"].strip() if row["col"].strip() else row["series_id"]
        result.append({
            "col":       col,
            "name":      row["name"],
            "category":  row["category"],
            "units":     row["units"],
            "frequency": row["frequency"],
            "notes":     row["notes"],
            "wb_id":     row["series_id"],
        })
    return result


def _load_imf_indicators() -> list:
    """Load IMF indicators from macro_library_imf.csv."""
    df = pd.read_csv(_IMF_CSV, dtype=str, keep_default_na=False)
    df["sort_key"] = pd.to_numeric(df["sort_key"], errors="coerce").fillna(0)
    result = []
    for _, row in df.sort_values("sort_key").iterrows():
        col = row["col"].strip() if row["col"].strip() else row["series_id"]
        result.append({
            "col":       col,
            "name":      row["name"],
            "category":  row["category"],
            "units":     row["units"],
            "frequency": row["frequency"],
            "notes":     row["notes"],
            "series":    row["series_id"],   # IMF fetch uses "series" key
        })
    return result


# Module-level globals — populated from CSVs at import time.
# All existing code that references these lists works unchanged.
OECD_INDICATORS      = oecd_src.load_library()
WB_INDICATORS        = _load_wb_indicators()
IMF_INDICATORS       = _load_imf_indicators()
FRED_INTL_INDICATORS = fred_src.load_intl_library()


# ---------------------------------------------------------------------------
# LIBRARY VALIDATION
# ---------------------------------------------------------------------------

def _validate_wb_library() -> list:
    """
    Validate World Bank indicator IDs against the WB API.
    Prints CSV name vs official WB indicator name for spot-checking.
    Returns a list of warning strings (empty = all indicators found).
    """
    warnings = []
    total = len(WB_INDICATORS)
    print(f"\nValidating {total} indicator(s) in macro_library_worldbank.csv...")
    for indic in WB_INDICATORS:
        wb_id = indic["wb_id"]
        try:
            resp = requests.get(
                f"https://api.worldbank.org/v2/indicator/{wb_id}",
                params={"format": "json"},
                timeout=15,
            )
            time.sleep(WB_DELAY)
            if resp.status_code == 200:
                data = resp.json()
                if data and len(data) > 1 and data[1]:
                    official = data[1][0].get("name", "")
                    print(f"  [OK] WB {wb_id}")
                    print(f"    csv: {indic['name']}")
                    print(f"    wb : {official}")
                else:
                    warnings.append(
                        f"WB '{wb_id}' not found — verify series_id "
                        f"in macro_library_worldbank.csv  (csv name: '{indic['name']}')"
                    )
            else:
                print(f"  [SKIP] WB {wb_id}: HTTP {resp.status_code} — cannot validate")
        except Exception as e:
            print(f"  [SKIP] WB {wb_id}: validation error — {e}")
    return warnings


def _validate_imf_library() -> list:
    """
    Validate IMF DataMapper indicator IDs.
    Prints CSV name vs official IMF label for spot-checking.
    Returns a list of warning strings (empty = all indicators found).
    """
    warnings = []
    total = len(IMF_INDICATORS)
    print(f"\nValidating {total} indicator(s) in macro_library_imf.csv...")
    for indic in IMF_INDICATORS:
        imf_id = indic["series"]
        try:
            resp = requests.get(
                f"{IMF_BASE}/indicator/{imf_id}",
                timeout=15,
            )
            time.sleep(IMF_DELAY)
            if resp.status_code == 200:
                data = resp.json()
                label = data.get("indicator", {}).get(imf_id, {}).get("label", "")
                if label:
                    print(f"  [OK] IMF {imf_id}")
                    print(f"    csv: {indic['name']}")
                    print(f"    imf: {label}")
                else:
                    warnings.append(
                        f"IMF '{imf_id}' not found in API response — verify series_id "
                        f"in macro_library_imf.csv  (csv name: '{indic['name']}')"
                    )
            else:
                print(f"  [SKIP] IMF {imf_id}: HTTP {resp.status_code} — cannot validate")
        except Exception as e:
            print(f"  [SKIP] IMF {imf_id}: validation error — {e}")
    return warnings


def _validate_fred_intl_library() -> list:
    """Validate FRED international indicator IDs via the shared FRED helper."""
    indicators = [
        {"series_id": indic["fred_id"], "name": indic["name"]}
        for indic in FRED_INTL_INDICATORS
    ]
    return fred_src.validate_series(indicators, FRED_API_KEY, label_prefix="FRED International")


# ---------------------------------------------------------------------------
# HTTP HELPER
# ---------------------------------------------------------------------------

def _fetch_with_backoff(
    url: str,
    params: dict = None,
    label: str = "",
    accept_csv: bool = False,
) -> dict | str | None:
    """Local wrapper so callers don't need to pass module-level retry config."""
    return fetch_with_backoff(
        url,
        params=params,
        label=label,
        accept_csv=accept_csv,
        retries=BACKOFF_RETRIES,
        backoff_base=BACKOFF_BASE,
    )


# ---------------------------------------------------------------------------
# WORLD BANK JSON PARSER
# ---------------------------------------------------------------------------

def _parse_worldbank(data: list, label: str = "") -> dict:
    """
    Parse World Bank API response [pagination_metadata, [observations]].

    Returns:
        {our_country_code: [(year_str, float_value), ...]} sorted ascending.
    """
    if not data or len(data) < 2 or not data[1]:
        print(f"  [{label}] Empty or unexpected World Bank response")
        return {}

    results = {}
    for obs in data[1]:
        val = obs.get("value")
        if val is None:
            continue
        # World Bank uses ISO 3-letter codes in countryiso3code
        iso3 = obs.get("countryiso3code", "")
        our_code = WB_CODE_MAP.get(iso3)
        if not our_code:
            continue
        yr  = str(obs.get("date", ""))
        results.setdefault(our_code, []).append((yr, float(val)))

    for k in results:
        results[k].sort(key=lambda x: x[0])

    print(f"    → {len(results)} countries parsed from World Bank")
    return results


# ---------------------------------------------------------------------------
# IMF DATAMAPPER PARSER
# ---------------------------------------------------------------------------

def _parse_imf_datamapper(data: dict, indicator: str, label: str = "") -> dict:
    """
    Parse IMF DataMapper response.
    IMF uses 3-letter ISO codes for countries and "EURO" for Euro Area.

    Returns:
        {our_country_code: [(year_str, float_value), ...]} sorted ascending.
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

    print(f"    → {len(results)} countries parsed from IMF")
    return results


# ---------------------------------------------------------------------------
# FRED INTERNATIONAL DATA FETCHERS (thin wrappers over sources.fred)
# ---------------------------------------------------------------------------

def fetch_fred_intl_snapshot(indic: dict) -> dict:
    """Last 3 monthly observations → {country_code: [(YYYY-MM, val), ...]}."""
    label = f"FRED/{indic['col']}"
    print(f"  Fetching {label} ({indic['fred_id']})...")
    data = fred_src.fetch_observations(
        indic["fred_id"], FRED_API_KEY,
        limit=3, sort_order="desc", label=label,
    )
    if data is None:
        return {}
    # Snapshot wants ascending order to match the history shape.
    data = {"observations": list(reversed(data.get("observations", [])))}
    result = fred_src.parse_monthly_by_country(data, indic["country"])
    if result:
        vals = result[indic["country"]]
        print(f"    → {len(vals)} obs; latest: {vals[-1] if vals else 'none'}")
    else:
        print(f"    → No data")
    return result


def fetch_fred_intl_history(indic: dict, start: str) -> dict:
    """Full history from `start` → {country_code: [(YYYY-MM, val), ...]}."""
    label = f"FRED/{indic['col']}/hist"
    print(f"  Fetching {label} ({indic['fred_id']})...")
    data = fred_src.fetch_observations(
        indic["fred_id"], FRED_API_KEY,
        start=start, limit=100_000, sort_order="asc", label=label,
    )
    if data is None:
        return {}
    result = fred_src.parse_monthly_by_country(data, indic["country"])
    if result:
        vals = result[indic["country"]]
        print(f"    → {len(vals)} obs "
              f"({vals[0][0] if vals else '?'} → {vals[-1][0] if vals else '?'})")
    else:
        print(f"    → No data")
    return result


# ---------------------------------------------------------------------------
# OECD DATA FETCHERS (thin wrappers over sources.oecd)
# ---------------------------------------------------------------------------

def fetch_oecd_snapshot(indic: dict) -> dict:
    """Last 3 observations per country for one OECD indicator."""
    return oecd_src.fetch_snapshot(
        indic, retries=BACKOFF_RETRIES, backoff_base=BACKOFF_BASE,
    )


def fetch_oecd_history(indic: dict) -> dict:
    """Full history from HIST_START for one OECD indicator."""
    return oecd_src.fetch_history(
        indic, HIST_START, retries=BACKOFF_RETRIES, backoff_base=BACKOFF_BASE,
    )


# ---------------------------------------------------------------------------
# WORLD BANK DATA FETCHERS
# ---------------------------------------------------------------------------

def fetch_wb_snapshot(indic: dict) -> dict:
    """
    Fetch last 5 annual observations from World Bank for one indicator.
    Returns {our_country_code: [(year_str, val), ...]} or {} on failure.
    """
    url   = f"{WB_BASE}/{WB_COUNTRIES}/indicator/{indic['wb_id']}"
    label = f"WB/{indic['col']}"
    print(f"  Fetching {label}...")

    data  = _fetch_with_backoff(
        url,
        params={"format": "json", "mrv": 5, "per_page": 200},
        label=label,
    )
    if data is None:
        return {}
    return _parse_worldbank(data, label=label)


def fetch_wb_history(indic: dict) -> dict:
    """
    Fetch full history from 2000 from World Bank for one indicator.
    Returns {our_country_code: [(year_str, val), ...]} or {} on failure.
    """
    url   = f"{WB_BASE}/{WB_COUNTRIES}/indicator/{indic['wb_id']}"
    label = f"WB/{indic['col']}/hist"
    print(f"  Fetching {label}...")

    data  = _fetch_with_backoff(
        url,
        params={"format": "json", "date": "2000:2025", "per_page": 1000},
        label=label,
    )
    if data is None:
        return {}
    return _parse_worldbank(data, label=label)


# ---------------------------------------------------------------------------
# IMF DATA FETCHER
# ---------------------------------------------------------------------------

def fetch_imf_indicator(indic: dict) -> dict:
    """
    Fetch full history for one IMF DataMapper indicator (all years, all countries).
    One API call returns everything — snapshot and history come from the same response.
    Returns {our_country_code: [(year_str, val), ...]} or {} on failure.
    """
    url   = f"{IMF_BASE}/{indic['series']}"
    label = f"IMF/{indic['col']}"
    print(f"  Fetching {label}...")

    data  = _fetch_with_backoff(url, label=label)
    if data is None:
        return {}
    return _parse_imf_datamapper(data, indic["series"], label=label)


# ---------------------------------------------------------------------------
# BUILD SNAPSHOT DATAFRAME
# ---------------------------------------------------------------------------

def build_snapshot(
    oecd_results:      dict,   # {col: {country_code: [(period, val), ...]}}
    wb_results:        dict,   # {col: {country_code: [(year, val), ...]}}
    imf_results:       dict,   # {col: {country_code: [(year, val), ...]}}
    fred_intl_results: dict = None,  # {col: {country_code: [(period, val), ...]}}
) -> pd.DataFrame:
    """
    Build the snapshot DataFrame: one row per country × indicator.

    Columns:
        Country | Country Name | Region | Indicator | Series | Category |
        Units | Latest Value | Prior Value | Change | Last Period |
        Frequency | Source | Notes | Fetched At
    """
    fetched_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
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
    _add_rows(WB_INDICATORS,   wb_results,   "World Bank", "Annual")
    _add_rows(IMF_INDICATORS,  imf_results,  "IMF",  "Annual")

    # FRED international indicators (country-specific; only include the relevant country row)
    if fred_intl_results:
        for indic in FRED_INTL_INDICATORS:
            col         = indic["col"]
            country_code = indic["country"]
            cname, region = COUNTRY_META.get(country_code, (country_code, ""))
            series       = (fred_intl_results.get(col) or {}).get(country_code, [])

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
                "Frequency":    indic["frequency"],
                "Source":       indic["source"],
                "Notes":        indic["notes"],
                "Fetched At":   fetched_at,
            })

    df = pd.DataFrame(rows)
    n_with_data = int(df["Latest Value"].notna().sum())
    print(f"\n[Phase C] Snapshot: {len(df)} rows total, {n_with_data} with data")
    return df


# ---------------------------------------------------------------------------
# BUILD HISTORY DATAFRAME
# ---------------------------------------------------------------------------

def _monthly_to_frame(series_dict: dict, col_prefix: str) -> pd.DataFrame:
    """
    Convert OECD monthly series {country: [("YYYY-MM", val), ...]} to a DataFrame.
    Each period is mapped to the last day of that month.
    """
    frames = []
    for country, obs in series_dict.items():
        if not obs:
            continue
        dates, vals = [], []
        for period, val in obs:
            try:
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
    Convert annual series {country: [("YYYY", val), ...]} to a DataFrame.
    Each year is mapped to Dec 31 of that year.
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
    oecd_hist:      dict,
    wb_hist:        dict,
    imf_hist:       dict,
    fred_intl_hist: dict = None,
) -> pd.DataFrame:
    """
    Build the weekly Friday-spine history DataFrame.
    Monthly OECD data and annual WB/IMF data are forward-filled onto the spine.
    """
    today = date.today()
    spine = build_friday_spine(HIST_START, today)
    hist  = pd.DataFrame(index=spine)
    hist.index.name = "Date"

    def _merge(raw_df: pd.DataFrame) -> None:
        if raw_df.empty:
            return
        combined = raw_df.reindex(spine.union(raw_df.index)).sort_index()
        combined = combined.ffill().reindex(spine)
        for col in combined.columns:
            hist[col] = combined[col]

    for indic in OECD_INDICATORS:
        _merge(_monthly_to_frame(oecd_hist.get(indic["col"], {}), indic["col"]))

    for indic in WB_INDICATORS:
        _merge(_annual_to_frame(wb_hist.get(indic["col"], {}), indic["col"]))

    for indic in IMF_INDICATORS:
        _merge(_annual_to_frame(imf_hist.get(indic["col"], {}), indic["col"]))

    if fred_intl_hist:
        for indic in FRED_INTL_INDICATORS:
            country_data = (fred_intl_hist.get(indic["col"]) or {})
            _merge(_monthly_to_frame(country_data, indic["col"]))

    print(f"\n[Phase C] History: {len(hist)} rows × {len(hist.columns)} data columns")
    return hist


# ---------------------------------------------------------------------------
# METADATA ROWS FOR HISTORY TAB
# ---------------------------------------------------------------------------

def _build_hist_metadata(columns: list) -> list:
    """
    Build metadata prefix rows for macro_intl_hist.  Row order (label in col A):
      1. Column ID      — internal column name (e.g. USA_GDP_GROWTH)
      2. Source Code    — upstream API series identifier
                          OECD: indicator col (CLI / UNEMPLOYMENT / RATE_3M)
                          World Bank: wb_id (FP.CPI.TOTL.ZG)
                          IMF: series (NGDP_RPCH)
                          FRED: fred_id (e.g. CSCICP03EZM665S)
      3. Source         — OECD / World Bank / IMF / FRED
      4. Indicator      — human-readable indicator name
      5. Country        — country display name
      6. Units          — measurement units
      7. Frequency      — "Weekly (from Monthly ffill)" etc.
      8. Last Updated   — UTC timestamp of this run
    """
    all_indics   = OECD_INDICATORS + WB_INDICATORS + IMF_INDICATORS + FRED_INTL_INDICATORS
    country_map  = {k: v[0] for k, v in COUNTRY_META.items()}
    run_ts       = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    # Build per-indicator-col lookup maps
    col_name_map    = {}
    col_source_map  = {}
    col_srccode_map = {}
    col_units_map   = {}
    col_freq_map    = {}

    _freq_label = {
        "Monthly":  "Weekly (monthly → ffill)",
        "Annual":   "Weekly (annual → ffill)",
    }

    for indic in OECD_INDICATORS:
        c = indic["col"]
        col_name_map[c]    = indic["name"]
        col_source_map[c]  = "OECD"
        col_srccode_map[c] = c                          # OECD internal col code
        col_units_map[c]   = indic.get("units", "")
        col_freq_map[c]    = _freq_label.get(indic.get("frequency", ""), indic.get("frequency", ""))

    for indic in WB_INDICATORS:
        c = indic["col"]
        col_name_map[c]    = indic["name"]
        col_source_map[c]  = "World Bank"
        col_srccode_map[c] = indic["wb_id"]
        col_units_map[c]   = indic.get("units", "")
        col_freq_map[c]    = _freq_label.get(indic.get("frequency", ""), indic.get("frequency", ""))

    for indic in IMF_INDICATORS:
        c = indic["col"]
        col_name_map[c]    = indic["name"]
        col_source_map[c]  = "IMF"
        col_srccode_map[c] = indic["series"]
        col_units_map[c]   = indic.get("units", "")
        col_freq_map[c]    = _freq_label.get(indic.get("frequency", ""), indic.get("frequency", ""))

    for indic in FRED_INTL_INDICATORS:
        c = indic["col"]
        col_name_map[c]    = indic["name"]
        col_source_map[c]  = "FRED"
        col_srccode_map[c] = indic.get("fred_id", c)
        col_units_map[c]   = indic.get("units", "")
        col_freq_map[c]    = _freq_label.get(indic.get("frequency", ""), indic.get("frequency", ""))

    row_col_id    = ["Column ID"]
    row_src_code  = ["Source Code"]
    row_source    = ["Source"]
    row_indicator = ["Indicator"]
    row_country   = ["Country"]
    row_units     = ["Units"]
    row_frequency = ["Frequency"]
    row_updated   = ["Last Updated"]

    for col in columns:
        # "EA19_GDP_GROWTH".split("_", 1) → ["EA19", "GDP_GROWTH"]
        parts = col.split("_", 1)
        if len(parts) == 2:
            country_code  = parts[0]
            indicator_col = parts[1]
        else:
            country_code  = col
            indicator_col = col

        row_col_id.append(col)
        row_src_code.append(col_srccode_map.get(indicator_col, indicator_col))
        row_source.append(col_source_map.get(indicator_col, ""))
        row_indicator.append(col_name_map.get(indicator_col, indicator_col))
        row_country.append(country_map.get(country_code, country_code))
        row_units.append(col_units_map.get(indicator_col, ""))
        row_frequency.append(col_freq_map.get(indicator_col, ""))
        row_updated.append(run_ts)

    return [
        row_col_id, row_src_code, row_source,
        row_indicator, row_country,
        row_units, row_frequency, row_updated,
    ]


# ---------------------------------------------------------------------------
# SAVE TO CSV
# ---------------------------------------------------------------------------

def save_snapshot_csv(df: pd.DataFrame) -> None:
    os.makedirs("data", exist_ok=True)
    if os.path.exists(SNAPSHOT_CSV):
        try:
            existing = pd.read_csv(SNAPSHOT_CSV)
            cols = ["Country", "Indicator", "Latest Value", "Prior Value",
                    "Change", "Last Period"]
            if existing[cols].equals(df[cols]):
                print(f"[Phase C] Snapshot CSV unchanged — skipping write")
                return
        except Exception:
            pass
    df.to_csv(SNAPSHOT_CSV, index=False)
    print(f"[Phase C] Written {len(df)} rows to {SNAPSHOT_CSV}")


def save_hist_csv(df: pd.DataFrame) -> None:
    """
    Save history DataFrame with 2 metadata prefix rows (matches macro_us_hist format).
    """
    os.makedirs("data", exist_ok=True)
    columns   = list(df.columns)
    meta_rows = _build_hist_metadata(columns)
    meta_rows = [[""] + row for row in meta_rows]

    # Reset index so Date becomes a column, then insert row_id in column A
    df_out = df.reset_index()
    df_out.rename(columns={df_out.columns[0]: "Date"}, inplace=True)
    df_out.insert(0, "row_id", range(1, len(df_out) + 1))

    with open(HIST_CSV, "w", newline="") as f:
        writer = csv_module.writer(f)
        writer.writerows(meta_rows)

    df_out.to_csv(HIST_CSV, mode="a", date_format="%Y-%m-%d",
                  float_format="%.4f", na_rep="", index=False)

    print(f"[Phase C] Written {len(df)} rows + {len(meta_rows)} metadata rows to {HIST_CSV}")


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
            label="Phase C",
        )
    except json.JSONDecodeError as e:
        print(f"[Phase C] Credentials parse error: {e}")
    except Exception as e:
        print(f"[Phase C] Snapshot Sheets push failed: {e}")


def push_hist_to_sheets(df: pd.DataFrame) -> None:
    if df.empty:
        return
    try:
        columns   = list(df.columns)
        meta_rows = _build_hist_metadata(columns)
        # One leading empty cell aligns metadata rows with the row_id column.
        meta_rows = [[""] + row for row in meta_rows]

        df_out = df.reset_index()
        df_out.rename(columns={df_out.columns[0]: "Date"}, inplace=True)
        df_out["Date"] = df_out["Date"].dt.strftime("%Y-%m-%d")
        df_out.insert(0, "row_id", range(1, len(df_out) + 1))

        push_df_to_sheets(
            get_sheets_service(GOOGLE_CREDENTIALS_JSON),
            SHEET_ID,
            HIST_TAB,
            df_out,
            label="Phase C",
            prefix_rows=meta_rows,
        )
    except json.JSONDecodeError as e:
        print(f"[Phase C] Credentials parse error: {e}")
    except Exception as e:
        print(f"[Phase C] Hist Sheets push failed: {e}")


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
        # VALIDATE LIBRARIES
        # ------------------------------------------------------------------
        all_warnings = []
        all_warnings += _validate_wb_library()
        all_warnings += _validate_imf_library()
        all_warnings += _validate_fred_intl_library()
        if all_warnings:
            print("\n" + "!" * 60)
            print("MACRO LIBRARY VALIDATION — ACTION REQUIRED:")
            for w in all_warnings:
                print(f"  [WARN] {w}")
            print("!" * 60 + "\n")

        # ------------------------------------------------------------------
        # SNAPSHOT: OECD (last 3 observations per indicator)
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
        # SNAPSHOT: World Bank
        # ------------------------------------------------------------------
        print("\n[Snapshot] Fetching World Bank indicators...")
        wb_snap = {}
        for i, indic in enumerate(WB_INDICATORS):
            try:
                time.sleep(WB_DELAY)
                wb_snap[indic["col"]] = fetch_wb_snapshot(indic)
            except Exception as e:
                print(f"  [Phase C] WB {indic['col']} snapshot failed: {e}")
                wb_snap[indic["col"]] = {}

        # ------------------------------------------------------------------
        # SNAPSHOT: IMF (returns full history — reused for hist tab)
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
        # SNAPSHOT: FRED international indicators (e.g. EA Consumer Confidence)
        # ------------------------------------------------------------------
        print("\n[Snapshot] Fetching FRED international indicators...")
        fred_intl_snap = {}
        for indic in FRED_INTL_INDICATORS:
            try:
                fred_intl_snap[indic["col"]] = fetch_fred_intl_snapshot(indic)
            except Exception as e:
                print(f"  [Phase C] FRED {indic['col']} snapshot failed: {e}")
                fred_intl_snap[indic["col"]] = {}
            time.sleep(0.6)

        # ------------------------------------------------------------------
        # Build and save snapshot
        # ------------------------------------------------------------------
        snap_df = build_snapshot(oecd_snap, wb_snap, imf_data, fred_intl_snap)
        if not snap_df.empty:
            snap_df.insert(0, "row_id", range(1, len(snap_df) + 1))
            save_snapshot_csv(snap_df)
            push_snapshot_to_sheets(snap_df)

        # ------------------------------------------------------------------
        # HISTORY: OECD full history (separate calls with startPeriod)
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

        # ------------------------------------------------------------------
        # HISTORY: World Bank (full date range in one call)
        # ------------------------------------------------------------------
        print("\n[History] Fetching World Bank full history (from 2000)...")
        wb_hist = {}
        for i, indic in enumerate(WB_INDICATORS):
            try:
                time.sleep(WB_DELAY)
                wb_hist[indic["col"]] = fetch_wb_history(indic)
            except Exception as e:
                print(f"  [Phase C] WB {indic['col']} history failed: {e}")
                wb_hist[indic["col"]] = {}

        # IMF DataMapper returns all years in the snapshot call — reuse it
        print("\n[History] Reusing IMF data (DataMapper returns all years in one call)...")
        imf_hist = imf_data

        # ------------------------------------------------------------------
        # HISTORY: FRED international indicators
        # ------------------------------------------------------------------
        print("\n[History] Fetching FRED international indicators (full history)...")
        fred_intl_hist = {}
        for indic in FRED_INTL_INDICATORS:
            try:
                fred_intl_hist[indic["col"]] = fetch_fred_intl_history(indic, HIST_START)
            except Exception as e:
                print(f"  [Phase C] FRED {indic['col']} history failed: {e}")
                fred_intl_hist[indic["col"]] = {}
            time.sleep(0.6)

        # ------------------------------------------------------------------
        # Build and save history
        # ------------------------------------------------------------------
        hist_df = build_history(oecd_hist, wb_hist, imf_hist, fred_intl_hist)
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
