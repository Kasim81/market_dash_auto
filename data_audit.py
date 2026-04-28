"""data_audit.py — daily pipeline-health audit (§2.6 of forward_plan.md).

Replaces the v1 freshness_audit.py with a three-section integrated audit:

  Section A — Fetch outcomes
      Scrapes pipeline.log for per-series outcomes the daily fetch already
      observed (HTTP 4xx/5xx errors, "possibly delisted" yfinance warnings,
      "Insufficient Data" results, etc.).  Filters out transient errors that
      were retried successfully so only persistent failures are reported.

  Section B — Static checks
      No-network sanity checks against the registry CSVs and the Phase E
      calculator code: orphan country codes, indicator-id uniqueness,
      calculator-registration consistency, and `_get_col(...)` column
      existence in the unified hist.

  Section C — Value-change staleness
      The v1 freshness audit logic — finds last value-change per series in
      macro_economic_hist.csv and compares against the per-frequency
      tolerance from data/freshness_thresholds.csv (with per-row override
      via the `freshness_override_days` column).  Catches silent freezes
      where forward-fill on the Friday spine would otherwise hide
      stale-publisher series.

Outputs:
    data_audit.txt      — full sorted report, repo-root
    audit_comment.md    — short markdown for posting as a GitHub Issue comment
                          (first line is the one-sentence ISSUE/CLEAN summary)

Exit code: always 0 — this is a warning channel, not a build gate.

Usage:
    python data_audit.py [--quiet]
"""
from __future__ import annotations

import csv
import sys
from datetime import date, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"

OUT_REPORT  = ROOT / "data_audit.txt"
OUT_COMMENT = ROOT / "audit_comment.md"

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


# =============================================================================
# Section C — Value-change staleness (ported from v1 freshness_audit.py)
# =============================================================================

def load_thresholds() -> dict[str, int]:
    """Per-frequency default tolerance in days, from data/freshness_thresholds.csv."""
    out: dict[str, int] = {}
    with (DATA / "freshness_thresholds.csv").open(newline="") as f:
        for row in csv.DictReader(f):
            out[row["frequency"].strip()] = int(row["default_days"])
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
    will still have non-null cells on every Friday since.
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


def classify_age(age: int | None, threshold: int) -> str:
    """FRESH if age <= threshold; STALE if 1x-2x; EXPIRED beyond 2x or no obs."""
    if age is None:
        return "EXPIRED"
    if age <= threshold:
        return "FRESH"
    if age <= 2 * threshold:
        return "STALE"
    return "EXPIRED"


def section_c_staleness() -> dict:
    """Return {fresh: [...], stale: [...], expired: [...]} keyed by status."""
    thresholds = load_thresholds()
    overrides = load_overrides()
    series = load_macro_hist()

    fresh: list = []
    stale: list = []
    expired: list = []

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

        status = classify_age(age, threshold)
        rec = {**s, "age": age, "threshold": threshold, "override": override_used}
        if status == "FRESH":
            fresh.append(rec)
        elif status == "STALE":
            stale.append(rec)
        else:
            expired.append(rec)

    # Sort STALE/EXPIRED by descending age
    stale.sort(key=lambda r: -(r["age"] if r["age"] is not None else 10**9))
    expired.sort(key=lambda r: -(r["age"] if r["age"] is not None else 10**9))
    return {"fresh": fresh, "stale": stale, "expired": expired}


# =============================================================================
# Section A — Fetch outcomes (pipeline.log scrape)
# =============================================================================

def section_a_fetch_outcomes() -> dict:
    """Stub for step 1b — returns empty buckets for now."""
    return {"http_errors": [], "delisted": [], "insufficient_data": []}


# =============================================================================
# Section B — Static checks
# =============================================================================

def section_b_static_checks() -> dict:
    """Stub for step 1c — returns empty buckets for now."""
    return {"orphan_country_codes": [], "duplicate_indicator_ids": [],
            "missing_calculators": [], "missing_columns": []}


# =============================================================================
# Report rendering
# =============================================================================

def render_report(sections: dict) -> str:
    """Build the plaintext data_audit.txt report."""
    lines: list[str] = []
    lines.append(f"=== Data audit @ {TODAY.isoformat()} ===")
    lines.append("")

    # Section A
    a = sections["a"]
    n_a = sum(len(v) for v in a.values())
    lines.append(f"--- Section A: Fetch outcomes ({n_a} issues) ---")
    if n_a == 0:
        lines.append("  (none)")
    else:
        for label, items in a.items():
            for item in items:
                lines.append(f"  {label.upper():18s}  {item}")
    lines.append("")

    # Section B
    b = sections["b"]
    n_b = sum(len(v) for v in b.values())
    lines.append(f"--- Section B: Static checks ({n_b} issues) ---")
    if n_b == 0:
        lines.append("  (none)")
    else:
        for label, items in b.items():
            for item in items:
                lines.append(f"  {label.upper():26s}  {item}")
    lines.append("")

    # Section C
    c = sections["c"]
    lines.append(
        f"--- Section C: Value-change staleness "
        f"(FRESH {len(c['fresh'])}  STALE {len(c['stale'])}  EXPIRED {len(c['expired'])}) ---"
    )
    for label, bucket in [("EXPIRED", c["expired"]), ("STALE", c["stale"])]:
        if not bucket:
            continue
        lines.append(f"  {label} ({len(bucket)}):")
        for r in bucket:
            age_str = f"{r['age']}d" if r["age"] is not None else "no_obs"
            t_str = f"{r['threshold']}d" + ("*" if r["override"] else "")
            lines.append(
                f"    {r['frequency']:10s}  {r['col_id']:32s}  "
                f"src={r['source']:11s}  series={r['series_id']:24s}  "
                f"last_obs={r['last_obs'] or '—':10s}  "
                f"age={age_str:8s}  tolerance={t_str}"
            )
    lines.append("")
    lines.append("Footer:")
    lines.append("  * = per-row override applied (freshness_override_days column)")
    lines.append("  STALE   = age between 1x and 2x tolerance — investigate")
    lines.append(
        "  EXPIRED = age beyond 2x tolerance OR no observations — series almost certainly dead"
    )

    return "\n".join(lines) + "\n"


def render_comment(sections: dict) -> str:
    """Build audit_comment.md — the GitHub Issue comment body."""
    a = sections["a"]; b = sections["b"]; c = sections["c"]
    n_a = sum(len(v) for v in a.values())
    n_b = sum(len(v) for v in b.values())
    n_stale = len(c["stale"]) + len(c["expired"])
    total = n_a + n_b + n_stale

    lines: list[str] = []
    if total == 0:
        lines.append(f"## Daily audit — {TODAY.isoformat()} — **ALL CLEAN**")
    else:
        parts: list[str] = []
        if n_a:
            parts.append(f"{n_a} fetch error{'s' if n_a != 1 else ''}")
        if n_stale:
            parts.append(f"{n_stale} stale serie{'s' if n_stale != 1 else ''}")
        if n_b:
            parts.append(f"{n_b} static-check failure{'s' if n_b != 1 else ''}")
        lines.append(
            f"## Daily audit — {TODAY.isoformat()} — **{total} ISSUE{'S' if total != 1 else ''}** "
            f"({', '.join(parts)})"
        )

    lines.append("")
    lines.append(f"_Run: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}_")
    lines.append("")
    lines.append("Full report attached as `data_audit.txt` in today's commit.")
    lines.append("")

    # Compact section summaries with collapsible detail
    if n_a:
        lines.append("<details><summary>Fetch errors</summary>\n")
        for label, items in a.items():
            if items:
                lines.append(f"\n**{label}** ({len(items)}):")
                for item in items[:50]:  # cap at 50 to keep comment readable
                    lines.append(f"- `{item}`")
                if len(items) > 50:
                    lines.append(f"- _… {len(items) - 50} more in `data_audit.txt`_")
        lines.append("\n</details>\n")

    if n_stale:
        lines.append("<details><summary>Stale series</summary>\n")
        for label, bucket in [("EXPIRED", c["expired"]), ("STALE", c["stale"])]:
            if not bucket:
                continue
            lines.append(f"\n**{label}** ({len(bucket)}):\n")
            lines.append("| Series | Source | Frequency | Last obs | Age | Tolerance |")
            lines.append("|---|---|---|---|---|---|")
            for r in bucket[:30]:
                age_str = f"{r['age']}d" if r["age"] is not None else "no_obs"
                t_str = f"{r['threshold']}d" + ("\\*" if r["override"] else "")
                lines.append(
                    f"| `{r['col_id']}` | {r['source']} | {r['frequency']} | "
                    f"{r['last_obs'] or '—'} | {age_str} | {t_str} |"
                )
            if len(bucket) > 30:
                lines.append(f"| _… {len(bucket) - 30} more in `data_audit.txt`_ |  |  |  |  |  |")
        lines.append("\n</details>\n")

    if n_b:
        lines.append("<details><summary>Static-check failures</summary>\n")
        for label, items in b.items():
            if items:
                lines.append(f"\n**{label}** ({len(items)}):")
                for item in items[:30]:
                    lines.append(f"- {item}")
                if len(items) > 30:
                    lines.append(f"- _… {len(items) - 30} more in `data_audit.txt`_")
        lines.append("\n</details>\n")

    return "\n".join(lines) + "\n"


def main() -> int:
    quiet = "--quiet" in sys.argv

    sections = {
        "a": section_a_fetch_outcomes(),
        "b": section_b_static_checks(),
        "c": section_c_staleness(),
    }

    OUT_REPORT.write_text(render_report(sections))
    OUT_COMMENT.write_text(render_comment(sections))

    if not quiet:
        print(OUT_REPORT.read_text())

    return 0  # warning channel — never fail the build


if __name__ == "__main__":
    sys.exit(main())
