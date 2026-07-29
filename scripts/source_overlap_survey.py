"""Source-overlap survey — Phase 0 diagnostic for the splice/segment work.

For every column with more than one registered source, fetch each candidate
through the coordinator's own history dispatcher and classify the pair:

  SAME_SERIES      values agree within tolerance -> one series relayed twice;
                   a coverage difference is a genuine splice candidate
  SAME_REBASED     index candidates whose ratio is constant -> pure rebasing,
                   spliceable after rescaling to the owner's base
  DIFFERENT        values disagree -> genuinely two series ("record both")
  CADENCE_DIFF     cross-cadence pair; reported under BOTH aggregation
                   conventions so the operator can see which one matches
  DISJOINT         no overlapping periods -> cannot validate a join
  THIN_OVERLAP     overlap too short to be evidence
  KIND_MISMATCH    index vs rate vs level -> never spliceable
  UNFETCHABLE      a candidate errored (usually a missing credential)

Two hard-won details, both of which silently corrupt the comparison if missed:

1. **Period normalisation.** Sources disagree on stamping convention — OECD
   stamps month-END (1955-01-31), BLS month-START (2024-01-01). Comparing raw
   timestamps finds ZERO overlap between them and reports a false DISJOINT.
   Everything is converted to pandas Periods before any comparison.

2. **Aggregation convention.** Coarsening a monthly series to annual by taking
   December and comparing it against an annual *average* produces differences
   of several pp between series that are in fact identical. Cross-cadence pairs
   therefore report both `end` and `mean` aggregations rather than picking one.

Run on a GitHub runner (see .github/workflows/source_survey.yml) so the
credentialed sources — FRED, BLS, e-Stat, BdF — are actually reachable.
Writes `source_overlap_survey.md`. Read-only: touches no data/ file.
"""
from __future__ import annotations

import collections
import os
import sys
import warnings

warnings.filterwarnings("ignore")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
import pandas as pd

os.environ.setdefault("SHEET_ID", "x")
os.environ.setdefault("GOOGLE_CREDENTIALS_JSON", "{}")

import fetch_macro_economic as F  # noqa: E402

OUT = "source_overlap_survey.md"
FAN = {"World Bank", "IMF", "OECD"}
CAD_ORDER = {"daily": 0, "business daily": 0, "weekly": 1,
             "monthly": 2, "quarterly": 3, "annual": 4, "annually": 4}
# minimum overlapping real observations for agreement to count as evidence
MIN_OVERLAP = {0: 60, 1: 40, 2: 24, 3: 8, 4: 3}
PERIOD = {0: "D", 1: "W", 2: "M", 3: "Q", 4: "Y"}
TOL_RATE = 0.15      # percentage points
TOL_LEVEL = 0.005    # relative
TOL_RATIO_DRIFT = 0.002


def cad_rank(freq: str) -> int:
    return CAD_ORDER.get((freq or "").strip().lower(), 5)


def measure_kind(units: str) -> str:
    u = (units or "").lower()
    if any(k in u for k in ("%", "percent", "change", "yoy",
                            "year-on-year", "growth")):
        return "rate"
    if "index" in u:
        return "index"
    return "level"


def to_period(s: pd.Series, rank: int) -> pd.Series:
    """Normalise a series' index to observation periods (detail 1 above)."""
    s = s.sort_index()
    s.index = pd.to_datetime(s.index).to_period(PERIOD.get(rank, "M"))
    return s[~s.index.duplicated(keep="last")]


def coarsen(s: pd.Series, target: str, how: str) -> pd.Series:
    """Re-express a series on a coarser period basis under a named convention."""
    g = s.groupby(s.index.asfreq(target, how="end"))
    return g.last() if how == "end" else g.mean()


def _data(name: str) -> str:
    return os.path.join(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__))), "data", name)


def _fanout_restrictions() -> dict:
    """`series_id -> [ISO, ...]` country restrictions, read from the LIBRARY CSVs.

    Must come from the CSV, not the indicator dict: source modules build their
    indicator dicts key-by-key and none of them carries the fan-out country
    list (the OECD dict exposes only `country: ''`). Reading it from the dict
    silently yields "no restriction", which then expands to EVERY country and
    invents contested columns that do not exist — it fabricated
    `CHE_GOVT_10Y` (OECD `GOVT_10Y` is India-only) and kept
    `FRA_UNEMPLOYMENT` looking contested after France was split out into its
    own `UNEMPLOYMENT_OECD` series. That over-count inflated the headline
    "contested columns" figure from 26 to 36.
    """
    import csv as _csv
    out: dict = {}
    for fn, key in (("macro_library_oecd.csv", "oecd_countries"),
                    ("macro_library_worldbank.csv", "countries"),
                    ("macro_library_imf.csv", "countries")):
        try:
            with open(_data(fn), newline="", encoding="utf-8") as fh:
                for row in _csv.DictReader(fh):
                    sid = (row.get("series_id") or "").strip()
                    raw = (row.get(key) or "").replace("+", "|")
                    isos = [x.strip() for x in raw.split("|") if x.strip()]
                    if sid and isos:
                        out[sid] = isos
        except FileNotFoundError:
            continue
    return out


def contested_columns(inds: list[dict]) -> set[str]:
    """Columns with >1 source, expanding fan-out rows to <ISO>_<col>."""
    import csv as _csv
    with open(_data("macro_library_countries.csv"), newline="", encoding="utf-8") as fh:
        isos = [(r.get("canonical") or r.get("code") or
                 list(r.values())[0] or "").strip()
                for r in _csv.DictReader(fh)]
    isos = [i for i in isos if i]
    restrict = _fanout_restrictions()
    cols: dict[str, set] = collections.defaultdict(set)
    for i in inds:
        c = i.get("col")
        if not c:
            continue
        if i.get("source") in FAN and not any(c.startswith(x + "_") for x in isos):
            sid = i.get("source_id") or i.get("series_id") or ""
            targets = restrict.get(sid, isos)
            for iso in targets:
                cols[f"{iso}_{c}"].add(i.get("source"))
        else:
            cols[c].add(i.get("source"))
    return {c for c, v in cols.items() if len(v) > 1}


def compare(A: dict, B: dict, a: pd.Series, b: pd.Series) -> dict:
    """Classify one candidate pair. A is the higher-priority candidate."""
    ka, kb = measure_kind(A["units"]), measure_kind(B["units"])
    ra, rb = cad_rank(A["freq"]), cad_rank(B["freq"])
    res = {
        "A": f"{A['source']} t{A['tier']} {A['freq']}",
        "B": f"{B['source']} t{B['tier']} {B['freq']}",
        "A_span": f"{a.index.min()}→{a.index.max()}",
        "B_span": f"{b.index.min()}→{b.index.max()}",
        "A_n": len(a), "B_n": len(b),
    }
    if ka != kb:
        res.update(verdict="KIND_MISMATCH", detail=f"{ka} vs {kb} — never spliceable")
        return res

    coarse_rank = max(ra, rb)
    target = PERIOD.get(coarse_rank, "M")
    cross = ra != rb

    def assess(how: str) -> tuple[str, str, int]:
        x = coarsen(a, target, how) if ra != coarse_rank else a.copy()
        y = coarsen(b, target, how) if rb != coarse_rank else b.copy()
        x.index = x.index.asfreq(target, how="end")
        y.index = y.index.asfreq(target, how="end")
        ov = x.index.intersection(y.index)
        need = MIN_OVERLAP.get(coarse_rank, 24)
        if len(ov) == 0:
            return "DISJOINT", "no overlapping periods — cannot validate", 0
        if len(ov) < need:
            return "THIN_OVERLAP", f"{len(ov)} periods < {need} required", len(ov)
        xs, ys = x[ov].astype(float), y[ov].astype(float)
        if ka == "index":
            ratio = (ys / xs).replace([np.inf, -np.inf], np.nan).dropna()
            if ratio.empty or ratio.min() <= 0:
                return "DIFFERENT", "ratio undefined", len(ov)
            drift = ratio.max() / ratio.min() - 1
            v = "SAME_REBASED" if drift <= TOL_RATIO_DRIFT else "DIFFERENT"
            return v, f"ratio drift={drift:.4f}, median r={ratio.median():.4f}", len(ov)
        if ka == "rate":
            d = (xs - ys).abs()
            v = "SAME_SERIES" if d.max() <= TOL_RATE else "DIFFERENT"
            return v, f"max|diff|={d.max():.4f} mean={d.mean():.4f}", len(ov)
        rel = (xs / ys - 1).abs().replace([np.inf, -np.inf], np.nan).dropna()
        v = "SAME_SERIES" if (not rel.empty and rel.max() <= TOL_LEVEL) else "DIFFERENT"
        return v, f"max|rel|={(rel.max() if not rel.empty else float('nan')):.5f}", len(ov)

    if not cross:
        v, d, n = assess("end")
        res.update(verdict=v, detail=d, overlap=n)
    else:
        # detail 2: report BOTH conventions so the right one is discoverable
        ve, de, n = assess("end")
        vm, dm, _ = assess("mean")
        best = ve if ve.startswith("SAME") else (vm if vm.startswith("SAME") else ve)
        res.update(verdict=("CADENCE_DIFF" if not best.startswith("SAME") else best),
                   detail=f"end-of-period: {ve} ({de}) | mean: {vm} ({dm})",
                   overlap=n)
    # Compare coverage on timestamps: a and b may sit on different Period
    # freqs (Y vs Q), and Period comparison across freqs raises.
    a_lo, a_hi = a.index.min().to_timestamp(), a.index.max().to_timestamp(how="end")
    b_lo, b_hi = b.index.min().to_timestamp(), b.index.max().to_timestamp(how="end")
    gain = ("head " if b_lo < a_lo else "") + ("tail" if b_hi > a_hi else "")
    res["gain"] = gain.strip() or "none"
    return res


def main() -> int:
    inds = F.load_all_indicators()
    ifo: list = []
    if isinstance(inds, tuple):
        inds, ifo = inds[0], (inds[1] if len(inds) > 1 else [])
    contested = contested_columns(inds)
    targets = [i for i in inds if i.get("source") in FAN or i.get("col") in contested]
    print(f"[survey] {len(contested)} contested columns, {len(targets)} indicators to fetch",
          flush=True)

    got: dict[str, list] = collections.defaultdict(list)
    errors: list[str] = []
    nodata: list[str] = []
    for n, ind in enumerate(targets, 1):
        src = ind.get("source")
        sid = ind.get("source_id") or ind.get("series_id")
        try:
            sd = F._history_for_indicator(ind, ifo) or {}
            kept = 0
            for col, s in sd.items():
                if s is None:
                    continue
                s = s.dropna()
                if s.empty:
                    continue
                got[col].append({"source": src, "sid": str(sid),
                                 "freq": ind.get("frequency"),
                                 "units": ind.get("units"),
                                 "tier": ind.get("tier"), "s": s})
                kept += 1
            if kept == 0:
                # A source that fails internally (e.g. FRED HTTP 400 on a bad
                # key) returns an empty dict rather than raising, so counting
                # only exceptions would report "0 errors" while silently
                # leaving those candidates unsurveyed.
                nodata.append(f"{src}/{sid}")
                print(f"  [{n}/{len(targets)}] NODATA {src}/{str(sid)[:40]}", flush=True)
            else:
                print(f"  [{n}/{len(targets)}] OK   {src}/{str(sid)[:40]}", flush=True)
        except Exception as exc:  # noqa: BLE001 — diagnostic must not abort
            errors.append(f"{src}/{sid}: {type(exc).__name__}: {exc}"[:160])
            print(f"  [{n}/{len(targets)}] FAIL {src}/{str(sid)[:40]}: "
                  f"{type(exc).__name__}", flush=True)

    rows = []
    for col in sorted(got):
        cands = got[col]
        if len(cands) < 2:
            continue
        for c in cands:
            c["s"] = to_period(c["s"], cad_rank(c["freq"]))
        cands.sort(key=lambda c: (int(c.get("tier") or 9), cad_rank(c.get("freq"))))
        r = compare(cands[0], cands[1], cands[0]["s"], cands[1]["s"])
        r["col"] = col
        r["n_cands"] = len(cands)
        rows.append(r)

    by_verdict = collections.Counter(r["verdict"] for r in rows)
    with open(OUT, "w", encoding="utf-8") as fh:
        fh.write("# Source-overlap survey\n\n")
        fh.write(f"Contested columns: **{len(contested)}**; "
                 f"pairs classified: **{len(rows)}**; "
                 f"fetch errors: **{len(errors)}**; "
                 f"candidates returning no data: **{len(nodata)}**\n\n")
        fh.write("| verdict | n |\n|---|---|\n")
        for v, n in by_verdict.most_common():
            fh.write(f"| {v} | {n} |\n")
        fh.write("\n## Detail\n\n")
        fh.write("| column | verdict | A (priority) | A span | B | B span | ovl | B adds | detail |\n")
        fh.write("|---|---|---|---|---|---|---|---|---|\n")
        for r in sorted(rows, key=lambda r: (r["verdict"], r["col"])):
            fh.write(f"| `{r['col']}` | {r['verdict']} | {r['A']} | {r['A_span']} "
                     f"| {r['B']} | {r['B_span']} | {r.get('overlap','')} "
                     f"| {r.get('gain','')} | {r.get('detail','')} |\n")
        if errors:
            fh.write("\n## Fetch errors (unsurveyed candidates)\n\n")
            for e in errors:
                fh.write(f"- `{e}`\n")
        if nodata:
            fh.write("\n## Returned no data — unsurveyed, usually a missing credential\n\n")
            for e in sorted(nodata):
                fh.write(f"- `{e}`\n")
    print(f"[survey] wrote {OUT}: {dict(by_verdict)}; "
          f"{len(errors)} errors, {len(nodata)} no-data", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
