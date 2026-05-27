"""
scripts/backadjust_hist_splits.py
=================================
One-time / on-demand back-adjustment of committed *_hist.csv (and their
*_hist_x.csv sisters) for splits registered in data/manual_splits.csv.

Why this exists separately from the runtime override:
  - fetch_data.py / fetch_hist.py call library_utils.apply_manual_splits()
    on every fresh yfinance pull, so the LIVE history self-corrects on the
    next daily rebuild.
  - The sister *_hist_x.csv is append-only with keep="first" dedup
    (library_utils._append_archive_rows), so an already-stored stale value
    is NEVER overwritten by a later corrected one. The sister therefore
    cannot self-heal — it must be corrected once, in place. This script does
    that, and also corrects the live file so the committed state is
    immediately consistent (rather than waiting a day for the rebuild).

Idempotent: for each (ticker, ex_date, ratio) it only divides the pre-ex_date
prices when the split discontinuity is actually still present at the boundary
(pre/post price ratio ≈ `ratio`). If the series is already continuous it is
left untouched, so re-running is safe.

Usage:
    python scripts/backadjust_hist_splits.py [--dry-run] [paths...]
Defaults to data/market_data_comp_hist.csv + its sister when no paths given.
"""
from __future__ import annotations

import csv
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
SPLITS_CSV = DATA / "manual_splits.csv"

# How close pre/post must be to `ratio` to count as an unadjusted split.
_RATIO_TOL = 0.25
META_ROWS_BY_FILE = 11  # market_data_comp_hist: 11 metadata rows, then header, then data


def load_splits() -> dict[str, list[tuple[datetime, float]]]:
    out: dict[str, list[tuple[datetime, float]]] = {}
    if not SPLITS_CSV.exists():
        return out
    with SPLITS_CSV.open(newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            tk = (row.get("ticker") or "").strip()
            ex = (row.get("ex_date") or "").strip()
            rt = (row.get("ratio") or "").strip()
            if not (tk and ex and rt):
                continue
            try:
                out.setdefault(tk, []).append(
                    (datetime.strptime(ex, "%Y-%m-%d"), float(rt))
                )
            except ValueError:
                continue
    return out


def _parse_date(s: str):
    try:
        return datetime.strptime(s.strip(), "%Y-%m-%d")
    except (ValueError, AttributeError):
        return None


def backadjust_file(path: Path, splits: dict, dry_run: bool) -> int:
    if not path.exists():
        print(f"  [skip] {path.name} — not found")
        return 0
    with path.open(newline="", encoding="utf-8") as f:
        rows = list(csv.reader(f))
    if not rows:
        return 0

    ticker_row = rows[0]            # row 0 = "Ticker ID" metadata row
    header = rows[META_ROWS_BY_FILE]  # row 11 = row_id,Date,<col>,...
    assert header[1].strip() == "Date", f"unexpected header in {path.name}: {header[:3]}"
    data = rows[META_ROWS_BY_FILE + 1:]

    changes = 0
    for ticker, entries in splits.items():
        # All columns (Local + USD variants) whose Ticker ID == ticker.
        cols = [c for c in range(2, len(ticker_row)) if ticker_row[c].strip() == ticker]
        if not cols:
            continue
        for ex_dt, ratio in entries:
            for c in cols:
                # Find the last non-blank value strictly before ex_date and the
                # first on/after, to test whether the discontinuity is present.
                pre_val = post_val = None
                for r in data:
                    if c >= len(r):
                        continue
                    d = _parse_date(r[1])
                    v = r[c].strip()
                    if d is None or v == "":
                        continue
                    try:
                        fv = float(v)
                    except ValueError:
                        continue
                    if d < ex_dt:
                        pre_val = fv
                    elif post_val is None:
                        post_val = fv
                if pre_val is None or post_val is None or post_val == 0:
                    continue
                observed = pre_val / post_val
                if abs(observed - ratio) > _RATIO_TOL * ratio:
                    # Either no jump (already adjusted) or not this ratio — skip.
                    print(f"  [skip] {path.name} col{c} ({ticker}): boundary ratio "
                          f"{observed:.3f} not ≈ {ratio} — leaving untouched")
                    continue
                # Divide every pre-ex_date value by ratio.
                n = 0
                for r in data:
                    if c >= len(r):
                        continue
                    d = _parse_date(r[1])
                    v = r[c].strip()
                    if d is None or v == "" or d >= ex_dt:
                        continue
                    try:
                        r[c] = repr(float(v) / ratio)
                        n += 1
                    except ValueError:
                        continue
                changes += n
                print(f"  [fix]  {path.name} col{c} ({ticker} {header[c]}): "
                      f"{n} pre-{ex_dt.date()} values ÷{ratio:g}")

    if changes and not dry_run:
        with path.open("w", newline="", encoding="utf-8") as f:
            csv.writer(f, lineterminator="\n").writerows(rows)
        print(f"  [write] {path.name}: {changes} cells adjusted")
    elif changes:
        print(f"  [dry-run] {path.name}: would adjust {changes} cells")
    else:
        print(f"  [ok] {path.name}: nothing to adjust")
    return changes


def main(argv: list[str]) -> int:
    dry_run = "--dry-run" in argv
    paths = [Path(a) for a in argv if not a.startswith("--")]
    if not paths:
        live = DATA / "market_data_comp_hist.csv"
        paths = [live, live.with_name("market_data_comp_hist_x.csv")]

    splits = load_splits()
    if not splits:
        print("No manual splits registered — nothing to do.")
        return 0
    print(f"Manual splits: {', '.join(splits)}")
    for p in paths:
        backadjust_file(p, splits, dry_run)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
