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
# ENTRY POINT (skeleton only in S2.C6 — no fetching yet)
# ---------------------------------------------------------------------------

def run_phase_macro_economic() -> None:
    print("\n" + "=" * 60)
    print("macro_economic — Unified Economic Data Coordinator (skeleton)")
    print("=" * 60)

    t0 = time.time()
    indicators = load_all_indicators()
    summarize(indicators)

    # Validate that every indicator carries a canonical country code or
    # is explicitly multi-country.  Flags misconfigured library rows.
    canonical = set(countries_src.country_meta().keys())
    bad = [i for i in indicators if i["country"] and i["country"] not in canonical]
    if bad:
        print(f"  [WARN] {len(bad)} indicator(s) have non-canonical country codes:")
        for i in bad:
            print(f"    - {i['source']} / {i['col']}: country={i['country']!r}")
    else:
        print("  [OK] Every single-country indicator uses a canonical country code.")

    print(f"\n  Skeleton run completed in {time.time() - t0:.1f}s")
    print("  (Snapshot + history fetch land in subsequent commits.)")


if __name__ == "__main__":
    run_phase_macro_economic()
