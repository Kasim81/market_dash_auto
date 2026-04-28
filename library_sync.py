"""library_sync.py — prune orphan columns from market_data_comp_hist.csv.

Companion to data_audit.py's Section B `registry_drift` check (forward_plan §0
/ §3.1). The library CSVs are the source of truth; this utility keeps the hist
file aligned with them after a library row has been edited or removed.

Behaviour:
  - Reads index_library.csv → expected base tickers (union of every
    ticker_yfinance_pr / ticker_yfinance_tr / ticker_fred_* field).
  - Reads market_data_comp_hist.csv → present base tickers (row 1
    "Ticker ID" metadata row, columns 2+).
  - Orphans = present − expected.
  - For each orphan ticker: archives every column that mentions it
    (`<ticker>_Local`, `<ticker>_USD`) to
    `data/_archived_columns/market_data_comp_hist__<ticker>__<YYYY-MM-DD>.csv`,
    then drops those columns from the live hist file.

Default mode is dry-run (reports what would happen). Pass `--confirm` to
apply. The `removed_tickers.csv` ledger is intentionally NOT updated by this
script — that ledger records human edits to the source-of-truth library
CSVs; this script is the downstream sync action.

Usage:
    python library_sync.py             # dry-run
    python library_sync.py --confirm   # apply
"""
from __future__ import annotations

import csv
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
ARCHIVE = DATA / "_archived_columns"

LIB_PATH  = DATA / "index_library.csv"
HIST_PATH = DATA / "market_data_comp_hist.csv"

TICKER_FIELDS = (
    "ticker_yfinance_pr", "ticker_yfinance_tr",
    "ticker_fred_tr", "ticker_fred_yield", "ticker_fred_oas",
    "ticker_fred_spread", "ticker_fred_duration",
)


def expected_tickers() -> set[str]:
    out: set[str] = set()
    with LIB_PATH.open(newline="") as f:
        for row in csv.DictReader(f):
            for field in TICKER_FIELDS:
                t = (row.get(field) or "").strip()
                if t:
                    out.add(t)
    return out


def hist_base_tickers(rows: list[list[str]]) -> set[str]:
    return {c.strip() for c in rows[0][2:] if c.strip()}


def column_indexes_for_ticker(rows: list[list[str]], ticker: str) -> list[int]:
    """Indices in each row that belong to the given base ticker. Row 1
    ("Ticker ID") holds the base; rows 12+ have suffixed names like
    `<ticker>_Local` / `<ticker>_USD`. Match on row 1 to be variant-agnostic."""
    return [i for i, c in enumerate(rows[0]) if c.strip() == ticker]


def archive_columns(rows: list[list[str]], ticker: str, idxs: list[int]) -> Path:
    """Write a small CSV containing the row-12 header and all data rows
    (rows 13+) for the orphan ticker columns, plus the Date column for
    reference."""
    ARCHIVE.mkdir(parents=True, exist_ok=True)
    out_path = ARCHIVE / f"market_data_comp_hist__{ticker}__{date.today().isoformat()}.csv"
    # Row 12 (index 11) has column headers like "Date", "<ticker>_Local"
    header_row = rows[11]
    keep_idxs = [1] + idxs  # column 1 is Date
    with out_path.open("w", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow([header_row[i] for i in keep_idxs])
        for r in rows[12:]:
            w.writerow([r[i] if i < len(r) else "" for i in keep_idxs])
    return out_path


def drop_columns(rows: list[list[str]], idxs: set[int]) -> list[list[str]]:
    return [[c for i, c in enumerate(r) if i not in idxs] for r in rows]


def main() -> int:
    confirm = "--confirm" in sys.argv

    expected = expected_tickers()
    with HIST_PATH.open(newline="") as f:
        rows = list(csv.reader(f))
    present = hist_base_tickers(rows)
    orphans = sorted(present - expected)

    if not orphans:
        print("library_sync: no drift — market_data_comp_hist.csv is in sync with index_library.csv")
        return 0

    print(f"library_sync: {len(orphans)} orphan ticker(s) found in market_data_comp_hist.csv:")
    drop_idxs: set[int] = set()
    for ticker in orphans:
        idxs = column_indexes_for_ticker(rows, ticker)
        print(f"  {ticker}  ({len(idxs)} column(s))")
        drop_idxs.update(idxs)

    if not confirm:
        print("\n(dry-run) re-run with --confirm to archive + drop these columns.")
        return 0

    print("\nApplying:")
    for ticker in orphans:
        idxs = column_indexes_for_ticker(rows, ticker)
        out_path = archive_columns(rows, ticker, idxs)
        print(f"  archived → {out_path.relative_to(ROOT)}")

    new_rows = drop_columns(rows, drop_idxs)
    with HIST_PATH.open("w", newline="") as f:
        csv.writer(f, lineterminator="\n").writerows(new_rows)
    n_dropped = len(drop_idxs)
    n_cols_after = len(new_rows[0]) if new_rows else 0
    print(f"  dropped {n_dropped} column(s); {n_cols_after} column(s) remain in {HIST_PATH.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
