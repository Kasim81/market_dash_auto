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
# Pair 2 — macro_economic_hist ↔ 6 macro library CSVs
# =============================================================================
#
# macro_economic_hist.csv layout:
#   row 0  ("Column ID")  col 0 = "Column ID", cols 1+ = column IDs (T10Y2Y, USA_CLI, ...)
#   rows 1-13             other metadata (Series ID, Source, Indicator, Country, ...)
#   row 14 ("Date")       col 0 = "Date" (header label), cols 1+ = column IDs (same as row 0)
#   rows 15+              data (col 0 = date string, cols 1+ = numeric)
#
# Column-name derivation per source:
#   FRED, DB.nomics, ifo:  col_id = row['col'] or row['series_id']         (single)
#   OECD:                  col_id = f"{country}_{series_id}" for each country in oecd_countries
#   World Bank, IMF:       col_id = f"{country}_{col}" for each of the 12 countries

MACRO_ECON_HIST = DATA / "macro_economic_hist.csv"
MACRO_LIBS = {
    "fred":      DATA / "macro_library_fred.csv",
    "oecd":      DATA / "macro_library_oecd.csv",
    "worldbank": DATA / "macro_library_worldbank.csv",
    "imf":       DATA / "macro_library_imf.csv",
    "dbnomics":  DATA / "macro_library_dbnomics.csv",
    "ifo":       DATA / "macro_library_ifo.csv",
    "boe":       DATA / "macro_library_boe.csv",
    "ecb":       DATA / "macro_library_ecb.csv",
    "boj":       DATA / "macro_library_boj.csv",
    "estat":     DATA / "macro_library_estat.csv",
    "nasdaqdl":  DATA / "macro_library_nasdaqdl.csv",
    "lbma":      DATA / "macro_library_lbma.csv",
}
COUNTRIES_LIB = DATA / "macro_library_countries.csv"


def _read_country_codes() -> list[str]:
    if not COUNTRIES_LIB.exists():
        return []
    with COUNTRIES_LIB.open(newline="") as f:
        return [r["code"].strip() for r in csv.DictReader(f) if r.get("code")]


def _macro_econ_expected() -> set[str]:
    out: set[str] = set()
    country_codes = _read_country_codes()

    # FRED, DB.nomics, ifo, BoE, ECB, BoJ, e-Stat: col or series_id
    for src in ("fred", "dbnomics", "ifo", "boe", "ecb", "boj", "estat", "nasdaqdl", "lbma"):
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


def _macro_econ_present(rows: list[list[str]]) -> set[str]:
    # Row 0 is "Column ID, T10Y2Y, T10Y3M, ..."; col 0 is the metadata-row label.
    return {c.strip() for c in rows[0][1:] if c.strip()}


def _macro_econ_idxs_for_orphan(rows: list[list[str]], col_id: str) -> list[int]:
    return [i for i, c in enumerate(rows[0]) if c.strip() == col_id]


def _macro_econ_archive(rows: list[list[str]], col_id: str, idxs: list[int]) -> Path:
    ARCHIVE.mkdir(parents=True, exist_ok=True)
    out_path = ARCHIVE / f"macro_economic_hist__{col_id}__{date.today().isoformat()}.csv"
    keep_idxs = [0] + idxs           # col 0 holds dates from row 15 onwards
    with out_path.open("w", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        # Header: use the row-0 (Column ID) values so the archive labels are
        # readable; use literal "Date" for col 0.
        w.writerow(["Date"] + [rows[0][i] for i in idxs])
        for r in rows[15:]:
            w.writerow([r[i] if i < len(r) else "" for i in keep_idxs])
    return out_path


def sync_macro_economic(confirm: bool) -> int:
    return _run_pair(
        name="macro_economic_hist.csv",
        hist_path=MACRO_ECON_HIST,
        expected=_macro_econ_expected(),
        present_fn=_macro_econ_present,
        idxs_fn=_macro_econ_idxs_for_orphan,
        archive_fn=_macro_econ_archive,
        confirm=confirm,
    )


# =============================================================================
# Pair 3 — macro_market_hist ↔ macro_indicator_library
# =============================================================================
#
# macro_market_hist.csv layout (no metadata prefix):
#   row 0 (data header)  col 0 = "Date", cols 1+ = "<id>_raw" / "<id>_zscore"
#                        / "<id>_regime" / "<id>_fwd_regime"
#   rows 1+              data
#
# Each indicator id from macro_indicator_library.csv produces 4 columns.

MACRO_MKT_HIST = DATA / "macro_market_hist.csv"
MACRO_IND_LIB  = DATA / "macro_indicator_library.csv"
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


def _macro_mkt_present(rows: list[list[str]]) -> set[str]:
    # Row 0 is the data header: "Date, US_G1_raw, US_G1_zscore, ..."
    return {c.strip() for c in rows[0][1:] if c.strip()}


def _macro_mkt_idxs_for_orphan(rows: list[list[str]], col_name: str) -> list[int]:
    return [i for i, c in enumerate(rows[0]) if c.strip() == col_name]


def _macro_mkt_archive(rows: list[list[str]], col_name: str, idxs: list[int]) -> Path:
    ARCHIVE.mkdir(parents=True, exist_ok=True)
    out_path = ARCHIVE / f"macro_market_hist__{col_name}__{date.today().isoformat()}.csv"
    keep_idxs = [0] + idxs           # col 0 = Date
    with out_path.open("w", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow([rows[0][i] for i in keep_idxs])
        for r in rows[1:]:
            w.writerow([r[i] if i < len(r) else "" for i in keep_idxs])
    return out_path


def sync_macro_market(confirm: bool) -> int:
    return _run_pair(
        name="macro_market_hist.csv",
        hist_path=MACRO_MKT_HIST,
        expected=_macro_mkt_expected(),
        present_fn=_macro_mkt_present,
        idxs_fn=_macro_mkt_idxs_for_orphan,
        archive_fn=_macro_mkt_archive,
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

    # Mirror the column drop on the *_hist_x.csv sister (per forward_plan §3.1.1):
    # sister and live must share the same column schema or load_hist_with_archive's
    # union semantics break.
    sister_path = hist_path.with_name(hist_path.name.replace("_hist.csv", "_hist_x.csv"))
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

    total_orphans = 0
    total_orphans += sync_comp(confirm)
    total_orphans += sync_macro_economic(confirm)
    total_orphans += sync_macro_market(confirm)

    if total_orphans and not confirm:
        print(f"\n(dry-run) {total_orphans} orphan id(s) total — re-run with --confirm to archive + drop.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
