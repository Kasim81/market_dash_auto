"""
sources/oecd.py
===============
OECD (sdmx.oecd.org) source module.  Provides library loading and CSV-format
snapshot / history fetchers for OECD REST endpoints.

Indicator definitions live in data/macro_library_oecd.csv.  Each row carries an
`oecd_key_template` and `oecd_countries` that combine to form the SDMX key used
by the OECD REST API.
"""

from __future__ import annotations

import io
import pathlib

import pandas as pd

from sources.base import fetch_with_backoff

_LIBRARY_CSV = pathlib.Path(__file__).parent.parent / "data" / "macro_library_oecd.csv"

OECD_BASE = "https://sdmx.oecd.org/public/rest/data"


# ---------------------------------------------------------------------------
# LIBRARY LOADER
# ---------------------------------------------------------------------------

def load_library() -> list[dict]:
    """
    Load OECD indicator definitions from macro_library_oecd.csv.

    Returns a list of dicts with keys: col, name, category, units, frequency,
    notes, dataflow, key.  The `key` is built by substituting {countries} in
    oecd_key_template with the oecd_countries value.
    """
    df = pd.read_csv(_LIBRARY_CSV, dtype=str, keep_default_na=False)
    df["sort_key"] = pd.to_numeric(df["sort_key"], errors="coerce").fillna(0)
    result = []
    for _, row in df.sort_values("sort_key").iterrows():
        key = row["oecd_key_template"].replace("{countries}", row["oecd_countries"])
        result.append({
            "source":       "OECD",
            "source_id":    row["series_id"].strip(),
            "col":          row["series_id"].strip(),
            "name":         row["name"].strip(),
            "country":      "",   # multi-country; fans out per OECD response
            "category":     row["category"].strip(),
            "subcategory":  row.get("subcategory", "").strip(),
            "concept":      row.get("concept", "").strip(),
            "cycle_timing": row.get("cycle_timing", "").strip(),
            "units":        row["units"].strip(),
            "frequency":    row["frequency"].strip(),
            "notes":        row["notes"].strip(),
            "sort_key":     float(row["sort_key"]),
            # OECD fetch plumbing:
            "dataflow":     row["oecd_dataflow"],
            "key":          key,
        })
    return result


# ---------------------------------------------------------------------------
# CSV PARSER
# ---------------------------------------------------------------------------

def parse_csv(text: str, label: str = "") -> dict:
    """
    Parse the OECD REST CSV response.  The new OECD API prepends metadata rows
    (STRUCTURE, STRUCTURE_ID) before the CSV header; we scan for the REF_AREA
    column dynamically, then read the rest with pandas.

    Returns:
        {country_code: [(period_str, float_value), ...]} sorted ascending.
    """
    if not text or not text.strip():
        print(f"  [{label}] Empty CSV response")
        return {}

    try:
        lines = text.strip().splitlines()

        header_idx = None
        for i, line in enumerate(lines):
            if "REF_AREA" in line.upper():
                header_idx = i
                break

        if header_idx is None:
            print(
                f"  [{label}] REF_AREA column not found in CSV. "
                f"First line: {lines[0][:120]}"
            )
            return {}

        csv_text = "\n".join(lines[header_idx:])
        df = pd.read_csv(io.StringIO(csv_text), dtype=str)

        col_upper = {c.strip().upper(): c for c in df.columns}
        ref_col  = col_upper.get("REF_AREA")
        time_col = col_upper.get("TIME_PERIOD")
        val_col  = col_upper.get("OBS_VALUE")

        if not all([ref_col, time_col, val_col]):
            print(
                f"  [{label}] Missing required CSV columns. "
                f"Found: {list(df.columns)[:10]}"
            )
            return {}

        results: dict[str, list[tuple[str, float]]] = {}
        for _, row in df.iterrows():
            country = str(row[ref_col]).strip()
            period  = str(row[time_col]).strip()
            raw_val = str(row[val_col]).strip()
            if not raw_val or raw_val.upper() in ("NAN", "NA", "N/A", ""):
                continue
            try:
                val = float(raw_val)
            except ValueError:
                continue
            results.setdefault(country, []).append((period, val))

        for k in results:
            results[k].sort(key=lambda x: x[0])

        print(f"    → {len(results)} countries parsed from CSV")
        return results

    except Exception as e:
        print(f"  [{label}] CSV parse error: {e}")
        return {}


# ---------------------------------------------------------------------------
# DATA FETCHERS
# ---------------------------------------------------------------------------

def _fetch(
    indic: dict,
    params: dict,
    label: str,
    retries: int = 5,
    backoff_base: int = 2,
) -> dict:
    """Common wrapper: build URL, fetch, parse CSV."""
    url = f"{OECD_BASE}/{indic['dataflow']}/{indic['key']}"
    print(f"  Fetching {label}...")
    text = fetch_with_backoff(
        url,
        params=params,
        label=label,
        accept_csv=True,
        retries=retries,
        backoff_base=backoff_base,
    )
    if text is None:
        print(f"    → No response for {label}")
        return {}
    return parse_csv(text, label=label)


def fetch_snapshot(indic: dict, retries: int = 5, backoff_base: int = 2) -> dict:
    """Fetch last 3 observations for one OECD indicator (format=csv)."""
    return _fetch(
        indic,
        params={"format": "csv", "lastNObservations": 3},
        label=f"OECD/{indic['col']}",
        retries=retries,
        backoff_base=backoff_base,
    )


def fetch_history(
    indic: dict,
    start: str,
    retries: int = 5,
    backoff_base: int = 2,
) -> dict:
    """
    Fetch full history from `start` (YYYY-MM-DD) for one OECD indicator.
    Only the YYYY-MM prefix is passed as startPeriod.
    """
    return _fetch(
        indic,
        params={"format": "csv", "startPeriod": start[:7]},
        label=f"OECD/{indic['col']}/hist",
        retries=retries,
        backoff_base=backoff_base,
    )
