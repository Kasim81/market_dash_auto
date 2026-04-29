"""audit_writeback.py — flip dead-ticker validation_status to UNAVAILABLE.

Sub-track 3 of forward_plan §3.1. The daily audit (`data_audit.py`)
*reports* dead yfinance tickers but does not edit `index_library.csv`.
This utility is the writeback half: it tracks how long each ticker has
been on the dead list and, after N=14 consecutive days, flips
`validation_status` from CONFIRMED to UNAVAILABLE.

Workflow:
  1. Parse data_audit.txt for the YFINANCE_DEAD list (Section A).
  2. Read/update data/yfinance_failure_streaks.csv:
       schema: ticker, first_seen_dead, last_seen_dead, consecutive_fail_days
     For each CONFIRMED ticker in today's dead list: streak++ (or =1 new).
     Tickers no longer in the dead list are dropped from the streak file
     (streak broken).
  3. For any streak >= UNAVAILABLE_THRESHOLD (14): set validation_status
     = UNAVAILABLE on the matching row in index_library.csv (only when
     current status is CONFIRMED — manual UNAVAILABLE is preserved; if
     an operator restored CONFIRMED after a real fix, the streak resets
     naturally on the next FRESH cycle).
  4. Append a one-line summary to audit_comment.md so the daily GitHub
     Issue comment captures any writeback actions.

Manual override always wins: setting `validation_status = CONFIRMED`
back on a previously-flagged row will re-include it in the fetch on
the next pipeline run; if it stays dead it will start a fresh streak.

Run as part of CI after `data_audit.py` and before the daily Issue
comment is posted, so the comment surfaces today's writeback actions.

Usage:
    python audit_writeback.py            # update streaks + flip if needed
    python audit_writeback.py --dry-run  # report-only; no CSV edits
"""
from __future__ import annotations

import csv
import re
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"

AUDIT_REPORT       = ROOT / "data_audit.txt"
AUDIT_COMMENT      = ROOT / "audit_comment.md"
INDEX_LIB          = DATA / "index_library.csv"
STREAK_CSV         = DATA / "yfinance_failure_streaks.csv"

UNAVAILABLE_THRESHOLD = 14   # consecutive days of being on the dead list

STREAK_HEADER = ["ticker", "first_seen_dead", "last_seen_dead", "consecutive_fail_days"]


def _parse_dead_tickers(report_text: str) -> set[str]:
    """Extract the YFINANCE_DEAD list from data_audit.txt Section A."""
    out: set[str] = set()
    in_section_a = False
    for line in report_text.splitlines():
        if line.startswith("--- Section A"):
            in_section_a = True
            continue
        if in_section_a and line.startswith("--- Section"):
            break
        if in_section_a:
            m = re.match(r"^\s+YFINANCE_DEAD\s+(\S+)", line)
            if m:
                out.add(m.group(1))
    return out


def _read_streaks() -> dict[str, dict]:
    """Return {ticker: {first_seen_dead, last_seen_dead, consecutive_fail_days}}."""
    if not STREAK_CSV.exists():
        return {}
    out: dict[str, dict] = {}
    with STREAK_CSV.open(newline="") as f:
        for r in csv.DictReader(f):
            t = r.get("ticker", "").strip()
            if t:
                out[t] = {
                    "first_seen_dead":        r.get("first_seen_dead", "").strip(),
                    "last_seen_dead":         r.get("last_seen_dead", "").strip(),
                    "consecutive_fail_days":  int((r.get("consecutive_fail_days") or "0").strip() or 0),
                }
    return out


def _write_streaks(streaks: dict[str, dict]) -> None:
    with STREAK_CSV.open("w", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(STREAK_HEADER)
        for ticker in sorted(streaks):
            s = streaks[ticker]
            w.writerow([
                ticker,
                s["first_seen_dead"],
                s["last_seen_dead"],
                s["consecutive_fail_days"],
            ])


def _index_library_rows() -> list[list[str]]:
    with INDEX_LIB.open(newline="") as f:
        return list(csv.reader(f))


def _ticker_to_validation_status(rows: list[list[str]]) -> dict[str, str]:
    """Map every PR/TR ticker → its row's validation_status (last write wins
    if a ticker appears in both PR and TR fields, but in practice they don't
    collide). Used to gate writeback on current status."""
    header = rows[0]
    i_pr  = header.index("ticker_yfinance_pr")
    i_tr  = header.index("ticker_yfinance_tr")
    i_st  = header.index("validation_status")
    out: dict[str, str] = {}
    for r in rows[1:]:
        if len(r) <= max(i_pr, i_tr, i_st):
            continue
        st = r[i_st].strip()
        for i in (i_pr, i_tr):
            t = r[i].strip()
            if t:
                out[t] = st
    return out


def _flip_validation_status(rows: list[list[str]], tickers: set[str]) -> int:
    """Set validation_status='UNAVAILABLE' on every row whose PR or TR ticker
    is in `tickers` AND whose current status is CONFIRMED. Returns the
    number of rows actually flipped."""
    if not tickers:
        return 0
    header = rows[0]
    i_pr = header.index("ticker_yfinance_pr")
    i_tr = header.index("ticker_yfinance_tr")
    i_st = header.index("validation_status")
    n = 0
    for r in rows[1:]:
        if len(r) <= max(i_pr, i_tr, i_st):
            continue
        if r[i_st].strip() != "CONFIRMED":
            continue
        if r[i_pr].strip() in tickers or r[i_tr].strip() in tickers:
            r[i_st] = "UNAVAILABLE"
            n += 1
    return n


def main() -> int:
    dry_run = "--dry-run" in sys.argv

    if not AUDIT_REPORT.exists():
        print(f"audit_writeback: {AUDIT_REPORT.name} missing — run data_audit.py first")
        return 0
    if not INDEX_LIB.exists():
        print(f"audit_writeback: {INDEX_LIB.name} missing — cannot write back")
        return 0

    today = date.today().isoformat()
    dead = _parse_dead_tickers(AUDIT_REPORT.read_text())
    lib_rows = _index_library_rows()
    status_by_ticker = _ticker_to_validation_status(lib_rows)
    streaks = _read_streaks()

    # Tickers no longer in the dead list → drop from streaks (broken).
    for t in list(streaks.keys()):
        if t not in dead:
            del streaks[t]

    # Tickers in the dead list with current status CONFIRMED → increment streak.
    # If status is UNAVAILABLE (already flagged or manually retired), don't
    # touch the streak — the registry already reflects reality.
    for t in dead:
        st = status_by_ticker.get(t, "")
        if st != "CONFIRMED":
            # Either UNAVAILABLE (already known) or ticker not in library at
            # all (e.g. a stray reference in pipeline.log). Skip.
            streaks.pop(t, None)
            continue
        if t in streaks:
            streaks[t]["last_seen_dead"] = today
            streaks[t]["consecutive_fail_days"] += 1
        else:
            streaks[t] = {
                "first_seen_dead":       today,
                "last_seen_dead":        today,
                "consecutive_fail_days": 1,
            }

    # Anything that crossed the threshold this run gets flipped.
    to_flip = {
        t for t, s in streaks.items() if s["consecutive_fail_days"] >= UNAVAILABLE_THRESHOLD
    }
    n_flipped = _flip_validation_status(lib_rows, to_flip) if to_flip else 0

    print(f"audit_writeback: {len(dead)} dead ticker(s) reported by audit; "
          f"{len(streaks)} active streak(s); {n_flipped} flipped to UNAVAILABLE this run")
    if to_flip:
        for t in sorted(to_flip):
            s = streaks[t]
            print(f"  {t}  streak={s['consecutive_fail_days']}d (first={s['first_seen_dead']})")

    if dry_run:
        print("(dry-run) no CSV edits applied.")
        return 0

    _write_streaks(streaks)
    if n_flipped:
        with INDEX_LIB.open("w", newline="") as f:
            csv.writer(f, lineterminator="\n").writerows(lib_rows)

    # Append summary line to audit_comment.md so the daily GitHub Issue
    # comment surfaces today's writeback actions.
    if AUDIT_COMMENT.exists() and (n_flipped or len(streaks)):
        with AUDIT_COMMENT.open("a") as f:
            f.write("\n")
            if n_flipped:
                f.write(f"_audit_writeback: flipped {n_flipped} row(s) to validation_status=UNAVAILABLE "
                        f"after {UNAVAILABLE_THRESHOLD}-day dead-list streak: "
                        f"{', '.join(sorted(to_flip))}._\n")
            elif streaks:
                f.write(f"_audit_writeback: {len(streaks)} ticker(s) on active dead-list streak "
                        f"(threshold {UNAVAILABLE_THRESHOLD}d); none flipped this run._\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
