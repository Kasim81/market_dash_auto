"""
sources/imf.py
==============
IMF DataMapper (imf.org/external/datamapper) source module.  One API call per
indicator returns the full multi-country history; snapshot and history both
come from the same response.

Indicator definitions live in data/macro_library_imf.csv.

TODO (Stage 2): IMF_CODE_MAP belongs in the shared country metadata CSV
(audit item H2).  For Stage 1 it stays co-located with IMF logic.
"""

from __future__ import annotations

import pathlib
import time

import pandas as pd
import requests

from sources.base import fetch_with_backoff

_LIBRARY_CSV = pathlib.Path(__file__).parent.parent / "data" / "macro_library_imf.csv"

IMF_BASE = "https://www.imf.org/external/datamapper/api/v1"

# IMF DataMapper country codes → our OECD-aligned codes.
# IMF uses ISO3 for countries; "EURO" for the Euro Area.
IMF_CODE_MAP = {
    "AUS":  "AUS",
    "CAN":  "CAN",
    "CHE":  "CHE",
    "CHN":  "CHN",
    "DEU":  "DEU",
    "EURO": "EA19",
    "FRA":  "FRA",
    "GBR":  "GBR",
    "ITA":  "ITA",
    "JPN":  "JPN",
    "USA":  "USA",
}


# ---------------------------------------------------------------------------
# LIBRARY LOADER
# ---------------------------------------------------------------------------

def load_library() -> list[dict]:
    """Load IMF indicators from macro_library_imf.csv."""
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
            "series":    row["series_id"],   # fetch uses "series" key
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
    """Validate IMF indicator IDs via /indicator/{imf_id}.  Returns warnings."""
    warnings = []
    total = len(indicators)
    print(f"\nValidating {total} indicator(s) in macro_library_imf.csv...")
    for indic in indicators:
        imf_id = indic["series"]
        try:
            resp = requests.get(
                f"{IMF_BASE}/indicator/{imf_id}",
                timeout=timeout,
            )
            time.sleep(delay)
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


# ---------------------------------------------------------------------------
# RESPONSE PARSER
# ---------------------------------------------------------------------------

def parse_response(data: dict, indicator: str, label: str = "") -> dict:
    """
    Parse an IMF DataMapper response.  Returns:
        {our_country_code: [(year_str, float_value), ...]} sorted ascending.
    """
    results: dict[str, list[tuple[str, float]]] = {}
    values = data.get("values", {}).get(indicator, {})

    for imf_code, year_data in values.items():
        our_code = IMF_CODE_MAP.get(imf_code)
        if not our_code or not year_data:
            continue
        obs_list: list[tuple[str, float]] = []
        for yr, val in year_data.items():
            try:
                obs_list.append((str(yr), float(val)))
            except (TypeError, ValueError):
                pass
        obs_list.sort(key=lambda x: x[0])
        results[our_code] = obs_list

    print(f"  [{label}] → {len(results)} countries parsed from IMF")
    return results


# ---------------------------------------------------------------------------
# FETCHER
# ---------------------------------------------------------------------------

def fetch_indicator(
    indic: dict,
    retries: int = 5,
    backoff_base: int = 2,
) -> dict:
    """
    Fetch full history for one IMF DataMapper indicator.  A single API call
    returns every year × every country; the caller can slice however needed.
    Returns {country_code: [(year_str, val), ...]} or {} on failure.
    """
    url = f"{IMF_BASE}/{indic['series']}"
    label = f"IMF/{indic['col']}"
    print(f"  Fetching {label}...")
    data = fetch_with_backoff(
        url, label=label,
        retries=retries, backoff_base=backoff_base,
    )
    if data is None:
        return {}
    return parse_response(data, indic["series"], label=label)
