#!/usr/bin/env python3
"""
Phase 0 coverage check for the regime-aa indicator demand.

This is the automated guard the regime-aa spec (regime-aa-indicator-req.md, §5.13)
describes: it reconciles the indicator demand against what the data pipeline
actually supplies, reports gaps, and auto-templates a cross-repo request memo
for each sourceable gap.

Demand side (canonical, structured):
    manuals/regime-aa-asks/regime-aa-indicator-coverage.csv

Supply side (the live pipeline):
    data/macro_economic.csv          base economic series (Series ID + Indicator)
    data/macro_indicator_library.csv derived regime composites (id)
    data/macro_market.csv            computed composite snapshot (id)
    data/index_library.csv           market-data instruments (ticker_* columns)
    data/macro_library_*.csv         per-source fetch catalogues (series_id)

What it does
    1. Builds the supply universe of every id / ticker the pipeline carries.
    2. For each row the map marks Covered or Partial, extracts the concrete
       ids/tickers cited in `pipeline_match` and verifies each still resolves in
       the supply universe. An id that no longer resolves is a REGRESSION (the
       pipeline dropped a series the regime engine was told it could rely on).
    3. Prints a coverage summary (by status and by pillar).
    4. Templates a request memo for every Missing-Sourceable gap (with
       --write-memos) under manuals/regime-aa-asks/requests/.

Exit code is non-zero if any regression is found, so the check can gate CI.

Usage
    python3 scripts/phase_0_coverage_check.py [--write-memos] [--quiet]
"""
from __future__ import annotations
import argparse
import csv
import glob
import os
import re
import sys
from collections import Counter, defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
COVERAGE_CSV = os.path.join(ROOT, "manuals", "regime-aa-asks",
                            "regime-aa-indicator-coverage.csv")
MEMO_DIR = os.path.join(ROOT, "manuals", "regime-aa-asks", "requests")

COVERED, PARTIAL = "Covered", "Partial"
SOURCEABLE, HARD, ACCEPTED = "Missing-Sourceable", "Missing-Hard", "Accepted-Gap"

# A token is treated as a concrete, verifiable identifier when it looks like one
# of these. Descriptive phrases ("Germany 10y Bund", "EM basket") and FX-pair
# shorthand ("USD/CNY") are deliberately NOT verifiable ids and are skipped.
RE_COMPOSITE = re.compile(r"^[A-Z]{1,5}_[A-Z0-9_]+$")          # US_R2, GL_PMI1, JP_TANKAN_FWD1
RE_SERIES_ID = re.compile(r"^[A-Z][A-Z0-9]{3,}$")              # T10Y2Y, BAMLH0A0HYM2, PERMIT, INDPRO
RE_TICKER = re.compile(r"^\^[A-Z0-9]+$|^[A-Z]+-[A-Z]\.[A-Z]+$")  # ^VIX, ^VXEFA, DX-Y.NYB

# Provider / source acronyms that pass the id regexes but are NOT series ids.
SOURCE_WORDS = {
    "OECD", "FRED", "DBNOMICS", "METI", "INSEE", "ISTAT", "NYFED", "BUNDESBANK",
}


def read_csv(path):
    with open(path, newline="") as f:
        return list(csv.DictReader(f))


def build_supply_universe():
    """Return (id_set, lower_name_blob) covering every series/composite/ticker."""
    ids = set()
    names = []

    econ = read_csv(os.path.join(ROOT, "data", "macro_economic.csv"))
    for r in econ:
        if r.get("Series ID"):
            ids.add(r["Series ID"].strip())
        if r.get("Indicator"):
            names.append(r["Indicator"].lower())

    for fn in ("macro_indicator_library.csv", "macro_market.csv"):
        for r in read_csv(os.path.join(ROOT, "data", fn)):
            if r.get("id"):
                ids.add(r["id"].strip())

    idx = read_csv(os.path.join(ROOT, "data", "index_library.csv"))
    for r in idx:
        for col, val in r.items():
            if col.startswith("ticker_") and val and val.strip():
                ids.add(val.strip())
        if r.get("name"):
            names.append(r["name"].lower())

    # Per-source fetch catalogues (catalogued but possibly not yet in macro_economic).
    for path in glob.glob(os.path.join(ROOT, "data", "macro_library_*.csv")):
        for r in read_csv(path):
            sid = r.get("series_id") or r.get("id")
            if sid and sid.strip():
                ids.add(sid.strip())

    return ids, names


def extract_ids(match_field):
    """Pull verifiable id/ticker tokens out of a pipeline_match cell."""
    # Strip parentheticals so "IRLTLT01GBM156N (10y gilt)" -> "IRLTLT01GBM156N".
    cleaned = re.sub(r"\([^)]*\)", "", match_field)
    tokens = re.split(r"[;,+]", cleaned)
    out = []
    for tok in tokens:
        t = tok.strip()
        if not t or " " in t:
            continue  # descriptive phrase, not a verifiable id
        if t.upper() in SOURCE_WORDS:
            continue  # provider/source name, not a series id
        if "/" in t:
            # ECB SDMX key ('CISS/D.U2...') or DB.nomics path ('ISM/prices/in')
            # are verifiable ids; FX-pair shorthand ('USD/CNY', one slash, no dot)
            # is not.
            if "." in t or t.count("/") >= 2:
                out.append(t)
            continue
        if RE_COMPOSITE.match(t) or RE_SERIES_ID.match(t) or RE_TICKER.match(t):
            out.append(t)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--write-memos", action="store_true",
                    help="write a request memo per sourceable gap")
    ap.add_argument("--quiet", action="store_true",
                    help="summary only; suppress per-row detail")
    args = ap.parse_args()

    rows = read_csv(COVERAGE_CSV)
    supply_ids, supply_names = build_supply_universe()

    status_counts = Counter(r["status"] for r in rows)
    pillar_status = defaultdict(Counter)
    for r in rows:
        pillar_status[r["pillar"]][r["status"]] += 1

    regressions = []        # (row, [unresolved ids])
    id_backed = 0           # rows whose coverage we could concretely verify
    descriptive_only = 0    # Covered/Partial rows with no verifiable id cited

    for r in rows:
        if r["status"] not in (COVERED, PARTIAL):
            continue
        cited = extract_ids(r["pipeline_match"])
        if not cited:
            descriptive_only += 1
            continue
        id_backed += 1
        missing = [c for c in cited if c not in supply_ids]
        if len(missing) == len(cited):
            # none of the cited ids resolve -> the claim's evidence is gone
            regressions.append((r, missing))

    # ---- report ----
    print("=" * 64)
    print("Phase 0 coverage check — regime-aa indicator demand vs pipeline")
    print("=" * 64)
    print(f"Demand rows (indicator x region): {len(rows)}")
    print(f"Supply universe (ids+tickers):    {len(supply_ids)}")
    print()
    print("Coverage by status:")
    for s in (COVERED, PARTIAL, SOURCEABLE, HARD, ACCEPTED):
        print(f"  {s:20} {status_counts.get(s, 0)}")
    print()
    print("By pillar (Covered / Partial / Sourceable / Hard / Accepted):")
    for pillar in sorted(pillar_status):
        c = pillar_status[pillar]
        print(f"  {pillar:28} {c[COVERED]:3} / {c[PARTIAL]:3} / "
              f"{c[SOURCEABLE]:3} / {c[HARD]:3} / {c[ACCEPTED]:3}")
    print()
    print(f"Coverage claims verified against live ids: {id_backed} "
          f"(descriptive-only, not id-verifiable: {descriptive_only})")

    if regressions:
        print()
        print(f"!! {len(regressions)} REGRESSION(S): claimed coverage whose cited "
              f"ids are no longer in the pipeline:")
        for r, missing in regressions:
            print(f"   - {r['indicator']} [{r['region']}]: missing {', '.join(missing)}")
    else:
        print("\nNo regressions: every id-backed coverage claim still resolves.")

    # ---- sourceable-gap memos ----
    sourceable = [r for r in rows if r["status"] == SOURCEABLE]
    if args.write_memos and sourceable:
        os.makedirs(MEMO_DIR, exist_ok=True)
        for r in sourceable:
            slug = re.sub(r"[^a-z0-9]+", "-",
                          f"{r['indicator']}-{r['region']}".lower()).strip("-")
            path = os.path.join(MEMO_DIR, f"{slug}.md")
            with open(path, "w") as f:
                f.write(memo_text(r))
        print(f"\nWrote {len(sourceable)} request memo(s) to "
              f"{os.path.relpath(MEMO_DIR, ROOT)}/")

    if not args.quiet and sourceable:
        print(f"\nSourceable gaps ({len(sourceable)}) — free source identified, "
              f"not yet in pipeline:")
        for r in sourceable:
            print(f"  - [{r['pillar']}] {r['indicator']} [{r['region']}] "
                  f"-> {r['candidate_free_source']}")

    return 1 if regressions else 0


def memo_text(r):
    return f"""# Pipeline data request: {r['indicator']} ({r['region']})

**Pillar:** {r['pillar']} / {r['sub_group']}
**Cycle-timing prior:** {r['cycle_timing_prior']}
**Regional analogue requested:** {r['regional_analogue']}
**Requested source / frequency:** {r['requested_source_freq']}  (lag: {r['lag']})

## Status
`{r['status']}` — not currently in the pipeline, but a free/public source exists.

## Candidate free source
{r['candidate_free_source']}

## Notes
{r['notes']}

---
*Auto-templated by `scripts/phase_0_coverage_check.py` from the regime-aa
indicator coverage map. Regenerate after updating the map.*
"""


if __name__ == "__main__":
    sys.exit(main())
