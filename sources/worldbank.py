"""
sources/worldbank.py
====================
World Bank (api.worldbank.org) source module.  Provides library loading,
JSON response parsing, and annual snapshot / history fetchers.

Indicator definitions live in data/macro_library_worldbank.csv.

TODO (Stage 2): WB_CODE_MAP and WB_COUNTRIES belong in a shared country
metadata CSV — see the audit's H2 item.  For Stage 1 they live here so
they are co-located with the WB-specific logic that uses them.
"""

from __future__ import annotations

import pathlib
import time

import pandas as pd
import requests

from sources.base import fetch_with_backoff

_LIBRARY_CSV = pathlib.Path(__file__).parent.parent / "data" / "macro_library_worldbank.csv"

WB_BASE = "https://api.worldbank.org/v2/country"
WB_VALIDATION_URL = "https://api.worldbank.org/v2/indicator/{wb_id}"

# World Bank uses ISO Alpha-3; EMU = Euro Area.  Map WB codes → our codes.
WB_CODE_MAP = {
    "AUS": "AUS",
    "CAN": "CAN",
    "CHE": "CHE",
    "CHN": "CHN",
    "DEU": "DEU",
    "EMU": "EA19",
    "FRA": "FRA",
    "GBR": "GBR",
    "ITA": "ITA",
    "JPN": "JPN",
    "USA": "USA",
}

# Semicolon-joined for WB URL composition.
WB_COUNTRIES = ";".join(WB_CODE_MAP.keys())


# ---------------------------------------------------------------------------
# LIBRARY LOADER
# ---------------------------------------------------------------------------

def load_library() -> list[dict]:
    """Load World Bank indicators from macro_library_worldbank.csv."""
    df = pd.read_csv(_LIBRARY_CSV, dtype=str, keep_default_na=False)
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


# ---------------------------------------------------------------------------
# VALIDATION
# ---------------------------------------------------------------------------

def validate_library(
    indicators: list[dict],
    delay: float = 1.0,
    timeout: int = 15,
) -> list[str]:
    """
    Call /indicator/{wb_id} for each indicator to confirm it exists.
    Returns a list of warning strings; empty list = all valid.
    """
    warnings = []
    total = len(indicators)
    print(f"\nValidating {total} indicator(s) in macro_library_worldbank.csv...")
    for indic in indicators:
        wb_id = indic["wb_id"]
        try:
            resp = requests.get(
                WB_VALIDATION_URL.format(wb_id=wb_id),
                params={"format": "json"},
                timeout=timeout,
            )
            time.sleep(delay)
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


# ---------------------------------------------------------------------------
# RESPONSE PARSER
# ---------------------------------------------------------------------------

def parse_response(data: list, label: str = "") -> dict:
    """
    Parse a World Bank JSON response, which is shaped
    [pagination_metadata, [observations]].

    Returns:
        {our_country_code: [(year_str, float_value), ...]} sorted ascending.
    """
    if not data or len(data) < 2 or not data[1]:
        print(f"  [{label}] Empty or unexpected World Bank response")
        return {}

    results: dict[str, list[tuple[str, float]]] = {}
    for obs in data[1]:
        val = obs.get("value")
        if val is None:
            continue
        iso3 = obs.get("countryiso3code", "")
        our_code = WB_CODE_MAP.get(iso3)
        if not our_code:
            continue
        yr = str(obs.get("date", ""))
        results.setdefault(our_code, []).append((yr, float(val)))

    for k in results:
        results[k].sort(key=lambda x: x[0])

    print(f"    → {len(results)} countries parsed from World Bank")
    return results


# ---------------------------------------------------------------------------
# FETCHERS
# ---------------------------------------------------------------------------

def _fetch(
    indic: dict,
    params: dict,
    label: str,
    retries: int = 5,
    backoff_base: int = 2,
) -> dict:
    url = f"{WB_BASE}/{WB_COUNTRIES}/indicator/{indic['wb_id']}"
    print(f"  Fetching {label}...")
    data = fetch_with_backoff(
        url, params=params, label=label,
        retries=retries, backoff_base=backoff_base,
    )
    if data is None:
        return {}
    return parse_response(data, label=label)


def fetch_snapshot(indic: dict, retries: int = 5, backoff_base: int = 2) -> dict:
    """Fetch last 5 annual observations for one WB indicator."""
    return _fetch(
        indic,
        params={"format": "json", "mrv": 5, "per_page": 200},
        label=f"WB/{indic['col']}",
        retries=retries,
        backoff_base=backoff_base,
    )


def fetch_history(
    indic: dict,
    start_year: int = 2000,
    end_year: int = 2025,
    retries: int = 5,
    backoff_base: int = 2,
) -> dict:
    """
    Fetch history for one WB indicator across a year range.
    """
    return _fetch(
        indic,
        params={
            "format":   "json",
            "date":     f"{start_year}:{end_year}",
            "per_page": 1000,
        },
        label=f"WB/{indic['col']}/hist",
        retries=retries,
        backoff_base=backoff_base,
    )
