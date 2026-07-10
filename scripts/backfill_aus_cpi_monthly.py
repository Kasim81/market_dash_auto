"""
scripts/backfill_aus_cpi_monthly.py
===================================
One-time (idempotent) deep-history seed for AUS_CPI_MONTHLY, per regime-aa
memo 2026-07-08-monthly-growth-inflation-cadence item 4:

  - AUS_CPI_MONTHLY  live = ABS complete monthly CPI (``CPI/1.10001.10.50.M``),
                     starts 2024-04 (the ABS backcast window for the full
                     monthly CPI introduced with the Nov-2025 publication).
                     Donor: the frozen "monthly CPI indicator"
                     ``CPI_M/1.10001.10.50.M`` (2017-09 → 2025-09; the ABS
                     discontinued the indicator when the complete monthly CPI
                     replaced it — frozen upstream, which is exactly why it is
                     a donor and NOT a registered library row).

Mechanism is identical to scripts/backfill_ind_prod_hist.py (forward_plan
§3.1.1 Pattern 9): the pre-seam history is written into the sister archive
``data/macro_economic_hist_x.csv``.  Consumers reading via
``library_utils.load_hist_with_archive`` see live ∪ sister with live winning
per cell, so the seeded cells surface only before the live series' start.

Base-splice: the indicator carries its own base (~2017=100 era) while the
complete monthly CPI is rebased (FY2024-25 era), so the donor is rescaled by
the mean(target/donor) ratio over the 2024-04 → 2025-09 overlap.  The two
series are methodologically close but not identical (the indicator priced
only part of the basket at monthly frequency), so the ratio-drift guard is
the real gate here — >2% drift aborts the seed.

The donor series_id lives here (not in macro_library_abs.csv) deliberately:
it must NOT participate in the live fetch/winner merge.  Recorded in
data/source_fallbacks.csv for provenance.

Run from the repo root:  python3 scripts/backfill_aus_cpi_monthly.py
"""

from __future__ import annotations

import csv
import io
import os
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from library_utils import sniff_hist_prefix_rows          # noqa: E402
from sources import abs as abs_src                         # noqa: E402

SISTER_CSV = "data/macro_economic_hist_x.csv"

DONOR_ID  = "CPI_M/1.10001.10.50.M"   # frozen 2025-09 — donor only
TARGET_ID = "CPI/1.10001.10.50.M"     # the registered live row (2024-04+)
COLUMN    = "AUS_CPI_MONTHLY"


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


def _splice_ratio(target_m: pd.Series, donor_m: pd.Series, label: str) -> float:
    """Mean target/donor ratio over the full overlap, with a drift check."""
    d = donor_m.reindex(target_m.index).dropna()
    t = target_m.reindex(d.index)
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
    """Snap a month-start-dated series onto Friday cells (ffill, capped 45d)."""
    filled = monthly.reindex(fridays.union(monthly.index)).sort_index().ffill()
    obs_dates = pd.Series(monthly.index, index=monthly.index) \
        .reindex(fridays.union(monthly.index)).sort_index().ffill()
    filled = filled.reindex(fridays)
    obs_dates = obs_dates.reindex(fridays)
    age_ok = (fridays - pd.DatetimeIndex(obs_dates)).days <= 45
    return filled.where(pd.Series(age_ok, index=fridays))


def main() -> None:
    print("== backfill_aus_cpi_monthly ==")
    sister_prefix, sister = _load_hist(SISTER_CSV)

    print(f"\n{COLUMN} — donor ABS CPI_M indicator → complete monthly CPI base")
    donor = abs_src.fetch_series_as_pandas(DONOR_ID)
    target = abs_src.fetch_series_as_pandas(TARGET_ID)
    if donor is None or donor.empty or target is None or target.empty:
        raise SystemExit("ABS donor/target fetch failed")
    print(f"  donor (CPI_M): {donor.index.min():%Y-%m} → {donor.index.max():%Y-%m} "
          f"n={len(donor)}")
    print(f"  target (CPI M-slice): {target.index.min():%Y-%m} → "
          f"{target.index.max():%Y-%m} n={len(target)}")

    ratio = _splice_ratio(target, donor, "AUS")
    seam = target.index.min()                       # 2024-04-01
    rebased = donor.loc[: seam - pd.Timedelta(days=1)] * ratio

    pre_fridays = sister.index[sister.index < seam]
    if COLUMN not in sister.columns:
        sister[COLUMN] = float("nan")
    seeded = _monthly_to_fridays(rebased, pre_fridays)
    sister.loc[pre_fridays, COLUMN] = seeded
    print(f"  seeded {seeded.notna().sum()} sister cells "
          f"({seeded.dropna().index.min():%Y-%m-%d} → seam {seam:%Y-%m-%d})")
    last_seed = seeded.dropna().iloc[-1]
    first_live = float(target.iloc[0])
    print(f"  seam check: last seeded {last_seed:.2f} vs first live {first_live:.2f} "
          f"({(first_live / last_seed - 1) * 100:+.2f}% step)")

    # ------------------------------------------------- extend sister metadata
    # One cell per column in the prefix; AUS_CPI_MONTHLY may be new. The next
    # daily write replaces this prefix wholesale with the live generation, so
    # this only needs to be sane in the interim.
    # sister already contains COLUMN here, so a prefix row's final length is
    # label cell + len(sister.columns) metadata cells (same as the writer's
    # Date + data-column layout).
    n_cols_before = len(sister.columns)
    meta = {
        "Column ID": COLUMN, "Series ID": DONOR_ID, "Source": "ABS",
        "Indicator": "Australia Monthly CPI (pre-2024-04 backfill, CPI_M indicator "
                     "rebased to the complete monthly CPI base)",
        "Country": "AUS", "Country Name": "Australia", "Region": "Asia-Pacific",
        "Category": "Prices", "Subcategory": "Consumer Prices",
        "Concept": "Prices / Inflation", "cycle_timing": "L",
        "Units": "Index (FY2024-25 base, rebased)", "Frequency": "Monthly",
        "Last Updated": "", "Last Observation": "",
    }
    header_labels = [row[0] for row in sister_prefix]
    already = any(COLUMN in row for row in sister_prefix)
    if not already:
        for row, label in zip(sister_prefix, header_labels):
            while len(row) < n_cols_before:
                row.append("")
            row.append(meta.get(label, ""))

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
