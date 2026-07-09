"""
scripts/backfill_ind_prod_hist.py
=================================
One-time (idempotent) deep-history seed for two industrial-production
columns whose LIVE winner source starts late, per regime-aa memo
2026-07-08-monthly-growth-inflation-cadence (forward_plan §3.18):

  - JPN_IND_PROD  live = e-Stat METI IIP 2020-base, starts 2018-01 (a source
                  limit of the 2020-base table, not a fetch window).
                  Donor: IMF PI ``JPN.IND.SA_IX.M`` (1953-01 → 2023-11,
                  2010=100 — frozen upstream at 2023-11, which is exactly why
                  it is a donor and NOT a registered library row).
  - FRA_IND_PROD  live = INSEE idbank 010768261, starts 1990-01 (INSEE BDM
                  limit for the 2021-base IPI).
                  Donor: IMF PI ``FRA.IND.SA_IX.M`` (1956-01+, 2010=100 —
                  live and registered as the T1 row; here it only supplies
                  the pre-1990 segment).

Mechanism (forward_plan §3.1.1 Pattern 9): the pre-seam history is written
into the sister archive ``data/macro_economic_hist_x.csv``.  Consumers that
read via ``library_utils.load_hist_with_archive`` see live ∪ sister with
live winning per cell, so the seeded cells surface only before the live
source's start — they can never mask a live value.

Base-splice: donor (2010=100) and live target carry different base years, so
raw concatenation would put a fake level step at the seam and corrupt any
YoY window straddling it.  Each donor series is therefore rescaled by the
mean(target/donor) ratio over an early overlap window (the same treatment a
statistical office applies when publishing linked/"接続" indices).  The
ratio's stability over the window is printed as a sanity check — a drifting
ratio would mean the two series do not track the same underlying index.

The donor series_ids live here (not in a macro_library_*.csv) deliberately:
they must NOT participate in the live fetch/winner merge.  Both are recorded
in data/source_fallbacks.csv so the provenance is discoverable.

Run from the repo root:  python3 scripts/backfill_ind_prod_hist.py
"""

from __future__ import annotations

import csv
import io
import os
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from library_utils import sniff_hist_prefix_rows          # noqa: E402
from sources import imf_sdmx as imf_src                    # noqa: E402
from sources import insee as insee_src                     # noqa: E402

LIVE_CSV   = "data/macro_economic_hist.csv"
SISTER_CSV = "data/macro_economic_hist_x.csv"

JPN_DONOR = "IMF.STA,PI/JPN.IND.SA_IX.M"    # frozen 2023-11 — donor only
FRA_DONOR = "IMF.STA,PI/FRA.IND.SA_IX.M"    # live T1 row; donor for pre-1990
FRA_TARGET_INSEE = "SERIES_BDM/010768261"   # the registered tier-0 live row


def _load_hist(path: str) -> tuple[list[list[str]], pd.DataFrame]:
    """Read a hist CSV → (prefix rows, Date-indexed DataFrame)."""
    n_prefix = sniff_hist_prefix_rows(path)
    if n_prefix is None:
        raise SystemExit(f"cannot find header row in {path}")
    with open(path, newline="", encoding="utf-8") as fh:
        prefix = [row for _, row in zip(range(n_prefix), csv.reader(fh))]
    df = pd.read_csv(path, skiprows=n_prefix, low_memory=False)
    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
    df = df[df["Date"].notna()].set_index("Date").sort_index()
    return prefix, df


def _monthly_from_spine(spine: pd.Series) -> pd.Series:
    """Recover the monthly observation series from a Friday-spine column.

    Sources date month m at m-01 and the spine forward-fills, so the value at
    the FIRST Friday >= m-01 is month m's observation."""
    out = {}
    for month_start in pd.date_range(spine.index.min(), spine.index.max(), freq="MS"):
        fridays = spine.index[spine.index >= month_start]
        if len(fridays) == 0:
            continue
        v = spine.get(fridays[0])
        if pd.notna(v):
            out[month_start] = float(v)
    return pd.Series(out).sort_index()


def _splice_ratio(target_m: pd.Series, donor_m: pd.Series,
                  window: slice, label: str) -> float:
    """Mean target/donor ratio over the overlap window, with a drift check."""
    t = target_m.loc[window]
    d = donor_m.reindex(t.index).dropna()
    t = t.reindex(d.index)
    if len(d) < 12:
        raise SystemExit(f"{label}: overlap window too short ({len(d)} months)")
    ratios = t / d
    ratio = float(ratios.mean())
    drift = float(ratios.std() / ratio)
    print(f"  [{label}] splice ratio {ratio:.5f} over {len(d)} months "
          f"({d.index.min():%Y-%m} → {d.index.max():%Y-%m}); rel. std {drift:.3%}")
    if drift > 0.02:
        raise SystemExit(f"{label}: ratio drift {drift:.2%} > 2% — donor and "
                         f"target do not track the same index; aborting")
    return ratio


def _monthly_to_fridays(monthly: pd.Series, fridays: pd.DatetimeIndex) -> pd.Series:
    """Snap a month-start-dated series onto Friday cells (ffill, capped 45d —
    donor months are contiguous so the cap only trims the tail)."""
    filled = monthly.reindex(fridays.union(monthly.index)).sort_index().ffill()
    obs_dates = pd.Series(monthly.index, index=monthly.index) \
        .reindex(fridays.union(monthly.index)).sort_index().ffill()
    filled = filled.reindex(fridays)
    obs_dates = obs_dates.reindex(fridays)
    age_ok = (fridays - pd.DatetimeIndex(obs_dates)).days <= 45
    return filled.where(pd.Series(age_ok, index=fridays))


def main() -> None:
    print("== backfill_ind_prod_hist ==")
    live_prefix, live = _load_hist(LIVE_CSV)
    sister_prefix, sister = _load_hist(SISTER_CSV)

    # ------------------------------------------------------------------ JPN
    print("\nJPN_IND_PROD — donor IMF PI (2010=100) → e-Stat 2020 base")
    donor_jpn = imf_src.fetch_series_as_pandas(JPN_DONOR, start="1947-01-01")
    if donor_jpn is None or donor_jpn.empty:
        raise SystemExit("IMF PI JPN donor fetch failed")
    print(f"  donor: {donor_jpn.index.min():%Y-%m} → {donor_jpn.index.max():%Y-%m} "
          f"n={len(donor_jpn)}")
    live_jpn_m = _monthly_from_spine(live["JPN_IND_PROD"].dropna())
    seam_jpn = live["JPN_IND_PROD"].dropna().index.min()
    print(f"  live starts {seam_jpn:%Y-%m-%d} (first spine cell of the e-Stat series)")
    # Pre-COVID overlap: 2018-01 → 2019-12 (donor is final-vintage throughout).
    ratio_jpn = _splice_ratio(live_jpn_m, donor_jpn,
                              slice("2018-01-01", "2019-12-31"), "JPN")
    rebased_jpn = donor_jpn.loc[:"2017-12-31"] * ratio_jpn
    pre_fridays = sister.index[sister.index < seam_jpn]
    seeded_jpn = _monthly_to_fridays(rebased_jpn, pre_fridays)
    n_before = sister.loc[sister.index < seam_jpn, "JPN_IND_PROD"].notna().sum()
    sister.loc[pre_fridays, "JPN_IND_PROD"] = seeded_jpn
    n_after = sister.loc[sister.index < seam_jpn, "JPN_IND_PROD"].notna().sum()
    print(f"  sister pre-seam cells: {n_before} (old FRED 2015-base) → {n_after} "
          f"(rebased IMF, {seeded_jpn.dropna().index.min():%Y-%m-%d} → seam)")
    # Seam continuity check: last seeded vs first live value.
    last_seed = seeded_jpn.dropna().iloc[-1]
    first_live = live["JPN_IND_PROD"].dropna().iloc[0]
    print(f"  seam check: last seeded {last_seed:.2f} vs first live {first_live:.2f} "
          f"({(first_live / last_seed - 1) * 100:+.2f}% step)")

    # ------------------------------------------------------------------ FRA
    print("\nFRA_IND_PROD — donor IMF PI (2010=100) → INSEE 2021 base")
    donor_fra = imf_src.fetch_series_as_pandas(FRA_DONOR, start="1947-01-01")
    target_fra = insee_src.fetch_series_as_pandas(FRA_TARGET_INSEE)
    if donor_fra is None or donor_fra.empty or target_fra is None or target_fra.empty:
        raise SystemExit("FRA donor/target fetch failed")
    print(f"  donor: {donor_fra.index.min():%Y-%m} → {donor_fra.index.max():%Y-%m} "
          f"n={len(donor_fra)}")
    print(f"  target (INSEE): {target_fra.index.min():%Y-%m} → "
          f"{target_fra.index.max():%Y-%m} n={len(target_fra)}")
    ratio_fra = _splice_ratio(target_fra, donor_fra,
                              slice("1990-01-01", "1992-12-31"), "FRA")
    seam_fra = target_fra.index.min()          # 1990-01-01
    rebased_fra = donor_fra.loc[: seam_fra - pd.Timedelta(days=1)] * ratio_fra
    pre_fridays = sister.index[sister.index < seam_fra]
    if "FRA_IND_PROD" not in sister.columns:
        sister["FRA_IND_PROD"] = float("nan")
    seeded_fra = _monthly_to_fridays(rebased_fra, pre_fridays)
    sister.loc[pre_fridays, "FRA_IND_PROD"] = seeded_fra
    print(f"  seeded {seeded_fra.notna().sum()} sister cells "
          f"({seeded_fra.dropna().index.min():%Y-%m-%d} → seam {seam_fra:%Y-%m-%d})")
    last_seed = seeded_fra.dropna().iloc[-1]
    first_live = float(target_fra.iloc[0])
    print(f"  seam check: last seeded {last_seed:.2f} vs first INSEE {first_live:.2f} "
          f"({(first_live / last_seed - 1) * 100:+.2f}% step)")

    # ------------------------------------------------- extend sister metadata
    # The sister prefix has one cell per column; FRA_IND_PROD is new. The next
    # daily write replaces this prefix wholesale with the live generation, so
    # this only needs to be sane in the interim.
    header_labels = [row[0] for row in sister_prefix]
    fra_meta = {
        "Column ID": "FRA_IND_PROD", "Series ID": FRA_DONOR, "Source": "IMF SDMX",
        "Indicator": "France Industrial Production (pre-1990 backfill, rebased to INSEE 2021 base)",
        "Country": "FRA", "Country Name": "France", "Region": "Europe",
        "Category": "Growth", "Subcategory": "Real Activity", "Concept": "Growth",
        "cycle_timing": "C", "Units": "Index 2021=100 (SA, rebased)",
        "Frequency": "Monthly", "Last Updated": "", "Last Observation": "",
    }
    n_cols_before = len(sister.columns)
    for row, label in zip(sister_prefix, header_labels):
        # pad first (older prefixes can be ragged), then append the new cell
        while len(row) < n_cols_before:          # label cell + (n-1) data cells
            row.append("")
        row.append(fra_meta.get(label, ""))

    # ------------------------------------------------------------- write out
    out = sister.reset_index()
    out["Date"] = out["Date"].dt.strftime("%Y-%m-%d")
    buf = io.StringIO()
    csv.writer(buf, lineterminator="\n").writerows(sister_prefix)
    with open(SISTER_CSV, "w", encoding="utf-8") as fh:
        fh.write(buf.getvalue())
        out.to_csv(fh, index=False)
    print(f"\nWritten {len(out)} rows x {len(sister.columns)} cols to {SISTER_CSV}")


if __name__ == "__main__":
    main()
