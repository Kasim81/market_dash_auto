#!/usr/bin/env python3
"""
Build the regime-aa sourcing backlog from the coverage map.

Reads the Missing-Sourceable rows of `regime-aa-indicator-coverage.csv` and joins
a curated implementation plan for each (bucket, exact identifier, target file,
effort, and how confidently the candidate id was validated). Emits
`regime-aa-sourcing-backlog.md`.

Buckets (ascending effort):
  A  FRED single-series add   one row in data/macro_library_fred.csv
  B  Wire existing market data ticker already in index_library; build composite
  C  New / non-FRED endpoint  fetch logic in an existing sources/*.py + catalogue
  D  Derived-only             calculator in compute_macro_market.py + library row,
                              no new fetch (the US_INFL1 pattern)

Validation confidence (from scripts spot-check, FRED graph endpoint blocked in
the build sandbox; api needs a runtime key):
  CONFIRMED  id already fetched by the pipeline, or exact OECD/FRED template with
             multi-country precedent
  VERIFY     research-derived id; confirm on first fetch (pipeline has the key)
  SOURCE-OK  free source definitely exists; exact series path to be pinned down
"""
import csv
import os
from collections import defaultdict

OUT_DIR = os.path.dirname(os.path.abspath(__file__))
COVERAGE_CSV = os.path.join(OUT_DIR, "regime-aa-indicator-coverage.csv")

# Curated implementation plan, keyed by (indicator, region).
# value: (bucket, identifier, target_file, effort, confidence, note)
IMPL = {
    ("Yield Curve (10y minus 2y)", "China"):
        ("A", "IRLTLT01CNM156N (10y leg only)", "data/macro_library_fred.csv", "S", "CONFIRMED",
         "Monthly 10y via exact OECD MEI template (10-country precedent). 2y CGB leg still unresolved — slope stays monthly-only."),
    ("M2 Money Supply (YoY%)", "Eurozone"):
        ("A", "MABMM301EZM189S", "data/macro_library_fred.csv", "S", "VERIFY",
         "ECB M3 via FRED; alternative is ECB BSI direct."),
    ("M2 Money Supply (YoY%)", "Japan"):
        ("A", "MYAGM2JPM189S", "data/macro_library_fred.csv", "S", "VERIFY",
         "Confirm N vs S suffix (pipeline already has MYAGM2CNM189N for China)."),
    ("M2 Money Supply (YoY%)", "UK"):
        ("C", "BoE M4 (IADB LPMVWYH)", "sources/boe.py + data/macro_library_boe.csv", "M", "SOURCE-OK",
         "BoE M4; new series in the existing BoE fetcher."),
    ("NAHB Housing Market Index", "US"):
        ("A", "NAHBSHF", "data/macro_library_fred.csv", "S", "VERIFY",
         "NAHB/Wells Fargo HMI; research says free on FRED."),
    ("Trimmed Mean / Median CPI", "US"):
        ("A", "MEDCPIM158SFRBCLE + TRMMEANCPIM158SFRBCLE (+ PCETRIM12M159SFRBDAL)",
         "data/macro_library_fred.csv", "S", "VERIFY",
         "Cleveland median/trimmed CPI; Dallas trimmed PCE optional."),
    ("University of Michigan Inflation Expectations (5-10y)", "US"):
        ("A", "MICH5YR", "data/macro_library_fred.csv", "S", "VERIFY",
         "Long-run UMich expectations; pipeline already has 1y MICH. Spot-check id."),
    ("IG Credit Spreads (OAS)", "Eurozone"):
        ("A", "BAMLER00ICOAS", "data/macro_library_fred.csv", "S", "VERIFY",
         "ICE BofA Euro Corp OAS; ICE family already widely fetched (e.g. BAMLEMRACRPIASIAOAS confirmed present)."),

    ("ISM / PMI Prices Paid", "US"):
        ("C", "DB.nomics ISM/prices", "sources/dbnomics.py + data/macro_library_dbnomics.csv", "S", "SOURCE-OK",
         "Same DB.nomics path as the ISM PMI / New Orders already fetched. ISM data is licensed — verify."),
    ("Building Permits (SAAR)", "Eurozone"):
        ("C", "Eurostat sts_cobp_m", "sources/dbnomics.py + data/macro_library_dbnomics.csv", "M", "SOURCE-OK",
         "Eurostat building-permits index via DB.nomics."),
    ("PPI Final Demand (YoY%)", "Eurozone"):
        ("C", "Eurostat sts_inpp_m", "sources/dbnomics.py + data/macro_library_dbnomics.csv", "M", "SOURCE-OK",
         "Eurostat PPI via DB.nomics."),
    ("Building Permits (SAAR)", "UK"):
        ("C", "MHCLG dwelling starts", "new MHCLG source + data/macro_library_*.csv", "L", "SOURCE-OK",
         "NOT on the ONS timeseries (Zebedee) API; published by MHCLG. Needs a new source module or CMD path."),
    ("PPI Final Demand (YoY%)", "UK"):
        ("C", "ONS PPI output/input", "sources/ons.py + data/macro_library_ons.csv", "M", "SOURCE-OK",
         "ONS producer prices."),
    ("Initial Jobless Claims", "UK"):
        ("C", "ONS Claimant Count", "sources/ons.py + data/macro_library_ons.csv", "S", "SOURCE-OK",
         "Monthly (not weekly); ONS labour-market series."),
    ("Nonfarm Payrolls (MoM change)", "UK"):
        ("C", "ONS PAYE RTI (CMD API)", "ONS CMD-datasets fetch path", "L", "SOURCE-OK",
         "PAYE RTI payrolls are in the newer ONS CMD datasets API, not the classic timeseries the fetcher uses. Needs a CMD path, or use LFS employment level as a proxy."),
    ("Senior Loan Officer Survey (SLOOS)", "Eurozone"):
        ("C", "ECB BLS (key pending)", "sources/ecb.py + data/macro_library_ecb.csv", "M", "SOURCE-OK",
         "ECB dataflow BLS confirmed reachable. Net-% series = BLS_ITEM APP + agg WFNET (B6 backward / F6 forward); pin the canonical 'net % tightening, enterprises, 3m' key before adding."),
    ("Senior Loan Officer Survey (SLOOS)", "UK"):
        ("C", "BoE Credit Conditions Survey", "sources/boe.py + data/macro_library_boe.csv", "L", "SOURCE-OK",
         "Published as spreadsheet — extraction is the work, not access."),
    ("Chicago Fed NFCI", "Eurozone"):
        ("C", "ECB CISS", "sources/ecb.py + data/macro_library_ecb.csv", "M", "CONFIRMED",
         "Systemic-stress composite; free via ECB. Reused by GS-FCI and Bloomberg-FCI EZ rows below."),
    ("Goldman Sachs FCI (US)", "Eurozone"):
        ("C", "ECB CISS (shared with NFCI row)", "sources/ecb.py + data/macro_library_ecb.csv", "M", "CONFIRMED",
         "Same ECB CISS series — one fetch satisfies all three EZ financial-conditions rows."),
    ("Bloomberg US FCI", "Eurozone"):
        ("C", "ECB CISS (shared with NFCI row)", "sources/ecb.py + data/macro_library_ecb.csv", "M", "CONFIRMED",
         "Same ECB CISS series."),
    ("5y5y Forward Inflation Swap", "Eurozone"):
        ("C", "ECB Data Portal inflation-linked-swap 5y5y", "sources/ecb.py + data/macro_library_ecb.csv", "M", "SOURCE-OK",
         "EZ 5y5y free via ECB; UK/JP remain proprietary (Hard)."),
    ("University of Michigan Inflation Expectations (5-10y)", "UK"):
        ("C", "BoE/Ipsos Inflation Attitudes Survey", "sources/boe.py + data/macro_library_boe.csv", "M", "SOURCE-OK",
         "Quarterly long-run consumer inflation expectations."),
    ("University of Michigan Inflation Expectations (5-10y)", "Eurozone"):
        ("C", "ECB Survey of Consumer Expectations", "sources/ecb.py + data/macro_library_ecb.csv", "M", "SOURCE-OK",
         "ECB SCE."),
    ("TIPS 5-year Breakeven Rate", "Eurozone"):
        ("C", "ECB / Eurostat HICP-linked yields", "sources/ecb.py + data/macro_library_ecb.csv", "L", "SOURCE-OK",
         "Limited free coverage; lower-priority."),

    ("Taylor Rule Gap", "US"):
        ("D", "FFR, Core PCE, output gap (all in pipeline)", "compute_macro_market.py + data/macro_indicator_library.csv", "M", "CONFIRMED",
         "Pure calculator; no fetch. Highest-confidence derived item."),
    ("Taylor Rule Gap", "UK"):
        ("D", "Bank Rate, CPI, output gap", "compute_macro_market.py + data/macro_indicator_library.csv", "M", "SOURCE-OK",
         "Derived; output-gap input weaker than US."),
    ("Taylor Rule Gap", "Eurozone"):
        ("D", "ECB rate, HICP, output gap", "compute_macro_market.py + data/macro_indicator_library.csv", "M", "SOURCE-OK",
         "Derived."),
    ("Taylor Rule Gap", "Japan"):
        ("D", "BoJ rate, Core CPI, output gap", "compute_macro_market.py + data/macro_indicator_library.csv", "M", "SOURCE-OK",
         "Derived."),
    ("Taylor Rule Gap", "China"):
        ("D", "PBoC rate, CPI, output gap", "compute_macro_market.py + data/macro_indicator_library.csv", "M", "SOURCE-OK",
         "Derived; China output-gap estimate weak."),
    ("Global Monetary Policy Tracker", "Global"):
        ("D", "BIS central-bank policy-rate panel", "compute_macro_market.py + data/macro_indicator_library.csv", "L", "SOURCE-OK",
         "Net hikers-minus-cutters diffusion from the free BIS policy-rate panel."),
}

# High-value items not flagged Sourceable but worth carrying in the backlog.
EXTRA = [
    {"indicator": "ISM New Orders minus Inventories", "region": "US",
     "pillar": "Growth", "candidate_free_source": "Both legs now catalogued",
     "status": "Partial", "_impl":
        ("D", "ISM/neword/in - ISM/inventories/in", "compute_macro_market.py + data/macro_indicator_library.csv", "S", "CONFIRMED",
         "Both legs now in the pipeline (Inventories added Bucket C). Remaining work is the spread calculator + a library row.")},
]

BUCKET_TITLES = {
    "A": "Bucket A — FRED single-series add (lowest effort)",
    "B": "Bucket B — wire existing market data into a composite",
    "C": "Bucket C — new / non-FRED endpoint",
    "D": "Bucket D — derived-only (calculator, no new fetch)",
}
EFFORT_ORDER = {"S": 0, "M": 1, "L": 2}


def main():
    rows = list(csv.DictReader(open(COVERAGE_CSV)))
    items = [r for r in rows if r["status"] == "Missing-Sourceable"]

    grouped = defaultdict(list)
    unmatched = []
    for r in items:
        key = (r["indicator"], r["region"])
        if key not in IMPL:
            unmatched.append(key)
            continue
        bucket = IMPL[key][0]
        grouped[bucket].append((r, IMPL[key]))
    for e in EXTRA:
        grouped[e["_impl"][0]].append((e, e["_impl"]))

    lines = []
    lines.append("# Regime-AA Sourcing Backlog")
    lines.append("")
    lines.append("Actionable plan for the **Missing-Sourceable** rows of "
                 "`regime-aa-indicator-coverage.md` — indicators a free/public "
                 "source can supply but the pipeline does not yet carry. Generated "
                 "by `build_sourcing_backlog.py`; regenerate after updating the map.")
    lines.append("")
    lines.append("**Validation confidence** (FRED's keyless graph endpoint is "
                 "blocked in the build sandbox and the API needs a runtime key, so "
                 "candidate ids were validated structurally):")
    lines.append("")
    lines.append("- `CONFIRMED` — id already fetched by the pipeline, or an exact "
                 "OECD/FRED template with multi-country precedent")
    lines.append("- `VERIFY` — research-derived id; confirm on first fetch (the "
                 "fetcher has the FRED key)")
    lines.append("- `SOURCE-OK` — free source definitely exists; exact series path "
                 "to be pinned down during implementation")
    lines.append("")
    total = sum(len(v) for v in grouped.values())
    lines.append(f"**{total} backlog items** across {len([b for b in grouped if grouped[b]])} buckets.")
    lines.append("")

    for bucket in ("A", "B", "C", "D"):
        if not grouped.get(bucket):
            continue
        lines.append(f"## {BUCKET_TITLES[bucket]}")
        lines.append("")
        lines.append("| Indicator | Region | Pillar | Identifier / source | Target file | Effort | Confidence | Note |")
        lines.append("|---|---|---|---|---|---|---|---|")
        for r, impl in sorted(grouped[bucket], key=lambda x: EFFORT_ORDER.get(x[1][3], 9)):
            _, ident, target, effort, conf, note = impl
            ind = r["indicator"].replace("|", "\\|")
            lines.append(f"| {ind} | {r['region']} | {r['pillar']} | "
                         f"`{ident}` | `{target}` | {effort} | {conf} | {note} |")
        lines.append("")

    if unmatched:
        lines.append("## Unmapped sourceable rows (need triage)")
        lines.append("")
        for ind, reg in unmatched:
            lines.append(f"- {ind} [{reg}]")
        lines.append("")

    lines.append("## Suggested sequencing")
    lines.append("")
    lines.append("1. **Bucket A** in one pass — eight single-id FRED adds; biggest "
                 "coverage gain per line of code. Mark each `VERIFY` id confirmed "
                 "once the fetcher runs.")
    lines.append("2. **Bucket C ECB cluster** — one ECB CISS fetch closes three "
                 "Eurozone financial-conditions rows (NFCI, GS-FCI, Bloomberg-FCI "
                 "proxies); ECB BLS + SCE + 5y5y reuse the same fetcher.")
    lines.append("3. **Bucket C ONS cluster** — claimant count, PAYE payrolls, "
                 "permits, PPI: the UK Growth column is the spec's single largest "
                 "regional gap (§5.8).")
    lines.append("4. **Bucket D** — Taylor-rule gaps and the global policy tracker "
                 "are pure calculators on series already present.")
    lines.append("")
    lines.append("Run `python3 scripts/phase_0_coverage_check.py --write-memos` to "
                 "emit a per-gap cross-repo request memo under `requests/`.")
    lines.append("")

    out = os.path.join(OUT_DIR, "regime-aa-sourcing-backlog.md")
    with open(out, "w") as f:
        f.write("\n".join(lines) + "\n")
    print(f"Wrote {total} backlog items to {os.path.relpath(out, os.path.dirname(OUT_DIR))}")
    if unmatched:
        print(f"WARNING: {len(unmatched)} sourceable rows unmapped: {unmatched}")


if __name__ == "__main__":
    main()
