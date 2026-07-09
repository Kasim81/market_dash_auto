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
import glob
import os
import re
import time
from datetime import date, datetime, timezone

import pandas as pd

from sources import countries as countries_src
from sources import dbnomics as dbn_src
from sources import ism_prnewswire as ism_src
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
from sources import ny_fed as ny_fed_src
from sources import imf_sdmx as imf_sdmx_src
from sources.base import build_friday_spine, get_sheets_service, push_df_to_sheets

from library_utils import write_hist_with_archive, bounded_spine_fill


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
    indicators.extend(ny_fed_src.load_library())
    indicators.extend(imf_sdmx_src.load_library())
    return _attach_tiers(indicators)


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
        # internal only (dropped by SNAPSHOT_COLUMNS on CSV write) — carries
        # declared source authority into _dedupe_snapshot_rows.
        "_tier":        int(indic.get("tier", 0) or 0),
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


# ---------------------------------------------------------------------------
# TIER (declared source authority) — read from the `tier` column in each
# macro_library_*.csv. 0 = primary/national/direct; 1 = aggregator (FRED,
# OECD, IMF, World Bank, DB.nomics); 2 = last-resort. Absent column ⇒ 0.
# ---------------------------------------------------------------------------
_DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")

# filename stem -> the `source` label the loaders emit (for the tier join).
# Derived from the shared identity table (§2.C C2) — one registration point.
from sources import LABEL_BY_STEM as _FILE_SOURCE  # noqa: E402


def _load_tier_map() -> dict[tuple[str, str], int]:
    """Map (source_label, series_id) -> tier by reading every library CSV."""
    tiers: dict[tuple[str, str], int] = {}
    for path in glob.glob(os.path.join(_DATA_DIR, "macro_library_*.csv")):
        stem = os.path.basename(path)[len("macro_library_"):-len(".csv")]
        src = _FILE_SOURCE.get(stem)
        if not src:
            continue
        try:
            with open(path, newline="") as fh:
                rdr = _csv.DictReader(fh)
                if "tier" not in (rdr.fieldnames or []):
                    continue
                for row in rdr:
                    sid = (row.get("series_id") or "").strip()
                    t = (row.get("tier") or "").strip()
                    if sid and t:
                        try:
                            tiers[(src, sid)] = int(t)
                        except ValueError:
                            pass
        except FileNotFoundError:
            continue
    return tiers


def _load_override_map() -> dict[tuple[str, str], int]:
    """Map (source_label, series_id) -> freshness_override_days, read from
    every library CSV (same sweep shape as _load_tier_map). Drives the
    bounded-fill limit alongside data/freshness_thresholds.csv."""
    overrides: dict[tuple[str, str], int] = {}
    for path in glob.glob(os.path.join(_DATA_DIR, "macro_library_*.csv")):
        stem = os.path.basename(path)[len("macro_library_"):-len(".csv")]
        src = _FILE_SOURCE.get(stem)
        if not src:
            continue
        try:
            with open(path, newline="") as fh:
                rdr = _csv.DictReader(fh)
                if "freshness_override_days" not in (rdr.fieldnames or []):
                    continue
                for row in rdr:
                    sid = (row.get("series_id") or "").strip()
                    o = (row.get("freshness_override_days") or "").strip()
                    if sid and o:
                        try:
                            overrides[(src, sid)] = int(o)
                        except ValueError:
                            pass
        except FileNotFoundError:
            continue
    return overrides


def _attach_tiers(indicators: list[dict]) -> list[dict]:
    """Set indic['tier'] and indic['freshness_override_days'] from the
    library CSVs (tier default 0; override default None)."""
    tiers = _load_tier_map()
    overrides = _load_override_map()
    for ind in indicators:
        key = (ind.get("source", ""), ind.get("source_id", ""))
        ind["tier"] = tiers.get(key, 0)
        ind["freshness_override_days"] = overrides.get(key)
    return indicators


# ---- bounded forward-fill (no fabricated currency past a series' cadence) --
#
# The Friday-spine hist forward-fills each raw series so a monthly print
# "is" the value for the following weeks — legitimate step-function
# semantics. What is NOT legitimate is unbounded fill: a series whose
# publisher dies keeps emitting its last value forever, silently freezing
# every composite and z-score built on it (the JP_INFL1 / EU_INFL1 /
# CN_INFL1 bug class). Fill is therefore bounded at 2x the series'
# staleness tolerance — the same registry (freshness_thresholds.csv +
# per-row freshness_override_days) whose 2x line is where data_audit
# Section C declares a series EXPIRED. Beyond the bound the column is NaN:
# a dead series visibly ends.

_FRESHNESS_DEFAULTS: dict[str, int] | None = None


def _freshness_default_days(frequency: str) -> int:
    """Per-frequency staleness tolerance from data/freshness_thresholds.csv."""
    global _FRESHNESS_DEFAULTS
    if _FRESHNESS_DEFAULTS is None:
        _FRESHNESS_DEFAULTS = {}
        try:
            with open(os.path.join(_DATA_DIR, "freshness_thresholds.csv"),
                      newline="") as fh:
                for row in _csv.DictReader(fh):
                    freq = (row.get("frequency") or "").strip().lower()
                    days = (row.get("default_days") or "").strip()
                    if freq and days:
                        try:
                            _FRESHNESS_DEFAULTS[freq] = int(days)
                        except ValueError:
                            pass
        except FileNotFoundError:
            pass
    return _FRESHNESS_DEFAULTS.get((frequency or "").strip().lower(), 45)


def _fill_limit_days(indic: dict) -> int:
    """Forward-fill bound for one indicator: 2x its staleness tolerance."""
    override = indic.get("freshness_override_days")
    tolerance = int(override) if override else \
        _freshness_default_days(indic.get("frequency", ""))
    return 2 * tolerance


# Shared with fetch_hist since §2.A A16 — canonical implementation lives in
# library_utils (tech_manual §11 Pattern 12).
_bounded_spine_fill = bounded_spine_fill


# ---- measure-kind / cadence / period helpers for winner selection ----
_CAD_ORDER = {"daily": 0, "business daily": 0, "weekly": 1, "monthly": 2,
              "quarterly": 3, "annual": 4, "annually": 4, "yearly": 4}


def _cad_rank(freq: str) -> int:
    return _CAD_ORDER.get((freq or "").strip().lower(), 5)


def _cad_days(freq: str) -> int:
    return {0: 3, 1: 8, 2: 31, 3: 93, 4: 366, 5: 93}[_cad_rank(freq)]


def _measure_kind(units: str) -> str:
    """Coarse measure classification so we never let an index compete with a
    YoY rate for the same column (the JPN_CPI class of bug)."""
    u = (units or "").lower()
    if any(k in u for k in ("%", "percent", "change", "year-on-year", "yoy", "growth")):
        return "rate"
    if "index" in u:
        return "index"
    if any(k in u for k in ("per annum", "bp", "basis point", "yield")):
        return "rate"
    return "level"


def _period_to_date(p: str):
    """Parse a Last Period string to a comparable date (period end)."""
    p = (p or "").strip()
    if not p:
        return None
    m = re.match(r"^(\d{4})-Q([1-4])$", p)
    if m:
        y, q = int(m.group(1)), int(m.group(2))
        return date(y, q * 3, 28)
    m = re.match(r"^(\d{4})[-/](\d{2})[-/](\d{2})$", p)
    if m:
        return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    m = re.match(r"^(\d{4})[-/](\d{2})$", p) or re.match(r"^(\d{4})(\d{2})$", p)
    if m:
        return date(int(m.group(1)), int(m.group(2)), 28)
    m = re.match(r"^(\d{4})$", p)
    if m:
        return date(int(m.group(1)), 12, 31)
    return None


def _select_winner(cands: list[dict]) -> dict:
    """Pick the winning candidate for one (Country, Col) group.

    Each cand: {has_data, kind, cad_rank, cad_days, last(date|None),
    tier, rank(primary=1), order, payload}.

    Rule (per the 2026-06-18 precedence policy):
      * candidates that mix measure-kinds (e.g. index vs YoY) are a DEFINITION
        collision — do NOT guess; fall back to the legacy freshest→primary pick
        so behaviour is unchanged until the column is split by definition.
      * otherwise finest cadence wins, then lowest tier, then freshest — but a
        candidate stale by >2× its own cadence relative to the freshest in the
        group is dropped first (so a fresh coarser/fallback source takes over).
    """
    withdata = [c for c in cands if c["has_data"]]
    if not withdata:
        return cands[0]
    if len({c["kind"] for c in withdata}) > 1:
        # definition collision → legacy behaviour (freshest, then primary)
        return max(withdata, key=lambda c: (c["last"] or date.min, c["rank"], -c["order"]))
    dated = [c["last"] for c in withdata if c["last"]]
    best = max(dated) if dated else None
    fresh = [c for c in withdata
             if c["last"] is None or best is None
             or (best - c["last"]).days <= 2 * c["cad_days"]]
    pool = fresh or withdata
    return min(pool, key=lambda c: (
        c["cad_rank"], c["tier"],
        -(c["last"].toordinal() if c["last"] else 0), c["order"]))


def _dedupe_snapshot_rows(rows: list[dict]) -> list[dict]:
    """Collapse rows that share a (Country, Col) to a single winning source
    using the tier-aware, cadence-first, staleness-fallback policy."""
    order: list[tuple[str, str]] = []
    groups: dict[tuple[str, str], list[dict]] = {}
    for r in rows:
        key = (r.get("Country", ""), r.get("Col", ""))
        if key not in groups:
            groups[key] = []
            order.append(key)
        groups[key].append(r)

    out: list[dict] = []
    for key in order:
        grp = groups[key]
        if len(grp) == 1:
            out.append(grp[0])
            continue
        cands = [{
            "has_data":  r.get("Latest Value") is not None,
            "kind":      _measure_kind(r.get("Units", "")),
            "cad_rank":  _cad_rank(r.get("Frequency", "")),
            "cad_days":  _cad_days(r.get("Frequency", "")),
            "last":      _period_to_date(r.get("Last Period", "")),
            "tier":      int(r.get("_tier", 0) or 0),
            "rank":      _source_rank(r.get("Source", "")),
            "order":     i,
            "payload":   r,
        } for i, r in enumerate(grp)]
        out.append(_select_winner(cands)["payload"])
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

def _guarded_dbnomics_obs(indic: dict, doc: dict) -> list[tuple[str, float]]:
    """Parse DB.nomics observations, drop any outside the indicator's declared
    plausibility band, then (for ISM columns only) splice the latest official
    ISM press-release point on top when it's newer than the mirror. The band +
    the ISM fallback are the two-part fix for the DB.nomics ISM mirror going
    both corrupted (values ~10 for a 0-100 index) and chronically stale."""
    obs = dbn_src.parse_observations(doc)
    obs = dbn_src.filter_plausible(
        obs, indic.get("plausible_min"), indic.get("plausible_max"), indic["col"]
    )
    return _maybe_ism_fallback(indic, obs)


def _maybe_ism_fallback(
    indic: dict, obs: list[tuple[str, float]]
) -> list[tuple[str, float]]:
    """For an ISM column, replace/append the current month from ISM's official
    release when it is newer than the last DB.nomics observation. No-op for
    non-ISM columns or when the release fetch is unavailable (no Bright Data
    credentials, discovery/parse miss) — the series is returned unchanged."""
    fresh = ism_src.latest_value_for_col(indic["col"])
    if fresh is None:
        return obs
    f_period, f_val = fresh
    f_date = dbn_src.parse_period_to_date(f_period)
    if f_date is None:
        return obs
    f_ym = f_date.strftime("%Y-%m")
    # Drop any mirror obs from the same month — the official value wins.
    kept = [
        (p, v) for (p, v) in obs
        if (dbn_src.parse_period_to_date(p) or datetime.min).strftime("%Y-%m") != f_ym
    ]
    last_date = dbn_src.parse_period_to_date(kept[-1][0]) if kept else None
    if last_date is not None and f_date <= last_date:
        # Official release is not newer than the mirror — leave obs untouched.
        return obs
    spliced = kept + [(f_period, f_val)]
    spliced.sort(key=lambda pv: dbn_src.parse_period_to_date(pv[0]) or datetime.min)
    print(
        f"    [ISM fallback] {indic['col']}: using official release point "
        f"{f_period}={f_val} (last DB.nomics obs: "
        f"{obs[-1][0] if obs else 'none'})",
        flush=True,
    )
    return spliced


def _fetch_dbnomics_snapshot(indic: dict, fetched_at: str) -> list[dict]:
    doc = dbn_src.fetch_series(indic["source_id"])
    time.sleep(DBN_DELAY)
    if doc is None:
        # Even with the mirror down, an ISM column may still refresh from the
        # official release (guard/fallback handle the empty-obs case).
        obs = _maybe_ism_fallback(indic, [])
        if not obs:
            return [_blank_row(indic, indic["country"], indic["col"], fetched_at)]
    else:
        obs = _guarded_dbnomics_obs(indic, doc)
    if not obs:
        return [_blank_row(indic, indic["country"], indic["col"], fetched_at)]
    latest = obs[-1][1]
    prior  = obs[-2][1] if len(obs) >= 2 else None
    last_period = obs[-1][0]
    return [_make_row(indic, indic["country"], indic["col"],
                      latest, prior, last_period, fetched_at)]


# -- Standard per-series sources: delays + shared handler factory ----------
#
# Per-source politeness delays (seconds between API calls). The §3.13
# long-run sources (Shiller / Ken French / JST / the Fed nowcasts) cache one
# workbook/ZIP/.dta per process so the whole library costs one download —
# their delay only matters between distinct downloads, keep it short.
BOE_DELAY = 0.6
ECB_DELAY = 0.6
BOC_DELAY = 0.4
STATCAN_DELAY = 0.4
ONS_DELAY = 0.4
BUNDESBANK_DELAY = 0.4
ABS_DELAY = 0.4
ISTAT_DELAY = 0.6   # flaky gateway — go gentle
BLS_DELAY = 0.5
INSEE_DELAY = 0.5
BDF_DELAY = 0.5
BOJ_DELAY = 0.6
ESTAT_DELAY = 0.6
NDL_DELAY = 0.6
LBMA_DELAY = 0.6
SHILLER_DELAY = 0.1
FRENCH_DELAY = 0.1
JST_DELAY = 0.1
ATLANTA_FED_DELAY = 0.1
NY_FED_DELAY = 0.1


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


def _make_source_handlers(mod, delay: float, snapshot_kwargs: dict | None = None,
                          sub_field_default: str | None = None):
    """Build the (snapshot, history) handler pair for a standard single-series
    source module exposing ``fetch_series_as_pandas(series_id, ...)``.

    §2.C C2 (2026-07-09): this factory replaced ~21 pairs of near-identical
    hand-written ``_fetch_<src>_{snapshot,history}`` wrappers. Per-source
    variation is carried in the arguments:

    snapshot_kwargs    — extra kwargs for the *snapshot* call only (the
                         source-specific "just the latest couple of points"
                         fast path, e.g. ``{"last_n": 2}`` for ECB or
                         ``{"recent": True}`` for BLS). History always pulls
                         the full series.
    sub_field_default  — for modules whose fetch takes a ``sub_field``
                         (Nasdaq Data Link ``""``, LBMA ``"USD"``): forwarded
                         from the indicator row with this default, on both
                         snapshot and history calls.
    """
    snap_kw = dict(snapshot_kwargs or {})

    def snapshot(indic: dict, fetched_at: str) -> list[dict]:
        kw = dict(snap_kw)
        if sub_field_default is not None:
            kw["sub_field"] = indic.get("sub_field", sub_field_default)
        s = mod.fetch_series_as_pandas(indic["source_id"], **kw)
        time.sleep(delay)
        return _snapshot_from_series(s, indic, fetched_at)

    def history(indic: dict) -> dict[str, pd.Series]:
        kw = {}
        if sub_field_default is not None:
            kw["sub_field"] = indic.get("sub_field", sub_field_default)
        s = mod.fetch_series_as_pandas(indic["source_id"],
                                       col_name=indic["col"], **kw)
        time.sleep(delay)
        return {indic["col"]: s} if s is not None and not s.empty else {}

    return snapshot, history


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
    _validate_dispatch(indicators)
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
            got = _SOURCE_HANDLERS[src][0](indic, fetched_at)
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

def _fetch_fred_history(indic: dict) -> dict[str, pd.Series]:
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
        # Mirror down: an ISM column may still refresh from the official release.
        obs = _maybe_ism_fallback(indic, [])
    else:
        obs = _guarded_dbnomics_obs(indic, doc)
    if not obs:
        return {}
    s = dbn_src.obs_to_series(obs, indic["col"])
    if s.empty:
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

def _fetch_fred_snapshot(indic: dict, fetched_at: str) -> list[dict]:
    """US rows use the latest/prior fast path; intl rows the desc-order probe."""
    if indic["country"] == "USA":
        return _fetch_fred_us_snapshot(indic, fetched_at)
    return _fetch_fred_intl_snapshot(indic, fetched_at)


# ---------------------------------------------------------------------------
# SOURCE DISPATCH (§2.C C2, 2026-07-09)
# ---------------------------------------------------------------------------
# One registry entry per source label: (snapshot_handler, history_handler).
# Standard single-series sources come from _make_source_handlers; the five
# structurally-special sources (FRED us/intl split, the OECD/WB/IMF
# multi-country fan-outs, DB.nomics with the plausibility guard + ISM
# press-release fallback) keep their hand-written handlers, registered here.
# "ifo" is deliberately absent: its workbook is fetched once per run and
# fanned out as a batch (see _fetch_ifo_snapshot_batch / _fetch_ifo_history).
#
# The label strings must match what each sources/<mod>.load_library() emits
# — the shared identity table is sources.SOURCE_REGISTRY, and
# _validate_dispatch() hard-fails the run on any loaded indicator whose
# label has no entry here (replacing the old silent "[WARN] Unknown
# source" skip).

_SOURCE_HANDLERS: dict[str, tuple] = {
    "FRED":       (_fetch_fred_snapshot, _fetch_fred_history),
    "OECD":       (_fetch_oecd_snapshot, _fetch_oecd_history),
    "World Bank": (_fetch_wb_snapshot, _fetch_wb_history),
    "IMF":        (_fetch_imf_snapshot, _fetch_imf_history),
    "DB.nomics":  (_fetch_dbnomics_snapshot, _fetch_dbnomics_history),
    "BoE":        _make_source_handlers(boe_src, BOE_DELAY),
    "ECB":        _make_source_handlers(ecb_src, ECB_DELAY,
                                        snapshot_kwargs={"last_n": 2}),
    "BoJ":        _make_source_handlers(boj_src, BOJ_DELAY),
    "e-Stat":     _make_source_handlers(estat_src, ESTAT_DELAY),
    "Nasdaq Data Link": _make_source_handlers(ndl_src, NDL_DELAY,
                                              sub_field_default=""),
    "LBMA":       _make_source_handlers(lbma_src, LBMA_DELAY,
                                        sub_field_default="USD"),
    "BoC":        _make_source_handlers(boc_src, BOC_DELAY,
                                        snapshot_kwargs={"recent": 2}),
    "StatCan":    _make_source_handlers(statcan_src, STATCAN_DELAY,
                                        snapshot_kwargs={"latest_n": 2}),
    "ONS":        _make_source_handlers(ons_src, ONS_DELAY),
    "Bundesbank": _make_source_handlers(bundesbank_src, BUNDESBANK_DELAY,
                                        snapshot_kwargs={"last_n": 2}),
    "ABS":        _make_source_handlers(abs_src, ABS_DELAY,
                                        snapshot_kwargs={"last_n": 2}),
    "ISTAT":      _make_source_handlers(istat_src, ISTAT_DELAY,
                                        snapshot_kwargs={"last_n": 3}),
    "BLS":        _make_source_handlers(bls_src, BLS_DELAY,
                                        snapshot_kwargs={"recent": True}),
    "INSEE":      _make_source_handlers(insee_src, INSEE_DELAY),
    "Banque de France": _make_source_handlers(bdf_src, BDF_DELAY),
    "Shiller":    _make_source_handlers(shiller_src, SHILLER_DELAY),
    "KenFrench":  _make_source_handlers(french_src, FRENCH_DELAY),
    "JST":        _make_source_handlers(jst_src, JST_DELAY),
    "AtlantaFed": _make_source_handlers(atlanta_fed_src, ATLANTA_FED_DELAY),
    "NYFed":      _make_source_handlers(ny_fed_src, NY_FED_DELAY),
    "IMF SDMX":   _make_source_handlers(imf_sdmx_src, imf_sdmx_src.IMF_SDMX_DELAY,
                                        snapshot_kwargs={"last_n": 13}),
}


def _validate_dispatch(indicators: list[dict]) -> None:
    """Hard-fail before any network work if a loaded indicator's source label
    has no registered handler — a typo'd or newly-added source must be a loud
    startup error, never a silently skipped library row (§2.C C2)."""
    unknown = sorted({i["source"] for i in indicators}
                     - set(_SOURCE_HANDLERS) - {"ifo"})
    if unknown:
        raise RuntimeError(
            f"No handler registered in _SOURCE_HANDLERS for source label(s) "
            f"{unknown} — add the entry (and, for a new source, a "
            f"sources.SOURCE_REGISTRY SourceSpec)."
        )


def _history_for_indicator(
    indic: dict,
    ifo_indicators: list[dict],
) -> dict[str, pd.Series]:
    src = indic["source"]
    if src == "ifo":
        return _fetch_ifo_history(indic, ifo_indicators)
    return _SOURCE_HANDLERS[src][1](indic)


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
    _validate_dispatch(indicators)
    today = date.today()
    spine = build_friday_spine(HIST_START, today)

    ifo_indicators = [i for i in indicators if i["source"] == "ifo"]

    # Collect every candidate series per column, then pick one winner with the
    # tier-aware, cadence-first, staleness-fallback policy (_select_winner).
    cand_lists: dict[str, list[dict]] = {}
    col_order: list[str] = []
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
            fill_limit = _fill_limit_days(indic)
            combined = _bounded_spine_fill(s, spine, fill_limit)
            if col_name not in cand_lists:
                cand_lists[col_name] = []
                col_order.append(col_name)
            cand_lists[col_name].append({
                "has_data":  pd.notna(new_last),
                "kind":      _measure_kind(indic.get("units", "")),
                "cad_rank":  _cad_rank(indic.get("frequency", "")),
                "cad_days":  _cad_days(indic.get("frequency", "")),
                "last":      (new_last.date() if pd.notna(new_last) else None),
                "tier":      int(indic.get("tier", 0) or 0),
                "rank":      _source_rank(indic["source"]),
                "order":     len(cand_lists[col_name]),
                "payload":   {"indic": indic, "series": combined,
                              "last": new_last, "fill_limit": fill_limit},
            })

    columns: dict[str, pd.Series] = {}
    provenance: dict[str, dict] = {}
    for col_name in col_order:
        cands = cand_lists[col_name]
        win = _select_winner(cands)["payload"]
        columns[col_name] = win["series"]
        # Copy so the shared indicator dict isn't mutated; _last_obs feeds
        # the "Last Observation" metadata row and _fill_limit_days feeds the
        # sister-archive trailing-bound enforcement in save_hist_csv.
        provenance[col_name] = {
            **win["indic"],
            "_last_obs": (win["last"].date().isoformat()
                          if pd.notna(win["last"]) else ""),
            "_fill_limit_days": win["fill_limit"],
        }
        if len(cands) > 1:
            others = ", ".join(sorted({c["payload"]["indic"]["source"] for c in cands}
                                      - {win["indic"]["source"]}))
            wl = win["last"].date().isoformat() if pd.notna(win["last"]) else "NaT"
            print(f"    [merge] {col_name}: chose {win['indic']['source']} "
                  f"(tier={win['indic'].get('tier',0)}, last={wl}) over [{others}]")

    hist = pd.DataFrame(columns, index=spine)
    hist.index.name = "Date"

    print(f"  macro_economic_hist: {len(hist)} rows × {len(hist.columns)} data columns")
    return hist, provenance


# -- Metadata prefix rows (one per metadata field × per column) --

HIST_METADATA_ROWS = [
    "Column ID", "Series ID", "Source", "Indicator",
    "Country", "Country Name", "Region",
    "Category", "Subcategory", "Concept", "cycle_timing",
    "Units", "Frequency", "Last Updated", "Last Observation",
]


def _build_hist_metadata_rows(
    columns: list[str], provenance: dict[str, dict],
) -> list[list]:
    """
    Build the 15 metadata rows that prefix macro_economic_hist.csv.

    `provenance[col_name]` is the indicator dict that actually populated the
    column in build_hist_df (freshness-wins merge), so the Source / Series ID
    / Indicator rows here truthfully describe what's in each column even when
    multiple sources targeted the same col_name. "Last Observation" (added
    2026-07-08 with the bounded-fill change) is the per-column date of the
    last *real* raw observation — ground truth for staleness, as opposed to
    the last spine cell, which includes bounded forward-fill.

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
            "Last Observation": indic.get("_last_obs", ""),
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
    Write macro_economic_hist.csv.  Format: 15 metadata prefix rows,
    then a header row (Date + column names), then one row per Friday.

    Routes through library_utils.write_hist_with_archive() to preserve any
    rows that would otherwise be lost to source-side floor advancement
    (per forward_plan §3.1.1 — e.g. ICE BofA 3-yr rolling window).

    trailing_bounds carries each column's (last real observation,
    fill-limit-days) so the sister archive can be held to the same
    bounded-fill invariant as the live file — fabricated fill written to the
    sister before the 2026-07-08 bounded-fill change is cleared on the first
    run, and can never re-enter (the writer knows real-vs-fill exactly).
    """
    columns = list(df.columns)
    meta_rows = _build_hist_metadata_rows(columns, provenance)

    trailing_bounds = {}
    for col, ind in provenance.items():
        last_obs = ind.get("_last_obs")
        limit = ind.get("_fill_limit_days")
        if last_obs and limit:
            trailing_bounds[col] = (last_obs, int(limit))

    df_out = df.reset_index()
    write_hist_with_archive(df_out, HIST_CSV, prefix_rows=meta_rows,
                            trailing_bounds=trailing_bounds)
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
