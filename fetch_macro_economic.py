"""
fetch_macro_economic.py
========================
Unified coordinator for every macro economic data source.

Emits (in later commits):
  - data/macro_economic.csv       — long-form snapshot (one row per series
                                    × country).
  - data/macro_economic_hist.csv  — wide-form Friday spine from 1947-01-01
                                    (one column per canonical `col`).

Replaces the four per-source coordinators (fetch_macro_us_fred,
fetch_macro_international, fetch_macro_dbnomics, fetch_macro_ifo), which
get retired once this coordinator has proven itself in the live pipeline.

This commit (S2.C6) only provides the skeleton: it iterates every
source library, builds a unified indicator index, and prints a summary.
Snapshot and history fetching, CSV output, and the Sheets push are
added in S2.C7, S2.C8, and S2.C10 respectively.
"""

from __future__ import annotations

import os
import time
from datetime import datetime, timezone

import pandas as pd

from sources import countries as countries_src
from sources import dbnomics as dbn_src
from sources import fred as fred_src
from sources import ifo as ifo_src
from sources import imf as imf_src
from sources import oecd as oecd_src
from sources import worldbank as worldbank_src


# ---------------------------------------------------------------------------
# CONFIG
# ---------------------------------------------------------------------------

GOOGLE_CREDENTIALS_JSON = os.environ.get("GOOGLE_CREDENTIALS", "")
FRED_API_KEY            = os.environ.get("FRED_API_KEY", "")
SHEET_ID                = "12nKIUGHz5euDbNQPDTVECsJBNwrceRF1ymsQrIe4_ac"

SNAPSHOT_TAB = "macro_economic"
HIST_TAB     = "macro_economic_hist"
SNAPSHOT_CSV = "data/macro_economic.csv"
HIST_CSV     = "data/macro_economic_hist.csv"

# Matches macro_us_hist today — cheap storage, existing consumers already
# handle NaNs in the pre-1960/1985/1991 range.
HIST_START   = "1947-01-01"

# Per-source rate-limit delays (seconds between sequential calls).
FRED_DELAY = 0.6    # ~100 req/min, under FRED's 120/min cap
OECD_DELAY = 4.0    # OECD is strict; max 20/hour
WB_DELAY   = 1.0
IMF_DELAY  = 1.0
DBN_DELAY  = 0.5

# Unified snapshot schema (column order used when writing macro_economic.csv).
SNAPSHOT_COLUMNS = [
    "row_id",
    "Series ID", "Col", "Indicator",
    "Country", "Country Name", "Region", "Source",
    "Category", "Subcategory", "Concept", "cycle_timing",
    "Units", "Frequency",
    "Latest Value", "Prior Value", "Change", "Last Period",
    "Notes", "Fetched At",
]


# ---------------------------------------------------------------------------
# INDICATOR INDEX
# ---------------------------------------------------------------------------
# Each entry returned by load_all_indicators() is a dict with the unified
# schema (source, source_id, col, name, country, category, subcategory,
# concept, cycle_timing, units, frequency, notes, sort_key) plus any
# source-specific fetch plumbing (fred_id, dataflow, key, wb_id, series).
#
# Multi-country sources (OECD, World Bank, IMF) return one row per
# indicator with country="".  The snapshot/history fetchers fan those out
# per country at fetch time.

def load_all_indicators() -> list[dict]:
    """Walk every source library and return a merged list of indicators."""
    indicators: list[dict] = []
    indicators.extend(fred_src.load_us_library_as_list())
    indicators.extend(fred_src.load_intl_library())
    indicators.extend(oecd_src.load_library())
    indicators.extend(worldbank_src.load_library())
    indicators.extend(imf_src.load_library())
    indicators.extend(dbn_src.load_library())
    indicators.extend(ifo_src.load_library())
    return indicators


def summarize(indicators: list[dict]) -> None:
    """Print a concise per-source breakdown for eyeballing the index."""
    by_source: dict[str, int] = {}
    for i in indicators:
        by_source[i["source"]] = by_source.get(i["source"], 0) + 1

    by_concept: dict[str, int] = {}
    for i in indicators:
        by_concept[i["concept"] or "(blank)"] = by_concept.get(i["concept"] or "(blank)", 0) + 1

    by_cycle: dict[str, int] = {}
    for i in indicators:
        by_cycle[i["cycle_timing"] or "(blank)"] = by_cycle.get(i["cycle_timing"] or "(blank)", 0) + 1

    countries = sorted({i["country"] for i in indicators if i["country"]})
    multi = [i["col"] for i in indicators if not i["country"]]

    print("\n── macro_economic indicator index ─────────────────────────────────")
    print(f"  total indicators: {len(indicators)}")
    print(f"  by source:")
    for src, n in sorted(by_source.items(), key=lambda kv: -kv[1]):
        print(f"    {src:<12} {n}")
    print(f"  by concept:")
    for c, n in sorted(by_concept.items(), key=lambda kv: -kv[1]):
        print(f"    {c:<22} {n}")
    print(f"  by cycle_timing:")
    for c, n in sorted(by_cycle.items(), key=lambda kv: -kv[1]):
        print(f"    {c:<10} {n}")
    print(f"  single-country series:   {sum(1 for i in indicators if i['country'])}")
    print(f"  multi-country fan-outs:  {len(multi)}  ({', '.join(multi)})")
    print(f"  countries referenced:    {len(countries)}  ({', '.join(countries)})")
    print("────────────────────────────────────────────────────────────────────\n")


# ---------------------------------------------------------------------------
# SNAPSHOT BUILDERS
# ---------------------------------------------------------------------------

def _utc_ts() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def _make_row(
    indic: dict,
    country: str,
    col: str,
    latest: float | None,
    prior: float | None,
    last_period: str | None,
    fetched_at: str,
) -> dict:
    """Assemble one snapshot row dict from an indicator + per-country values."""
    change = (
        round(latest - prior, 4)
        if (latest is not None and prior is not None)
        else None
    )
    if country:
        cname, region = countries_src.country_meta().get(country, (country, ""))
    else:
        cname, region = "", ""
    return {
        "Series ID":    indic["source_id"],
        "Col":          col,
        "Indicator":    indic["name"],
        "Country":      country,
        "Country Name": cname,
        "Region":       region,
        "Source":       indic["source"],
        "Category":     indic["category"],
        "Subcategory":  indic["subcategory"],
        "Concept":      indic["concept"],
        "cycle_timing": indic["cycle_timing"],
        "Units":        indic["units"],
        "Frequency":    indic["frequency"],
        "Latest Value": round(latest, 4) if latest is not None else None,
        "Prior Value":  round(prior,  4) if prior  is not None else None,
        "Change":       change,
        "Last Period":  last_period or "",
        "Notes":        indic["notes"],
        "Fetched At":   fetched_at,
    }


def _blank_row(indic: dict, country: str, col: str, fetched_at: str) -> dict:
    return _make_row(indic, country, col, None, None, None, fetched_at)


# -- FRED US snapshot --

def _fetch_fred_us_snapshot(indic: dict, fetched_at: str) -> list[dict]:
    latest, prior, last_date = fred_src.fetch_latest_prior(
        indic["source_id"], FRED_API_KEY,
        lookback_start="2015-01-01", limit=24,
    )
    time.sleep(FRED_DELAY)
    return [_make_row(indic, indic["country"], indic["col"],
                      latest, prior, last_date, fetched_at)]


# -- FRED intl snapshot --

def _fetch_fred_intl_snapshot(indic: dict, fetched_at: str) -> list[dict]:
    data = fred_src.fetch_observations(
        indic["source_id"], FRED_API_KEY,
        limit=3, sort_order="desc", label=f"FRED/{indic['col']}",
    )
    time.sleep(FRED_DELAY)
    if data is None:
        return [_blank_row(indic, indic["country"], indic["col"], fetched_at)]
    obs = [o for o in data.get("observations", [])
           if o.get("value") not in (".", "", None)]
    if not obs:
        return [_blank_row(indic, indic["country"], indic["col"], fetched_at)]
    # Desc order → latest is obs[0], prior is obs[1].
    try:
        latest = float(obs[0]["value"])
    except (ValueError, TypeError):
        latest = None
    try:
        prior = float(obs[1]["value"]) if len(obs) > 1 else None
    except (ValueError, TypeError):
        prior = None
    last_period = obs[0].get("date", "")
    return [_make_row(indic, indic["country"], indic["col"],
                      latest, prior, last_period, fetched_at)]


# -- Multi-country fan-out helper (OECD / WB / IMF all share this shape) --

def _fan_out_snapshot(
    indic: dict,
    country_data: dict[str, list[tuple[str, float]]],
    fetched_at: str,
) -> list[dict]:
    rows = []
    for country, obs in country_data.items():
        col = f"{country}_{indic['col']}"
        if obs:
            latest = obs[-1][1]
            prior  = obs[-2][1] if len(obs) >= 2 else None
            last_period = obs[-1][0]
        else:
            latest = prior = None
            last_period = None
        rows.append(_make_row(indic, country, col, latest, prior, last_period, fetched_at))
    return rows


def _fetch_oecd_snapshot(indic: dict, fetched_at: str) -> list[dict]:
    country_data = oecd_src.fetch_snapshot(indic)
    time.sleep(OECD_DELAY)
    return _fan_out_snapshot(indic, country_data, fetched_at)


def _fetch_wb_snapshot(indic: dict, fetched_at: str) -> list[dict]:
    country_data = worldbank_src.fetch_snapshot(indic)
    time.sleep(WB_DELAY)
    return _fan_out_snapshot(indic, country_data, fetched_at)


def _fetch_imf_snapshot(indic: dict, fetched_at: str) -> list[dict]:
    # IMF returns the full series; take the last two obs per country.
    country_data = imf_src.fetch_indicator(indic)
    time.sleep(IMF_DELAY)
    return _fan_out_snapshot(indic, country_data, fetched_at)


# -- DB.nomics snapshot --

def _fetch_dbnomics_snapshot(indic: dict, fetched_at: str) -> list[dict]:
    doc = dbn_src.fetch_series(indic["source_id"])
    time.sleep(DBN_DELAY)
    if doc is None:
        return [_blank_row(indic, indic["country"], indic["col"], fetched_at)]
    obs = dbn_src.parse_observations(doc)
    if not obs:
        return [_blank_row(indic, indic["country"], indic["col"], fetched_at)]
    latest = obs[-1][1]
    prior  = obs[-2][1] if len(obs) >= 2 else None
    last_period = obs[-1][0]
    return [_make_row(indic, indic["country"], indic["col"],
                      latest, prior, last_period, fetched_at)]


# -- ifo snapshot (batch) --

def _fetch_ifo_snapshot_batch(
    ifo_indicators: list[dict],
    fetched_at: str,
) -> list[dict]:
    """Single workbook download → 3 rows."""
    try:
        url = ifo_src.resolve_workbook_url()
        print(f"  [ifo] Resolved workbook: {url}")
        xlsx = ifo_src.download_workbook(url)
        monthly = ifo_src.parse_workbook(xlsx, ifo_indicators)
    except Exception as e:
        print(f"  [ifo] Workbook fetch/parse failed: {e}")
        return [_blank_row(i, i["country"], i["col"], fetched_at) for i in ifo_indicators]

    rows = []
    for indic in ifo_indicators:
        s = monthly[indic["col"]].dropna()
        if s.empty:
            latest = prior = None
            last_period = ""
        else:
            latest = float(s.iloc[-1])
            prior  = float(s.iloc[-2]) if len(s) >= 2 else None
            last_period = s.index[-1].strftime("%Y-%m")
        rows.append(_make_row(indic, indic["country"], indic["col"],
                              latest, prior, last_period, fetched_at))
    return rows


# -- Top-level snapshot builder --

def build_snapshot_df(indicators: list[dict]) -> pd.DataFrame:
    """Iterate every indicator, fetch its latest observations, return a DF."""
    fetched_at = _utc_ts()
    rows: list[dict] = []

    ifo_indicators = [i for i in indicators if i["source"] == "ifo"]

    for indic in indicators:
        src = indic["source"]
        if src == "ifo":
            continue  # handled in a single batch below
        label = f"{src}/{indic['col']}"
        print(f"  [{label}]")
        try:
            if src == "FRED" and indic["country"] == "USA":
                got = _fetch_fred_us_snapshot(indic, fetched_at)
            elif src == "FRED":
                got = _fetch_fred_intl_snapshot(indic, fetched_at)
            elif src == "OECD":
                got = _fetch_oecd_snapshot(indic, fetched_at)
            elif src == "World Bank":
                got = _fetch_wb_snapshot(indic, fetched_at)
            elif src == "IMF":
                got = _fetch_imf_snapshot(indic, fetched_at)
            elif src == "DB.nomics":
                got = _fetch_dbnomics_snapshot(indic, fetched_at)
            else:
                print(f"  [WARN] Unknown source '{src}' — skipping")
                continue
            rows.extend(got)
        except Exception as e:
            print(f"  [{label}] snapshot failed: {e}")
            rows.append(_blank_row(indic, indic["country"], indic["col"], fetched_at))

    if ifo_indicators:
        try:
            rows.extend(_fetch_ifo_snapshot_batch(ifo_indicators, fetched_at))
        except Exception as e:
            print(f"  [ifo] snapshot batch failed: {e}")
            rows.extend(_blank_row(i, i["country"], i["col"], fetched_at) for i in ifo_indicators)

    for i, row in enumerate(rows, start=1):
        row["row_id"] = i

    return pd.DataFrame(rows, columns=SNAPSHOT_COLUMNS)


def save_snapshot_csv(df: pd.DataFrame) -> None:
    os.makedirs("data", exist_ok=True)
    df.to_csv(SNAPSHOT_CSV, index=False, float_format="%.4f", na_rep="")
    print(f"  Written {len(df)} rows to {SNAPSHOT_CSV}")


# ---------------------------------------------------------------------------
# ENTRY POINT
# ---------------------------------------------------------------------------

def run_phase_macro_economic() -> None:
    print("\n" + "=" * 60)
    print("macro_economic — Unified Economic Data Coordinator")
    print("=" * 60)

    t0 = time.time()
    indicators = load_all_indicators()
    summarize(indicators)

    canonical = set(countries_src.country_meta().keys())
    bad = [i for i in indicators if i["country"] and i["country"] not in canonical]
    if bad:
        print(f"  [WARN] {len(bad)} indicator(s) have non-canonical country codes:")
        for i in bad:
            print(f"    - {i['source']} / {i['col']}: country={i['country']!r}")
    else:
        print("  [OK] Every single-country indicator uses a canonical country code.")

    # Snapshot
    print("\n[Snapshot] Fetching latest observations ...")
    snap_df = build_snapshot_df(indicators)
    save_snapshot_csv(snap_df)

    # History deferred to S2.C8.

    print(f"\n  macro_economic run completed in {time.time() - t0:.1f}s")


if __name__ == "__main__":
    run_phase_macro_economic()
