"""library_sync.py — prune orphan columns from hist CSVs.

Companion to data_audit.py's Section B `registry_drift` check (forward_plan §0
/ §3.1). The library CSVs are the source of truth; this utility keeps the hist
files aligned with them after a library row has been edited or removed.

Covers three hist↔library pairs:
  - market_data_comp_hist.csv       ↔ index_library.csv (yfinance + FRED ticker fields)
  - macro_economic_hist.csv         ↔ macro_library_{fred,oecd,worldbank,imf,dbnomics,ifo}.csv
  - macro_market_hist.csv           ↔ macro_indicator_library.csv (id × {_raw,_zscore,_regime,_fwd_regime})

For each orphan column, the existing data is archived to
data/_archived_columns/<hist_basename>__<id>__<YYYY-MM-DD>.csv (preserving
historical observations), then the column is dropped from the live hist file.

Default mode is dry-run (reports what would happen). Pass `--confirm` to
apply. The `removed_tickers.csv` ledger is intentionally NOT updated by this
script — that ledger records human edits to the source-of-truth library
CSVs; this script is the downstream sync action.

Usage:
    python library_sync.py             # dry-run, all 3 pairs
    python library_sync.py --confirm   # apply, all 3 pairs
"""
from __future__ import annotations

import csv
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
ARCHIVE = DATA / "_archived_columns"


# =============================================================================
# Generic helpers
# =============================================================================

def _read_csv_rows(path: Path) -> list[list[str]]:
    with path.open(newline="") as f:
        return list(csv.reader(f))


def _write_csv_rows(path: Path, rows: list[list[str]]) -> None:
    with path.open("w", newline="") as f:
        csv.writer(f, lineterminator="\n").writerows(rows)


def _drop_columns(rows: list[list[str]], idxs: set[int]) -> list[list[str]]:
    return [[c for i, c in enumerate(r) if i not in idxs] for r in rows]


# =============================================================================
# Pair 1 — comp pipeline (existing behaviour)
# =============================================================================
#
# market_data_comp_hist.csv layout:
#   row 0 ("Ticker ID")   col 0 = "" , col 1 = "Ticker ID", cols 2+ = base ticker
#   rows 1-10             other metadata
#   row 11 (data header)  col 0 = "row_id", col 1 = "Date", cols 2+ = "<ticker>_Local" / "<ticker>_USD"
#   rows 12+              data
#
# Each base ticker shows up twice in row 0 (once for _Local, once for _USD).

COMP_HIST   = DATA / "market_data_comp_hist.csv"
COMP_LIB    = DATA / "index_library.csv"
COMP_TICKER_FIELDS = (
    "ticker_yfinance_pr", "ticker_yfinance_tr",
    "ticker_fred_tr", "ticker_fred_yield", "ticker_fred_oas",
    "ticker_fred_spread", "ticker_fred_duration",
)


def _comp_expected() -> set[str]:
    out: set[str] = set()
    with COMP_LIB.open(newline="") as f:
        for row in csv.DictReader(f):
            for field in COMP_TICKER_FIELDS:
                t = (row.get(field) or "").strip()
                if t:
                    out.add(t)
    return out


def _comp_present(rows: list[list[str]]) -> set[str]:
    return {c.strip() for c in rows[0][2:] if c.strip()}


def _comp_idxs_for_orphan(rows: list[list[str]], ticker: str) -> list[int]:
    return [i for i, c in enumerate(rows[0]) if c.strip() == ticker]


def _comp_archive(rows: list[list[str]], ticker: str, idxs: list[int]) -> Path:
    ARCHIVE.mkdir(parents=True, exist_ok=True)
    out_path = ARCHIVE / f"market_data_comp_hist__{ticker}__{date.today().isoformat()}.csv"
    header_row = rows[11]            # data-header row: "row_id, Date, <ticker>_Local, ..."
    keep_idxs = [1] + idxs           # col 1 is Date
    with out_path.open("w", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow([header_row[i] for i in keep_idxs])
        for r in rows[12:]:
            w.writerow([r[i] if i < len(r) else "" for i in keep_idxs])
    return out_path


def sync_comp(confirm: bool) -> int:
    return _run_pair(
        name="market_data_comp_hist.csv",
        hist_path=COMP_HIST,
        expected=_comp_expected(),
        present_fn=_comp_present,
        idxs_fn=_comp_idxs_for_orphan,
        archive_fn=_comp_archive,
        confirm=confirm,
    )


# =============================================================================
# Generic per-pair runner
# =============================================================================

def _run_pair(
    *,
    name: str,
    hist_path: Path,
    expected: set[str],
    present_fn,
    idxs_fn,
    archive_fn,
    confirm: bool,
) -> int:
    """Drive one library↔hist pair. Returns count of orphan IDs."""
    if not hist_path.exists():
        print(f"library_sync [{name}]: hist file missing — skipped")
        return 0

    rows = _read_csv_rows(hist_path)
    present = present_fn(rows)
    orphans = sorted(present - expected)

    if not orphans:
        print(f"library_sync [{name}]: no drift — in sync with library")
        return 0

    print(f"library_sync [{name}]: {len(orphans)} orphan(s):")
    drop_idxs: set[int] = set()
    for orphan in orphans:
        idxs = idxs_fn(rows, orphan)
        print(f"  {orphan}  ({len(idxs)} column(s))")
        drop_idxs.update(idxs)

    if not confirm:
        return len(orphans)

    print(f"\nApplying [{name}]:")
    for orphan in orphans:
        idxs = idxs_fn(rows, orphan)
        out_path = archive_fn(rows, orphan, idxs)
        print(f"  archived → {out_path.relative_to(ROOT)}")

    new_rows = _drop_columns(rows, drop_idxs)
    _write_csv_rows(hist_path, new_rows)
    n_cols_after = len(new_rows[0]) if new_rows else 0
    print(f"  dropped {len(drop_idxs)} column(s); {n_cols_after} column(s) remain in {hist_path.relative_to(ROOT)}")
    return len(orphans)


# =============================================================================
# Entry point
# =============================================================================

def main() -> int:
    confirm = "--confirm" in sys.argv

    total_orphans = 0
    total_orphans += sync_comp(confirm)

    if total_orphans and not confirm:
        print(f"\n(dry-run) {total_orphans} orphan id(s) total — re-run with --confirm to archive + drop.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
