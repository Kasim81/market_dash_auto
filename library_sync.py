"""library_sync.py — prune orphan columns from hist CSVs.

Companion to data_audit.py's Section B `registry_drift` check (forward_plan §0
/ §3.1). The library CSVs are the source of truth; this utility keeps the hist
files aligned with them after a library row has been edited or removed.

Covers three hist↔library pairs (one ``SyncSpec`` each — §2.C C6):
  - market_data_comp_hist.csv       ↔ index_library.csv (yfinance + FRED ticker fields)
  - macro_economic_hist.csv         ↔ macro_library_*.csv (registry-driven)
  - macro_market_hist.csv           ↔ macro_indicator_library.csv (id × {_raw,_zscore,_regime,_fwd_regime})

For each orphan column, the existing data is archived to
data/_archived_columns/<hist_basename>__<id>__<YYYY-MM-DD>.csv (preserving
historical observations), then the column is dropped from the live hist file
(and mirrored on the *_hist_x.csv sister so the union schema stays aligned).

§2.C C6 (2026-07-09): the three hand-written expected/present/orphan/archive
trios collapsed into ``SYNC_SPECS`` + one generic ``sync(spec, confirm)``.
Only the *expected-ids* derivation is genuinely per-pair; everything else
(present ids, orphan column indexes, archive writer, sister mirror) is shared.
The archive writer now locates each file's data-header row by inspection
("Date" in the first two cells — the same rule as
``library_utils.sniff_hist_prefix_rows``) instead of hardcoded row counts;
this fixes a latent bug where ``macro_economic_hist`` archives written after
the 14→15 metadata-row growth (§2.A A14) included the "Date" header row as a
data row. A fourth hist pair (§5 multifreq) becomes one more spec entry.

Default mode is dry-run (reports what would happen). Pass `--confirm` to
apply. The `removed_tickers.csv` ledger is intentionally NOT updated by this
script — that ledger records human edits to the source-of-truth library
CSVs; this script is the downstream sync action.

Usage:
    python library_sync.py             # dry-run, all pairs
    python library_sync.py --confirm   # apply, all pairs
"""
from __future__ import annotations

import csv
import sys
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Callable

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
ARCHIVE = DATA / "_archived_columns"


# =============================================================================
# Generic CSV helpers
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
# Per-pair expected-id derivation (the only genuinely pair-specific logic)
# =============================================================================

# ---- Pair 1: comp pipeline ----
#
# market_data_comp_hist.csv layout:
#   row 0 ("Ticker ID")   col 0 = "" , col 1 = "Ticker ID", cols 2+ = base ticker
#   rows 1..N             other metadata (11 rows pre-A16, 12 after)
#   data header row       col 0 = "row_id", col 1 = "Date", cols 2+ = "<ticker>_Local"/"_USD"
#   rows below            data
#
# Each base ticker shows up twice in row 0 (once for _Local, once for _USD).

COMP_HIST = DATA / "market_data_comp_hist.csv"
COMP_LIB = DATA / "index_library.csv"
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


# ---- Pair 2: macro_economic_hist ↔ macro_library_*.csv ----
#
# macro_economic_hist.csv layout:
#   row 0  ("Column ID")  col 0 = "Column ID", cols 1+ = column IDs (T10Y2Y, USA_CLI, ...)
#   rows 1..N             other metadata (13 rows pre-A14, 14 after)
#   data header row       col 0 = "Date", cols 1+ = column IDs (same as row 0)
#   rows below            data
#
# Column-name derivation per source:
#   single-series sources: col_id = row['col'] or row['series_id']
#   OECD:                  col_id = f"{country}_{series_id}" per oecd_countries
#   World Bank, IMF:       col_id = f"{country}_{col}" for each library country

MACRO_ECON_HIST = DATA / "macro_economic_hist.csv"
# Derived from the shared identity table (sources.SOURCE_REGISTRY, §2.C C2) —
# a new source registered there is automatically covered by the sync.
from sources import LABEL_BY_STEM as _LABEL_BY_STEM  # noqa: E402

MACRO_LIBS = {stem: DATA / f"macro_library_{stem}.csv" for stem in _LABEL_BY_STEM}
COUNTRIES_LIB = DATA / "macro_library_countries.csv"


def _read_country_codes() -> list[str]:
    if not COUNTRIES_LIB.exists():
        return []
    with COUNTRIES_LIB.open(newline="") as f:
        return [r["code"].strip() for r in csv.DictReader(f) if r.get("code")]


def _macro_econ_expected() -> set[str]:
    out: set[str] = set()
    country_codes = _read_country_codes()

    # Single-column sources (col or series_id): every registered source except
    # the three multi-country fan-outs (OECD / World Bank / IMF) below.
    for src in sorted(set(MACRO_LIBS) - {"oecd", "worldbank", "imf"}):
        path = MACRO_LIBS[src]
        if not path.exists():
            continue
        with path.open(newline="") as f:
            for r in csv.DictReader(f):
                col = (r.get("col") or "").strip() or (r.get("series_id") or "").strip()
                if col:
                    out.add(col)

    # OECD: per-row country fan-out via oecd_countries field
    if MACRO_LIBS["oecd"].exists():
        with MACRO_LIBS["oecd"].open(newline="") as f:
            for r in csv.DictReader(f):
                base = (r.get("series_id") or "").strip()
                if not base:
                    continue
                countries_str = (r.get("oecd_countries") or "").strip()
                for country in countries_str.split("+"):
                    country = country.strip()
                    if country:
                        out.add(f"{country}_{base}")

    # WB, IMF: every row × every country in macro_library_countries.csv
    for src in ("worldbank", "imf"):
        path = MACRO_LIBS[src]
        if not path.exists():
            continue
        with path.open(newline="") as f:
            for r in csv.DictReader(f):
                col = (r.get("col") or "").strip() or (r.get("series_id") or "").strip()
                if not col:
                    continue
                for country in country_codes:
                    out.add(f"{country}_{col}")

    return out


# ---- Pair 3: macro_market_hist ↔ macro_indicator_library ----
#
# macro_market_hist.csv layout (no metadata prefix):
#   row 0 (data header)  col 0 = "Date", cols 1+ = "<id>_raw" / "<id>_zscore"
#                        / "<id>_regime" / "<id>_fwd_regime"
#   rows 1+              data

MACRO_MKT_HIST = DATA / "macro_market_hist.csv"
MACRO_IND_LIB = DATA / "macro_indicator_library.csv"
INDICATOR_SUFFIXES = ("_raw", "_zscore", "_regime", "_fwd_regime")


def _macro_mkt_expected() -> set[str]:
    out: set[str] = set()
    if not MACRO_IND_LIB.exists():
        return out
    with MACRO_IND_LIB.open(newline="") as f:
        for r in csv.DictReader(f):
            ind_id = (r.get("id") or "").strip()
            if ind_id:
                for suf in INDICATOR_SUFFIXES:
                    out.add(f"{ind_id}{suf}")
    return out


# =============================================================================
# SyncSpec registry — one entry per hist↔library pair (§2.C C6)
# =============================================================================

@dataclass(frozen=True)
class SyncSpec:
    """One hist↔library pair.

    name          — display name (hist basename) for log lines
    hist_path     — the live hist CSV (sister derived by _hist → _hist_x)
    expected      — callable returning the ids the library says must exist
    id_start_col  — first row-0 cell that is an id (2 for comp, whose row 0 is
                    ["", "Ticker ID", <ids>...]; 1 for the label-first layouts)
    """
    name: str
    hist_path: Path
    expected: Callable[[], set[str]]
    id_start_col: int


SYNC_SPECS: tuple[SyncSpec, ...] = (
    SyncSpec("market_data_comp_hist.csv", COMP_HIST, _comp_expected, 2),
    SyncSpec("macro_economic_hist.csv", MACRO_ECON_HIST, _macro_econ_expected, 1),
    SyncSpec("macro_market_hist.csv", MACRO_MKT_HIST, _macro_mkt_expected, 1),
)


# =============================================================================
# Generic present / orphan-index / archive machinery
# =============================================================================

def _present_ids(spec: SyncSpec, rows: list[list[str]]) -> set[str]:
    """Ids present in the hist file = row-0 cells from the spec's start col."""
    return {c.strip() for c in rows[0][spec.id_start_col:] if c.strip()}


def _idxs_for_id(rows: list[list[str]], id_: str) -> list[int]:
    """Column indexes carrying this id (comp ids appear twice: _Local + _USD)."""
    return [i for i, c in enumerate(rows[0]) if c.strip() == id_]


def _locate_data_header(rows: list[list[str]]) -> int:
    """Index of the data-header row: the first row whose first two cells
    include "Date" (same rule as library_utils.sniff_hist_prefix_rows, so
    every metadata-prefix generation parses — 11/12-row comp, 14/15-row
    macro, and the header-only macro_market layout where this is row 0)."""
    return next(i for i, r in enumerate(rows[:40])
                if "Date" in [c.strip() for c in r[:2]])


def _archive_orphan(spec: SyncSpec, rows: list[list[str]],
                    id_: str, idxs: list[int]) -> Path:
    """Write the orphan's observations to data/_archived_columns/ before the
    drop. Header labels come from the data-header row (for the comp layout
    that's the "<ticker>_Local"/"_USD" names; for the macro layouts the
    data-header repeats the row-0 ids, and its col 0 is literally "Date")."""
    ARCHIVE.mkdir(parents=True, exist_ok=True)
    out_path = ARCHIVE / f"{spec.hist_path.stem}__{id_}__{date.today().isoformat()}.csv"
    hdr_idx = _locate_data_header(rows)
    header_row = rows[hdr_idx]
    date_col = [c.strip() for c in header_row[:2]].index("Date")
    keep_idxs = [date_col] + idxs
    with out_path.open("w", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow([header_row[i] if i < len(header_row) else "" for i in keep_idxs])
        for r in rows[hdr_idx + 1:]:
            w.writerow([r[i] if i < len(r) else "" for i in keep_idxs])
    return out_path


def sync(spec: SyncSpec, confirm: bool) -> int:
    """Drive one library↔hist pair. Returns count of orphan IDs."""
    if not spec.hist_path.exists():
        print(f"library_sync [{spec.name}]: hist file missing — skipped")
        return 0

    rows = _read_csv_rows(spec.hist_path)
    present = _present_ids(spec, rows)
    orphans = sorted(present - spec.expected())

    if not orphans:
        print(f"library_sync [{spec.name}]: no drift — in sync with library")
        return 0

    print(f"library_sync [{spec.name}]: {len(orphans)} orphan(s):")
    drop_idxs: set[int] = set()
    for orphan in orphans:
        idxs = _idxs_for_id(rows, orphan)
        print(f"  {orphan}  ({len(idxs)} column(s))")
        drop_idxs.update(idxs)

    if not confirm:
        return len(orphans)

    print(f"\nApplying [{spec.name}]:")
    for orphan in orphans:
        idxs = _idxs_for_id(rows, orphan)
        out_path = _archive_orphan(spec, rows, orphan, idxs)
        print(f"  archived → {out_path.relative_to(ROOT)}")

    new_rows = _drop_columns(rows, drop_idxs)
    _write_csv_rows(spec.hist_path, new_rows)
    n_cols_after = len(new_rows[0]) if new_rows else 0
    print(f"  dropped {len(drop_idxs)} column(s); {n_cols_after} column(s) "
          f"remain in {spec.hist_path.relative_to(ROOT)}")

    # Mirror the column drop on the *_hist_x.csv sister (per forward_plan
    # §3.1.1): sister and live must share the same column schema or
    # load_hist_with_archive's union semantics break.
    sister_path = spec.hist_path.with_name(
        spec.hist_path.name.replace("_hist.csv", "_hist_x.csv"))
    if sister_path.exists():
        sister_rows = _read_csv_rows(sister_path)
        sister_new = _drop_columns(sister_rows, drop_idxs)
        _write_csv_rows(sister_path, sister_new)
        print(f"  mirrored drop on sister: {sister_path.relative_to(ROOT)}")

    return len(orphans)


# =============================================================================
# Entry point
# =============================================================================

def main() -> int:
    confirm = "--confirm" in sys.argv

    total_orphans = sum(sync(spec, confirm) for spec in SYNC_SPECS)

    if total_orphans and not confirm:
        print(f"\n(dry-run) {total_orphans} orphan id(s) total — "
              f"re-run with --confirm to archive + drop.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
