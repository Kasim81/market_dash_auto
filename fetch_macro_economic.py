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

import csv as _csv
import os
import time
from datetime import date, datetime, timezone

import pandas as pd

from sources import countries as countries_src
from sources import dbnomics as dbn_src
from sources import fred as fred_src
from sources import ifo as ifo_src
from sources import imf as imf_src
from sources import oecd as oecd_src
from sources import worldbank as worldbank_src
from sources import boe as boe_src
from sources import ecb as ecb_src
from sources import boj as boj_src
from sources import estat as estat_src
from sources import nasdaq_data_link as ndl_src
from sources import lbma as lbma_src
from sources import boc as boc_src
from sources import statcan as statcan_src
from sources import ons as ons_src
from sources import bundesbank as bundesbank_src
from sources import abs as abs_src
from sources import istat as istat_src
from sources import bls as bls_src
from sources import insee as insee_src
from sources import bdf as bdf_src
from sources import shiller as shiller_src
from sources import french as french_src
from sources import jst as jst_src
from sources import atlanta_fed as atlanta_fed_src
from sources.base import build_friday_spine, get_sheets_service, push_df_to_sheets

from library_utils import write_hist_with_archive


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
    indicators.extend(boe_src.load_library())
    indicators.extend(ecb_src.load_library())
    indicators.extend(boj_src.load_library())
    indicators.extend(estat_src.load_library())
    indicators.extend(ndl_src.load_library())
    indicators.extend(lbma_src.load_library())
    indicators.extend(boc_src.load_library())
    indicators.extend(statcan_src.load_library())
    indicators.extend(ons_src.load_library())
    indicators.extend(bundesbank_src.load_library())
    indicators.extend(abs_src.load_library())
    indicators.extend(istat_src.load_library())
    indicators.extend(bls_src.load_library())
    indicators.extend(insee_src.load_library())
    indicators.extend(bdf_src.load_library())
    indicators.extend(shiller_src.load_library())
    indicators.extend(french_src.load_library())
    indicators.extend(jst_src.load_library())
    indicators.extend(atlanta_fed_src.load_library())
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


# ---------------------------------------------------------------------------
# SOURCE SELECTION (single canonical column per indicator)
# ---------------------------------------------------------------------------
# We deliberately do NOT create parallel vendor-suffixed columns when more
# than one source can supply the same series. Instead every source targets
# the same canonical `col`, and a single winner populates it:
#   1. Data quality first — the source whose series carries the most recent
#      observation wins (higher cadence ⇒ fresher ⇒ wins automatically).
#   2. On a tie (equal latest period), the *ultimate* / primary source
#      (national statistics office, central bank, exchange) is preferred over
#      an aggregator that merely republishes it (FRED, OECD, World Bank, IMF,
#      DB.nomics, Nasdaq Data Link).
# Aggregators stay registered so they transparently back-fill when the
# primary source is stale or unavailable — preference, not deletion.

PRIMARY_SOURCES = {
    "BoC", "StatCan", "ONS", "Bundesbank", "ABS", "ISTAT", "BLS",
    "BoE", "ECB", "BoJ", "e-Stat", "ifo", "LBMA",
    "INSEE", "Banque de France",
}


def _source_rank(source: str) -> int:
    """Tie-break rank: 1 for ultimate/primary sources, 0 for aggregators."""
    return 1 if source in PRIMARY_SOURCES else 0


def _dedupe_snapshot_rows(rows: list[dict]) -> list[dict]:
    """Collapse rows that share a (Country, Col) to a single winning source.

    Winner = (has a value) > (most recent Last Period) > (primary over
    aggregator). Group order follows first appearance so output stays stable.
    """
    order: list[tuple[str, str]] = []
    groups: dict[tuple[str, str], list[dict]] = {}
    for r in rows:
        key = (r.get("Country", ""), r.get("Col", ""))
        if key not in groups:
            groups[key] = []
            order.append(key)
        groups[key].append(r)

    def _key(r: dict):
        has_val = 0 if r.get("Latest Value") is None else 1
        last_period = r.get("Last Period") or ""
        return (has_val, last_period, _source_rank(r.get("Source", "")))

    out: list[dict] = []
    for key in order:
        grp = groups[key]
        out.append(grp[0] if len(grp) == 1 else max(grp, key=_key))
    return out


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


# -- BoE IADB snapshot --

BOE_DELAY = 0.6  # seconds between BoE IADB calls


def _fetch_boe_snapshot(indic: dict, fetched_at: str) -> list[dict]:
    s = boe_src.fetch_series_as_pandas(indic["source_id"])
    time.sleep(BOE_DELAY)
    if s is None or s.empty:
        return [_blank_row(indic, indic["country"], indic["col"], fetched_at)]
    s = s.dropna()
    if s.empty:
        return [_blank_row(indic, indic["country"], indic["col"], fetched_at)]
    latest = float(s.iloc[-1])
    prior = float(s.iloc[-2]) if len(s) >= 2 else None
    last_period = s.index[-1].strftime("%Y-%m-%d")
    return [_make_row(indic, indic["country"], indic["col"],
                      latest, prior, last_period, fetched_at)]


# -- ECB Data Portal snapshot --

ECB_DELAY = 0.6  # seconds between ECB Data Portal calls


def _fetch_ecb_snapshot(indic: dict, fetched_at: str) -> list[dict]:
    # last_n=2 keeps the response small (latest + prior) so we don't need a
    # 60s timeout window for the snapshot call. History pulls full series.
    s = ecb_src.fetch_series_as_pandas(indic["source_id"], last_n=2)
    time.sleep(ECB_DELAY)
    if s is None or s.empty:
        return [_blank_row(indic, indic["country"], indic["col"], fetched_at)]
    s = s.dropna()
    if s.empty:
        return [_blank_row(indic, indic["country"], indic["col"], fetched_at)]
    latest = float(s.iloc[-1])
    prior = float(s.iloc[-2]) if len(s) >= 2 else None
    last_period = s.index[-1].strftime("%Y-%m-%d")
    return [_make_row(indic, indic["country"], indic["col"],
                      latest, prior, last_period, fetched_at)]


# -- Bank of Canada Valet snapshot --

BOC_DELAY = 0.4  # seconds between BoC Valet calls


def _fetch_boc_snapshot(indic: dict, fetched_at: str) -> list[dict]:
    s = boc_src.fetch_series_as_pandas(indic["source_id"], recent=2)
    time.sleep(BOC_DELAY)
    if s is None or s.empty:
        return [_blank_row(indic, indic["country"], indic["col"], fetched_at)]
    s = s.dropna()
    if s.empty:
        return [_blank_row(indic, indic["country"], indic["col"], fetched_at)]
    latest = float(s.iloc[-1])
    prior = float(s.iloc[-2]) if len(s) >= 2 else None
    last_period = s.index[-1].strftime("%Y-%m-%d")
    return [_make_row(indic, indic["country"], indic["col"],
                      latest, prior, last_period, fetched_at)]


# -- StatCan WDS snapshot --

STATCAN_DELAY = 0.4  # seconds between StatCan WDS calls


def _fetch_statcan_snapshot(indic: dict, fetched_at: str) -> list[dict]:
    s = statcan_src.fetch_series_as_pandas(indic["source_id"], latest_n=2)
    time.sleep(STATCAN_DELAY)
    if s is None or s.empty:
        return [_blank_row(indic, indic["country"], indic["col"], fetched_at)]
    s = s.dropna()
    if s.empty:
        return [_blank_row(indic, indic["country"], indic["col"], fetched_at)]
    latest = float(s.iloc[-1])
    prior = float(s.iloc[-2]) if len(s) >= 2 else None
    last_period = s.index[-1].strftime("%Y-%m-%d")
    return [_make_row(indic, indic["country"], indic["col"],
                      latest, prior, last_period, fetched_at)]


# -- ONS snapshot --

ONS_DELAY = 0.4  # seconds between ONS calls


def _fetch_ons_snapshot(indic: dict, fetched_at: str) -> list[dict]:
    # ONS /data returns the full series in one small JSON; no last_n param.
    s = ons_src.fetch_series_as_pandas(indic["source_id"])
    time.sleep(ONS_DELAY)
    if s is None or s.empty:
        return [_blank_row(indic, indic["country"], indic["col"], fetched_at)]
    s = s.dropna()
    if s.empty:
        return [_blank_row(indic, indic["country"], indic["col"], fetched_at)]
    latest = float(s.iloc[-1])
    prior = float(s.iloc[-2]) if len(s) >= 2 else None
    last_period = s.index[-1].strftime("%Y-%m-%d")
    return [_make_row(indic, indic["country"], indic["col"],
                      latest, prior, last_period, fetched_at)]


# -- Bundesbank snapshot --

BUNDESBANK_DELAY = 0.4  # seconds between Bundesbank calls


def _fetch_bundesbank_snapshot(indic: dict, fetched_at: str) -> list[dict]:
    s = bundesbank_src.fetch_series_as_pandas(indic["source_id"], last_n=2)
    time.sleep(BUNDESBANK_DELAY)
    if s is None or s.empty:
        return [_blank_row(indic, indic["country"], indic["col"], fetched_at)]
    s = s.dropna()
    if s.empty:
        return [_blank_row(indic, indic["country"], indic["col"], fetched_at)]
    latest = float(s.iloc[-1])
    prior = float(s.iloc[-2]) if len(s) >= 2 else None
    last_period = s.index[-1].strftime("%Y-%m-%d")
    return [_make_row(indic, indic["country"], indic["col"],
                      latest, prior, last_period, fetched_at)]


# -- ABS snapshot --

ABS_DELAY = 0.4  # seconds between ABS calls


def _fetch_abs_snapshot(indic: dict, fetched_at: str) -> list[dict]:
    s = abs_src.fetch_series_as_pandas(indic["source_id"], last_n=2)
    time.sleep(ABS_DELAY)
    if s is None or s.empty:
        return [_blank_row(indic, indic["country"], indic["col"], fetched_at)]
    s = s.dropna()
    if s.empty:
        return [_blank_row(indic, indic["country"], indic["col"], fetched_at)]
    latest = float(s.iloc[-1])
    prior = float(s.iloc[-2]) if len(s) >= 2 else None
    last_period = s.index[-1].strftime("%Y-%m-%d")
    return [_make_row(indic, indic["country"], indic["col"],
                      latest, prior, last_period, fetched_at)]


# -- ISTAT snapshot --

ISTAT_DELAY = 0.6  # seconds between ISTAT calls (flaky gateway — go gentle)


def _fetch_istat_snapshot(indic: dict, fetched_at: str) -> list[dict]:
    s = istat_src.fetch_series_as_pandas(indic["source_id"], last_n=3)
    time.sleep(ISTAT_DELAY)
    if s is None or s.empty:
        return [_blank_row(indic, indic["country"], indic["col"], fetched_at)]
    s = s.dropna()
    if s.empty:
        return [_blank_row(indic, indic["country"], indic["col"], fetched_at)]
    latest = float(s.iloc[-1])
    prior = float(s.iloc[-2]) if len(s) >= 2 else None
    last_period = s.index[-1].strftime("%Y-%m-%d")
    return [_make_row(indic, indic["country"], indic["col"],
                      latest, prior, last_period, fetched_at)]


# -- BLS snapshot --

BLS_DELAY = 0.5  # seconds between BLS API calls


def _fetch_bls_snapshot(indic: dict, fetched_at: str) -> list[dict]:
    s = bls_src.fetch_series_as_pandas(indic["source_id"], recent=True)
    time.sleep(BLS_DELAY)
    if s is None or s.empty:
        return [_blank_row(indic, indic["country"], indic["col"], fetched_at)]
    s = s.dropna()
    if s.empty:
        return [_blank_row(indic, indic["country"], indic["col"], fetched_at)]
    latest = float(s.iloc[-1])
    prior = float(s.iloc[-2]) if len(s) >= 2 else None
    last_period = s.index[-1].strftime("%Y-%m-%d")
    return [_make_row(indic, indic["country"], indic["col"],
                      latest, prior, last_period, fetched_at)]


# -- INSEE / Banque de France snapshots --
# National statistical offices wired as PRIMARY sources for FRA. INSEE is keyless
# and curated; Banque de France no-ops gracefully until BDF_API_KEY is present.

INSEE_DELAY = 0.5  # seconds between INSEE API calls
BDF_DELAY   = 0.5  # seconds between Banque de France API calls


def _snapshot_from_series(s, indic: dict, fetched_at: str) -> list[dict]:
    """Shared snapshot shaping: blank row on no data, else latest/prior row."""
    if s is None or s.empty:
        return [_blank_row(indic, indic["country"], indic["col"], fetched_at)]
    s = s.dropna()
    if s.empty:
        return [_blank_row(indic, indic["country"], indic["col"], fetched_at)]
    latest = float(s.iloc[-1])
    prior = float(s.iloc[-2]) if len(s) >= 2 else None
    last_period = s.index[-1].strftime("%Y-%m-%d")
    return [_make_row(indic, indic["country"], indic["col"],
                      latest, prior, last_period, fetched_at)]


def _fetch_insee_snapshot(indic: dict, fetched_at: str) -> list[dict]:
    s = insee_src.fetch_series_as_pandas(indic["source_id"])
    time.sleep(INSEE_DELAY)
    return _snapshot_from_series(s, indic, fetched_at)


def _fetch_bdf_snapshot(indic: dict, fetched_at: str) -> list[dict]:
    s = bdf_src.fetch_series_as_pandas(indic["source_id"])
    time.sleep(BDF_DELAY)
    return _snapshot_from_series(s, indic, fetched_at)


# -- §3.13 long-run sources (Shiller / Ken French / JST) snapshot --
#
# These three sources each cache a single workbook/ZIP/.dta per process so the
# whole library hits one network round-trip total — the delay only matters
# between distinct downloads, not between successive series within one source.
# Keep the delay short.
SHILLER_DELAY    = 0.1
FRENCH_DELAY     = 0.1
JST_DELAY        = 0.1
ATLANTA_FED_DELAY = 0.1


def _fetch_shiller_snapshot(indic: dict, fetched_at: str) -> list[dict]:
    s = shiller_src.fetch_series_as_pandas(indic["source_id"])
    time.sleep(SHILLER_DELAY)
    return _snapshot_from_series(s, indic, fetched_at)


def _fetch_french_snapshot(indic: dict, fetched_at: str) -> list[dict]:
    s = french_src.fetch_series_as_pandas(indic["source_id"])
    time.sleep(FRENCH_DELAY)
    return _snapshot_from_series(s, indic, fetched_at)


def _fetch_jst_snapshot(indic: dict, fetched_at: str) -> list[dict]:
    s = jst_src.fetch_series_as_pandas(indic["source_id"])
    time.sleep(JST_DELAY)
    return _snapshot_from_series(s, indic, fetched_at)


def _fetch_atlanta_fed_snapshot(indic: dict, fetched_at: str) -> list[dict]:
    s = atlanta_fed_src.fetch_series_as_pandas(indic["source_id"])
    time.sleep(ATLANTA_FED_DELAY)
    return _snapshot_from_series(s, indic, fetched_at)


# -- BoJ Time-Series Data Search snapshot --

BOJ_DELAY = 0.6  # seconds between BoJ API calls


def _fetch_boj_snapshot(indic: dict, fetched_at: str) -> list[dict]:
    s = boj_src.fetch_series_as_pandas(indic["source_id"])
    time.sleep(BOJ_DELAY)
    if s is None or s.empty:
        return [_blank_row(indic, indic["country"], indic["col"], fetched_at)]
    s = s.dropna()
    if s.empty:
        return [_blank_row(indic, indic["country"], indic["col"], fetched_at)]
    latest = float(s.iloc[-1])
    prior = float(s.iloc[-2]) if len(s) >= 2 else None
    last_period = s.index[-1].strftime("%Y-%m-%d")
    return [_make_row(indic, indic["country"], indic["col"],
                      latest, prior, last_period, fetched_at)]


# -- e-Stat snapshot --

ESTAT_DELAY = 0.6  # seconds between e-Stat API calls


def _fetch_estat_snapshot(indic: dict, fetched_at: str) -> list[dict]:
    s = estat_src.fetch_series_as_pandas(indic["source_id"])
    time.sleep(ESTAT_DELAY)
    if s is None or s.empty:
        return [_blank_row(indic, indic["country"], indic["col"], fetched_at)]
    s = s.dropna()
    if s.empty:
        return [_blank_row(indic, indic["country"], indic["col"], fetched_at)]
    latest = float(s.iloc[-1])
    prior = float(s.iloc[-2]) if len(s) >= 2 else None
    last_period = s.index[-1].strftime("%Y-%m-%d")
    return [_make_row(indic, indic["country"], indic["col"],
                      latest, prior, last_period, fetched_at)]


# -- Nasdaq Data Link snapshot --

NDL_DELAY = 0.6  # seconds between Nasdaq Data Link calls


def _fetch_ndl_snapshot(indic: dict, fetched_at: str) -> list[dict]:
    s = ndl_src.fetch_series_as_pandas(
        indic["source_id"],
        sub_field=indic.get("sub_field", ""),
    )
    time.sleep(NDL_DELAY)
    if s is None or s.empty:
        return [_blank_row(indic, indic["country"], indic["col"], fetched_at)]
    s = s.dropna()
    if s.empty:
        return [_blank_row(indic, indic["country"], indic["col"], fetched_at)]
    latest = float(s.iloc[-1])
    prior = float(s.iloc[-2]) if len(s) >= 2 else None
    last_period = s.index[-1].strftime("%Y-%m-%d")
    return [_make_row(indic, indic["country"], indic["col"],
                      latest, prior, last_period, fetched_at)]


# -- LBMA snapshot --

LBMA_DELAY = 0.6  # seconds between LBMA JSON calls


def _fetch_lbma_snapshot(indic: dict, fetched_at: str) -> list[dict]:
    s = lbma_src.fetch_series_as_pandas(
        indic["source_id"],
        sub_field=indic.get("sub_field", "USD"),
    )
    time.sleep(LBMA_DELAY)
    if s is None or s.empty:
        return [_blank_row(indic, indic["country"], indic["col"], fetched_at)]
    s = s.dropna()
    if s.empty:
        return [_blank_row(indic, indic["country"], indic["col"], fetched_at)]
    latest = float(s.iloc[-1])
    prior = float(s.iloc[-2]) if len(s) >= 2 else None
    last_period = s.index[-1].strftime("%Y-%m-%d")
    return [_make_row(indic, indic["country"], indic["col"],
                      latest, prior, last_period, fetched_at)]


# -- ifo snapshot (batch) --

def _fetch_ifo_snapshot_batch(
    ifo_indicators: list[dict],
    fetched_at: str,
) -> list[dict]:
    """Single workbook download → one row per ifo indicator."""
    try:
        url, xlsx = ifo_src.resolve_workbook()
        print(f"  [ifo] Resolved workbook: {url}  ({len(xlsx):,} bytes)")
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
            elif src == "BoE":
                got = _fetch_boe_snapshot(indic, fetched_at)
            elif src == "ECB":
                got = _fetch_ecb_snapshot(indic, fetched_at)
            elif src == "BoJ":
                got = _fetch_boj_snapshot(indic, fetched_at)
            elif src == "BoC":
                got = _fetch_boc_snapshot(indic, fetched_at)
            elif src == "StatCan":
                got = _fetch_statcan_snapshot(indic, fetched_at)
            elif src == "ONS":
                got = _fetch_ons_snapshot(indic, fetched_at)
            elif src == "Bundesbank":
                got = _fetch_bundesbank_snapshot(indic, fetched_at)
            elif src == "ABS":
                got = _fetch_abs_snapshot(indic, fetched_at)
            elif src == "ISTAT":
                got = _fetch_istat_snapshot(indic, fetched_at)
            elif src == "BLS":
                got = _fetch_bls_snapshot(indic, fetched_at)
            elif src == "INSEE":
                got = _fetch_insee_snapshot(indic, fetched_at)
            elif src == "Banque de France":
                got = _fetch_bdf_snapshot(indic, fetched_at)
            elif src == "e-Stat":
                got = _fetch_estat_snapshot(indic, fetched_at)
            elif src == "Nasdaq Data Link":
                got = _fetch_ndl_snapshot(indic, fetched_at)
            elif src == "LBMA":
                got = _fetch_lbma_snapshot(indic, fetched_at)
            elif src == "Shiller":
                got = _fetch_shiller_snapshot(indic, fetched_at)
            elif src == "KenFrench":
                got = _fetch_french_snapshot(indic, fetched_at)
            elif src == "JST":
                got = _fetch_jst_snapshot(indic, fetched_at)
            elif src == "AtlantaFed":
                got = _fetch_atlanta_fed_snapshot(indic, fetched_at)
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

    # One canonical row per (Country, Col): drop duplicate sources, keeping the
    # freshest / ultimate-source winner (see _dedupe_snapshot_rows).
    before = len(rows)
    rows = _dedupe_snapshot_rows(rows)
    if before != len(rows):
        print(f"  snapshot: collapsed {before} → {len(rows)} rows "
              f"(deduped {before - len(rows)} aggregator/primary overlaps)")

    for i, row in enumerate(rows, start=1):
        row["row_id"] = i

    return pd.DataFrame(rows, columns=SNAPSHOT_COLUMNS)


def save_snapshot_csv(df: pd.DataFrame) -> None:
    os.makedirs("data", exist_ok=True)
    df.to_csv(SNAPSHOT_CSV, index=False, float_format="%.4f", na_rep="")
    print(f"  Written {len(df)} rows to {SNAPSHOT_CSV}")


# ---------------------------------------------------------------------------
# HISTORY BUILDERS
# ---------------------------------------------------------------------------
# Each _fetch_*_history returns a dict {column_name: pd.Series} where the
# series is indexed by a DatetimeIndex.  Empty dict on failure.
# Column names are the canonical `col` value (single-country) or
# f"{country}_{col}" (multi-country fan-out).

def _obs_list_to_series(obs: list[tuple[str, float]], col_name: str) -> pd.Series:
    """Convert [(period_str, val), ...] to a DatetimeIndex pd.Series."""
    if not obs:
        return pd.Series(dtype=float, name=col_name)
    dates = []
    values = []
    for period, val in obs:
        dt = dbn_src.parse_period_to_date(period)
        if dt is None:
            continue
        dates.append(dt)
        values.append(val)
    if not dates:
        return pd.Series(dtype=float, name=col_name)
    return pd.Series(values, index=pd.DatetimeIndex(dates), name=col_name)


# -- FRED US --

def _fetch_fred_us_history(indic: dict) -> dict[str, pd.Series]:
    s = fred_src.fetch_series_as_pandas(indic["source_id"], FRED_API_KEY, HIST_START)
    time.sleep(FRED_DELAY)
    if s is None:
        return {}
    s.name = indic["col"]
    return {indic["col"]: s}


# -- FRED intl --

def _fetch_fred_intl_history(indic: dict) -> dict[str, pd.Series]:
    s = fred_src.fetch_series_as_pandas(indic["source_id"], FRED_API_KEY, HIST_START)
    time.sleep(FRED_DELAY)
    if s is None:
        return {}
    s.name = indic["col"]
    return {indic["col"]: s}


# -- Multi-country fan-out helper --

def _fan_out_history(
    indic: dict,
    country_data: dict[str, list[tuple[str, float]]],
) -> dict[str, pd.Series]:
    out = {}
    for country, obs in country_data.items():
        col_name = f"{country}_{indic['col']}"
        s = _obs_list_to_series(obs, col_name)
        if not s.empty:
            out[col_name] = s
    return out


def _fetch_oecd_history(indic: dict) -> dict[str, pd.Series]:
    country_data = oecd_src.fetch_history(indic, HIST_START)
    time.sleep(OECD_DELAY)
    return _fan_out_history(indic, country_data)


def _fetch_wb_history(indic: dict) -> dict[str, pd.Series]:
    # HIST_START = 1947-01-01; WB data mostly starts 1960, so use 1960 floor.
    country_data = worldbank_src.fetch_history(
        indic, start_year=int(HIST_START[:4]), end_year=date.today().year,
    )
    time.sleep(WB_DELAY)
    return _fan_out_history(indic, country_data)


def _fetch_imf_history(indic: dict) -> dict[str, pd.Series]:
    country_data = imf_src.fetch_indicator(indic)
    time.sleep(IMF_DELAY)
    return _fan_out_history(indic, country_data)


# -- DB.nomics --

def _fetch_dbnomics_history(indic: dict) -> dict[str, pd.Series]:
    doc = dbn_src.fetch_series(indic["source_id"])
    time.sleep(DBN_DELAY)
    if doc is None:
        return {}
    obs = dbn_src.parse_observations(doc)
    s = dbn_src.obs_to_series(obs, indic["col"])
    if s.empty:
        return {}
    return {indic["col"]: s}


# -- BoE IADB --

def _fetch_boe_history(indic: dict) -> dict[str, pd.Series]:
    s = boe_src.fetch_series_as_pandas(indic["source_id"], col_name=indic["col"])
    time.sleep(BOE_DELAY)
    if s is None or s.empty:
        return {}
    return {indic["col"]: s}


# -- ECB Data Portal --

def _fetch_ecb_history(indic: dict) -> dict[str, pd.Series]:
    s = ecb_src.fetch_series_as_pandas(indic["source_id"], col_name=indic["col"])
    time.sleep(ECB_DELAY)
    if s is None or s.empty:
        return {}
    return {indic["col"]: s}


# -- Bank of Canada Valet --

def _fetch_boc_history(indic: dict) -> dict[str, pd.Series]:
    s = boc_src.fetch_series_as_pandas(indic["source_id"], col_name=indic["col"])
    time.sleep(BOC_DELAY)
    if s is None or s.empty:
        return {}
    return {indic["col"]: s}


# -- StatCan WDS --

def _fetch_statcan_history(indic: dict) -> dict[str, pd.Series]:
    s = statcan_src.fetch_series_as_pandas(indic["source_id"], col_name=indic["col"])
    time.sleep(STATCAN_DELAY)
    if s is None or s.empty:
        return {}
    return {indic["col"]: s}


# -- ONS --

def _fetch_ons_history(indic: dict) -> dict[str, pd.Series]:
    s = ons_src.fetch_series_as_pandas(indic["source_id"], col_name=indic["col"])
    time.sleep(ONS_DELAY)
    if s is None or s.empty:
        return {}
    return {indic["col"]: s}


# -- Bundesbank --

def _fetch_bundesbank_history(indic: dict) -> dict[str, pd.Series]:
    s = bundesbank_src.fetch_series_as_pandas(indic["source_id"], col_name=indic["col"])
    time.sleep(BUNDESBANK_DELAY)
    if s is None or s.empty:
        return {}
    return {indic["col"]: s}


# -- ABS --

def _fetch_abs_history(indic: dict) -> dict[str, pd.Series]:
    s = abs_src.fetch_series_as_pandas(indic["source_id"], col_name=indic["col"])
    time.sleep(ABS_DELAY)
    if s is None or s.empty:
        return {}
    return {indic["col"]: s}


# -- ISTAT --

def _fetch_istat_history(indic: dict) -> dict[str, pd.Series]:
    s = istat_src.fetch_series_as_pandas(indic["source_id"], col_name=indic["col"])
    time.sleep(ISTAT_DELAY)
    if s is None or s.empty:
        return {}
    return {indic["col"]: s}


# -- BLS --

def _fetch_bls_history(indic: dict) -> dict[str, pd.Series]:
    s = bls_src.fetch_series_as_pandas(indic["source_id"], col_name=indic["col"])
    time.sleep(BLS_DELAY)
    if s is None or s.empty:
        return {}
    return {indic["col"]: s}


def _fetch_insee_history(indic: dict) -> dict[str, pd.Series]:
    s = insee_src.fetch_series_as_pandas(indic["source_id"], col_name=indic["col"])
    time.sleep(INSEE_DELAY)
    return {indic["col"]: s} if s is not None and not s.empty else {}


def _fetch_bdf_history(indic: dict) -> dict[str, pd.Series]:
    s = bdf_src.fetch_series_as_pandas(indic["source_id"], col_name=indic["col"])
    time.sleep(BDF_DELAY)
    return {indic["col"]: s} if s is not None and not s.empty else {}


# -- §3.13 long-run sources (Shiller / Ken French / JST) history --

def _fetch_shiller_history(indic: dict) -> dict[str, pd.Series]:
    s = shiller_src.fetch_series_as_pandas(indic["source_id"], col_name=indic["col"])
    time.sleep(SHILLER_DELAY)
    return {indic["col"]: s} if s is not None and not s.empty else {}


def _fetch_french_history(indic: dict) -> dict[str, pd.Series]:
    s = french_src.fetch_series_as_pandas(indic["source_id"], col_name=indic["col"])
    time.sleep(FRENCH_DELAY)
    return {indic["col"]: s} if s is not None and not s.empty else {}


def _fetch_jst_history(indic: dict) -> dict[str, pd.Series]:
    s = jst_src.fetch_series_as_pandas(indic["source_id"], col_name=indic["col"])
    time.sleep(JST_DELAY)
    return {indic["col"]: s} if s is not None and not s.empty else {}


def _fetch_atlanta_fed_history(indic: dict) -> dict[str, pd.Series]:
    s = atlanta_fed_src.fetch_series_as_pandas(indic["source_id"], col_name=indic["col"])
    time.sleep(ATLANTA_FED_DELAY)
    return {indic["col"]: s} if s is not None and not s.empty else {}


# -- BoJ Time-Series Data Search --

def _fetch_boj_history(indic: dict) -> dict[str, pd.Series]:
    s = boj_src.fetch_series_as_pandas(indic["source_id"], col_name=indic["col"])
    time.sleep(BOJ_DELAY)
    if s is None or s.empty:
        return {}
    return {indic["col"]: s}


# -- e-Stat --

def _fetch_estat_history(indic: dict) -> dict[str, pd.Series]:
    s = estat_src.fetch_series_as_pandas(indic["source_id"], col_name=indic["col"])
    time.sleep(ESTAT_DELAY)
    if s is None or s.empty:
        return {}
    return {indic["col"]: s}


# -- Nasdaq Data Link --

def _fetch_ndl_history(indic: dict) -> dict[str, pd.Series]:
    s = ndl_src.fetch_series_as_pandas(
        indic["source_id"],
        sub_field=indic.get("sub_field", ""),
        col_name=indic["col"],
    )
    time.sleep(NDL_DELAY)
    if s is None or s.empty:
        return {}
    return {indic["col"]: s}


# -- LBMA --

def _fetch_lbma_history(indic: dict) -> dict[str, pd.Series]:
    s = lbma_src.fetch_series_as_pandas(
        indic["source_id"],
        sub_field=indic.get("sub_field", "USD"),
        col_name=indic["col"],
    )
    time.sleep(LBMA_DELAY)
    if s is None or s.empty:
        return {}
    return {indic["col"]: s}


# -- ifo (shares the workbook download with snapshot via module cache) --

_IFO_MONTHLY_DF: pd.DataFrame | None = None


def _get_ifo_monthly_df(ifo_indicators: list[dict]) -> pd.DataFrame | None:
    """Fetch + parse the ifo workbook once per run; cache the monthly DF."""
    global _IFO_MONTHLY_DF
    if _IFO_MONTHLY_DF is not None:
        return _IFO_MONTHLY_DF
    try:
        url, xlsx = ifo_src.resolve_workbook()
        print(f"  [ifo] Resolved workbook: {url}  ({len(xlsx):,} bytes)")
        _IFO_MONTHLY_DF = ifo_src.parse_workbook(xlsx, ifo_indicators)
    except Exception as e:
        print(f"  [ifo] Workbook fetch/parse failed: {e}")
        _IFO_MONTHLY_DF = pd.DataFrame()
    return _IFO_MONTHLY_DF


def _fetch_ifo_history(
    indic: dict,
    ifo_indicators: list[dict],
) -> dict[str, pd.Series]:
    monthly = _get_ifo_monthly_df(ifo_indicators)
    if monthly is None or monthly.empty or indic["col"] not in monthly.columns:
        return {}
    s = monthly[indic["col"]].dropna()
    if s.empty:
        return {}
    s.name = indic["col"]
    return {indic["col"]: s}


# -- Top-level history builder --

def _history_for_indicator(
    indic: dict,
    ifo_indicators: list[dict],
) -> dict[str, pd.Series]:
    src = indic["source"]
    if src == "FRED" and indic["country"] == "USA":
        return _fetch_fred_us_history(indic)
    if src == "FRED":
        return _fetch_fred_intl_history(indic)
    if src == "OECD":
        return _fetch_oecd_history(indic)
    if src == "World Bank":
        return _fetch_wb_history(indic)
    if src == "IMF":
        return _fetch_imf_history(indic)
    if src == "DB.nomics":
        return _fetch_dbnomics_history(indic)
    if src == "BoE":
        return _fetch_boe_history(indic)
    if src == "ECB":
        return _fetch_ecb_history(indic)
    if src == "BoJ":
        return _fetch_boj_history(indic)
    if src == "BoC":
        return _fetch_boc_history(indic)
    if src == "StatCan":
        return _fetch_statcan_history(indic)
    if src == "ONS":
        return _fetch_ons_history(indic)
    if src == "Bundesbank":
        return _fetch_bundesbank_history(indic)
    if src == "ABS":
        return _fetch_abs_history(indic)
    if src == "ISTAT":
        return _fetch_istat_history(indic)
    if src == "BLS":
        return _fetch_bls_history(indic)
    if src == "INSEE":
        return _fetch_insee_history(indic)
    if src == "Banque de France":
        return _fetch_bdf_history(indic)
    if src == "e-Stat":
        return _fetch_estat_history(indic)
    if src == "Nasdaq Data Link":
        return _fetch_ndl_history(indic)
    if src == "LBMA":
        return _fetch_lbma_history(indic)
    if src == "Shiller":
        return _fetch_shiller_history(indic)
    if src == "KenFrench":
        return _fetch_french_history(indic)
    if src == "JST":
        return _fetch_jst_history(indic)
    if src == "AtlantaFed":
        return _fetch_atlanta_fed_history(indic)
    if src == "ifo":
        return _fetch_ifo_history(indic, ifo_indicators)
    print(f"  [WARN] Unknown source '{src}' in history fetch")
    return {}


def build_hist_df(
    indicators: list[dict],
) -> tuple[pd.DataFrame, dict[str, dict]]:
    """Build the wide-form Friday-spine history DataFrame.

    Returns (hist, provenance). `provenance[col_name]` is the indicator dict
    whose raw series actually populated the column. When multiple sources
    target the same col_name (e.g. JPN_POLICY_RATE on FRED, DB.nomics and
    BoJ), the source whose raw series has the most recent non-null
    observation wins — data freshness, not library load order. Ties are
    broken in favour of the source that arrived first (stable order).
    """
    today = date.today()
    spine = build_friday_spine(HIST_START, today)

    ifo_indicators = [i for i in indicators if i["source"] == "ifo"]

    columns: dict[str, pd.Series] = {}
    provenance: dict[str, dict] = {}
    last_obs: dict[str, pd.Timestamp] = {}

    for indic in indicators:
        label = f"{indic['source']}/{indic['col']}/hist"
        print(f"  [{label}]")
        try:
            series_dict = _history_for_indicator(indic, ifo_indicators)
        except Exception as e:
            print(f"  [{label}] history failed: {e}")
            continue
        for col_name, s in series_dict.items():
            nonnull = s.dropna()
            new_last = nonnull.index.max() if not nonnull.empty else pd.NaT
            combined = (
                s.reindex(spine.union(s.index)).sort_index().ffill().reindex(spine)
            )
            if col_name not in columns:
                columns[col_name] = combined
                provenance[col_name] = indic
                last_obs[col_name] = new_last
                continue

            cur_last = last_obs[col_name]
            cur_src = provenance[col_name]["source"]
            # Data quality first: the source with the most recent observation
            # wins (higher cadence ⇒ fresher). On a tie (equal latest period),
            # prefer the ultimate/primary source over an aggregator.
            fresher = pd.notna(new_last) and (
                pd.isna(cur_last) or new_last > cur_last
            )
            tie = (
                pd.notna(new_last) and pd.notna(cur_last) and new_last == cur_last
            )
            tie_to_primary = tie and (
                _source_rank(indic["source"]) > _source_rank(cur_src)
            )
            new_wins = fresher or tie_to_primary
            cur_str = cur_last.date().isoformat() if pd.notna(cur_last) else "NaT"
            new_str = new_last.date().isoformat() if pd.notna(new_last) else "NaT"
            if new_wins:
                print(
                    f"    [merge] {col_name}: replaced {cur_src} (last={cur_str}) "
                    f"with {indic['source']} (last={new_str})"
                )
                columns[col_name] = combined
                provenance[col_name] = indic
                last_obs[col_name] = new_last
            else:
                print(
                    f"    [merge] {col_name}: kept {cur_src} (last={cur_str}) "
                    f"over {indic['source']} (last={new_str})"
                )

    hist = pd.DataFrame(columns, index=spine)
    hist.index.name = "Date"

    print(f"  macro_economic_hist: {len(hist)} rows × {len(hist.columns)} data columns")
    return hist, provenance


# -- Metadata prefix rows (one per metadata field × per column) --

HIST_METADATA_ROWS = [
    "Column ID", "Series ID", "Source", "Indicator",
    "Country", "Country Name", "Region",
    "Category", "Subcategory", "Concept", "cycle_timing",
    "Units", "Frequency", "Last Updated",
]


def _build_hist_metadata_rows(
    columns: list[str], provenance: dict[str, dict],
) -> list[list]:
    """
    Build the 14 metadata rows that prefix macro_economic_hist.csv.

    `provenance[col_name]` is the indicator dict that actually populated the
    column in build_hist_df (freshness-wins merge), so the Source / Series ID
    / Indicator rows here truthfully describe what's in each column even when
    multiple sources targeted the same col_name.

    The column → country split is recovered by stripping the leading
    "<COUNTRY>_" prefix when the indicator is a multi-country fan-out.
    """
    country_meta = countries_src.country_meta()

    lookup: dict[str, tuple[dict, str]] = {}
    for col_name, indic in provenance.items():
        if indic["country"]:
            lookup[col_name] = (indic, indic["country"])
        else:
            # Multi-country fan-out: col_name == f"{country}_{indic['col']}"
            base = indic["col"]
            country = ""
            if col_name.endswith("_" + base):
                code = col_name[: -(len(base) + 1)]
                if code in country_meta:
                    country = code
            lookup[col_name] = (indic, country)

    ts = _utc_ts()

    rows: list[list] = [[label] for label in HIST_METADATA_ROWS]

    for col_name in columns:
        entry = lookup.get(col_name)
        if entry is None:
            # Unknown column: blank metadata.
            for r in rows:
                r.append("")
            continue
        indic, country = entry
        cname, region = country_meta.get(country, (country, ""))
        vals = {
            "Column ID":    col_name,
            "Series ID":    indic["source_id"],
            "Source":       indic["source"],
            "Indicator":    indic["name"],
            "Country":      country,
            "Country Name": cname,
            "Region":       region,
            "Category":     indic["category"],
            "Subcategory":  indic["subcategory"],
            "Concept":      indic["concept"],
            "cycle_timing": indic["cycle_timing"],
            "Units":        indic["units"],
            "Frequency":    indic["frequency"],
            "Last Updated": ts,
        }
        for r, label in zip(rows, HIST_METADATA_ROWS):
            r.append(vals[label])

    return rows


# ---------------------------------------------------------------------------
# SHEETS PUSH
# ---------------------------------------------------------------------------

def push_snapshot_to_sheets(df: pd.DataFrame) -> None:
    try:
        push_df_to_sheets(
            get_sheets_service(GOOGLE_CREDENTIALS_JSON),
            SHEET_ID,
            SNAPSHOT_TAB,
            df,
            label="macro_economic",
        )
    except Exception as e:
        print(f"  [macro_economic] snapshot Sheets push failed: {e}")


def push_hist_to_sheets(df: pd.DataFrame, provenance: dict[str, dict]) -> None:
    if df.empty:
        return
    try:
        columns = list(df.columns)
        meta_rows = _build_hist_metadata_rows(columns, provenance)

        df_out = df.reset_index()
        df_out["Date"] = df_out["Date"].dt.strftime("%Y-%m-%d")

        push_df_to_sheets(
            get_sheets_service(GOOGLE_CREDENTIALS_JSON),
            SHEET_ID,
            HIST_TAB,
            df_out,
            label="macro_economic_hist",
            prefix_rows=meta_rows,
        )
    except Exception as e:
        print(f"  [macro_economic] hist Sheets push failed: {e}")


def save_hist_csv(df: pd.DataFrame, provenance: dict[str, dict]) -> None:
    """
    Write macro_economic_hist.csv.  Format: 14 metadata prefix rows,
    then a header row (Date + column names), then one row per Friday.

    Routes through library_utils.write_hist_with_archive() to preserve any
    rows that would otherwise be lost to source-side floor advancement
    (per forward_plan §3.1.1 — e.g. ICE BofA 3-yr rolling window).
    """
    columns = list(df.columns)
    meta_rows = _build_hist_metadata_rows(columns, provenance)

    df_out = df.reset_index()
    write_hist_with_archive(df_out, HIST_CSV, prefix_rows=meta_rows)
    print(f"  Written {len(df)} rows + {len(meta_rows)} metadata rows to {HIST_CSV}")


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
    push_snapshot_to_sheets(snap_df)

    # History (Friday-spine wide DataFrame, 1947-present)
    print("\n[History] Fetching full history ...")
    hist_df, provenance = build_hist_df(indicators)
    save_hist_csv(hist_df, provenance)
    push_hist_to_sheets(hist_df, provenance)

    print(f"\n  macro_economic run completed in {time.time() - t0:.1f}s")


if __name__ == "__main__":
    run_phase_macro_economic()
