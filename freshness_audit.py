"""freshness_audit.py — per-ticker data-freshness audit (§2.6 of forward_plan.md).

Walks every `data/macro_library_*.csv` registry, finds each series' last non-null
observation in the unified `data/macro_economic_hist.csv`, compares the age of
that observation against a per-frequency tolerance (driven by
`data/freshness_thresholds.csv` plus per-row overrides in the registry's
`freshness_override_days` column), and emits a sorted FRESH/STALE/EXPIRED
report.

Exits with status 0 if every series is FRESH, status 1 if any series is STALE
or EXPIRED.

Usage:
    python freshness_audit.py             # writes freshness_audit.txt; prints to stdout
    python freshness_audit.py --quiet     # writes file only, no stdout
"""
from __future__ import annotations

import csv
import sys
from datetime import date, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
OUT_PATH = ROOT / "freshness_audit.txt"

TODAY = date.today()

# Number of metadata-prefix rows above the data in each hist CSV.
MACRO_HIST_META_ROWS = 14

# Library names map to the Source string the per-source modules write into the
# unified hist's Source metadata row.
SOURCE_BY_LIBRARY = {
    "fred":      "FRED",
    "oecd":      "OECD",
    "worldbank": "World Bank",
    "imf":       "IMF",
    "dbnomics":  "DB.nomics",
    "ifo":       "ifo",
}


def load_thresholds() -> dict[str, int]:
    """Per-frequency default tolerance in days, from data/freshness_thresholds.csv."""
    path = DATA / "freshness_thresholds.csv"
    out: dict[str, int] = {}
    with path.open(newline="") as f:
        for row in csv.DictReader(f):
            freq = row["frequency"].strip()
            out[freq] = int(row["default_days"])
    return out


def load_overrides() -> dict[tuple[str, str], int]:
    """Walk every per-source library CSV; collect per-row freshness overrides
    keyed by (Source, series_id)."""
    overrides: dict[tuple[str, str], int] = {}
    for lib_name, source in SOURCE_BY_LIBRARY.items():
        path = DATA / f"macro_library_{lib_name}.csv"
        if not path.exists():
            continue
        with path.open(newline="") as f:
            for row in csv.DictReader(f):
                sid = row.get("series_id", "").strip()
                ovr = row.get("freshness_override_days", "").strip()
                if sid and ovr:
                    overrides[(source, sid)] = int(ovr)
    return overrides


def parse_date(s: str | None) -> date | None:
    if not s:
        return None
    try:
        return datetime.strptime(s.strip(), "%Y-%m-%d").date()
    except ValueError:
        return None


def load_macro_hist() -> list[dict]:
    """Read data/macro_economic_hist.csv. Return one dict per data column with
    {col_id, series_id, source, frequency, last_obs}.

    `last_obs` is the date of the last *value-change* in the column — i.e. the
    date when the most recent novel observation arrived.  This is *not* simply
    the last non-null cell, because the unified hist is built on a Friday spine
    with forward-fill: a series whose publisher stopped emitting in Jan 2024
    will still have non-null cells on every Friday since.  Detecting the last
    value-change recovers the actual most-recent publication date.

    Trade-off: a series whose true value happens to be flat for several
    publication periods (e.g. a policy rate held steady) will trip this rule
    and be flagged for review.  That is intentional — better to verify a
    legitimately-flat series than to silently miss a dead one.  Apply a per-row
    `freshness_override_days` override to suppress known-flat-but-fresh series.
    """
    path = DATA / "macro_economic_hist.csv"
    with path.open(newline="") as f:
        rows = list(csv.reader(f))

    if len(rows) <= MACRO_HIST_META_ROWS:
        return []

    labels = [r[0] for r in rows[:MACRO_HIST_META_ROWS]]
    label_idx = {label: i for i, label in enumerate(labels)}

    n_cols = len(rows[0])
    data_rows = rows[MACRO_HIST_META_ROWS:]

    out: list[dict] = []
    for ci in range(1, n_cols):
        # Find last value-change: walk forward through non-null values, track
        # the most recent date at which the value differs from the prior value.
        last_change_date = ""
        prev_val: str | None = None
        for dr in data_rows:
            if ci >= len(dr):
                continue
            cell = dr[ci].strip()
            if cell == "":
                continue
            if prev_val is None or cell != prev_val:
                last_change_date = dr[0].strip()
                prev_val = cell

        out.append({
            "col_id":    rows[label_idx["Column ID"]][ci].strip(),
            "series_id": rows[label_idx["Series ID"]][ci].strip(),
            "source":    rows[label_idx["Source"]][ci].strip(),
            "frequency": rows[label_idx["Frequency"]][ci].strip(),
            "last_obs":  last_change_date,
        })
    return out


def classify(age: int | None, threshold: int) -> str:
    """FRESH if age <= threshold; STALE if 1x-2x threshold; EXPIRED beyond 2x or no obs."""
    if age is None:
        return "EXPIRED"
    if age <= threshold:
        return "FRESH"
    if age <= 2 * threshold:
        return "STALE"
    return "EXPIRED"


def main() -> int:
    quiet = "--quiet" in sys.argv

    thresholds = load_thresholds()
    overrides = load_overrides()
    series = load_macro_hist()

    fresh: list[tuple[dict, int | None, int]] = []
    stale: list[tuple[dict, int | None, int]] = []
    expired: list[tuple[dict, int | None, int]] = []

    for s in series:
        last_obs = parse_date(s["last_obs"])
        age = (TODAY - last_obs).days if last_obs else None

        key = (s["source"], s["series_id"])
        if key in overrides:
            threshold = overrides[key]
            override_used = True
        else:
            threshold = thresholds.get(s["frequency"], 60)
            override_used = False

        status = classify(age, threshold)
        s["_override"] = override_used
        if status == "FRESH":
            fresh.append((s, age, threshold))
        elif status == "STALE":
            stale.append((s, age, threshold))
        else:
            expired.append((s, age, threshold))

    # Build report
    lines: list[str] = []
    lines.append(f"=== Freshness audit @ {TODAY.isoformat()} ===")
    lines.append(
        f"  total series : {len(series)}"
    )
    lines.append(
        f"  FRESH        : {len(fresh)}"
    )
    lines.append(
        f"  STALE        : {len(stale)}"
    )
    lines.append(
        f"  EXPIRED      : {len(expired)}"
    )
    lines.append("")

    for label, bucket in [("EXPIRED", expired), ("STALE", stale)]:
        if not bucket:
            continue
        lines.append(f"--- {label} ({len(bucket)}) ---")
        bucket.sort(key=lambda x: -(x[1] if x[1] is not None else 10**9))
        for s, age, threshold in bucket:
            age_str = f"{age}d" if age is not None else "no_obs"
            t_str = f"{threshold}d" + ("*" if s["_override"] else "")
            lines.append(
                f"  {label:7s}  {s['frequency']:10s}  "
                f"{s['col_id']:32s}  "
                f"src={s['source']:11s}  "
                f"series={s['series_id']:24s}  "
                f"last_obs={s['last_obs'] or '—':10s}  "
                f"age={age_str:8s}  "
                f"tolerance={t_str}"
            )
        lines.append("")

    if stale or expired:
        lines.append("Footer:")
        lines.append("  * = per-row override applied (freshness_override_days column)")
        lines.append(
            "  STALE   = age between 1x and 2x tolerance — investigate; series may have "
            "lost its publisher."
        )
        lines.append(
            "  EXPIRED = age beyond 2x tolerance OR no observations at all — series is "
            "almost certainly dead; remove it from the library or wire it to a fresh source."
        )

    output = "\n".join(lines)
    OUT_PATH.write_text(output + "\n")
    if not quiet:
        print(output)

    return 1 if (stale or expired) else 0


if __name__ == "__main__":
    sys.exit(main())
