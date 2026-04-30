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
    """Scrape pipeline.log for per-series fetch failures.

    Patterns the daily pipeline emits today:

      yfinance:
        $<TICKER>: possibly delisted; no timezone found
        ^<TICKER>: Period 'max' is invalid, must be one of: 1d, 5d
        HTTP Error 404: ... Quote not found for symbol: <TICKER>

      FRED:
        [FRED] HTTP <code> on <X> — skipping             (final failure)
        [FRED] HTTP <code> on FRED/<X> — backoff ...     (retry — IGNORED)
      The backoff retry lines naturally filter out because we only match the
      `— skipping` suffix.  A series whose first 4 attempts 500'd but whose 5th
      succeeded never emits a `skipping` line, so it doesn't appear here.

      ECB / fallbacks (informational; included for visibility):
        [ECB] EU_I1 spread unavailable — ...

    Cross-check: yfinance "delisted" tickers are cross-referenced against the
    latest non-empty observation in market_data_comp_hist.csv.  If a ticker
    has data in the latest row, the warning was transient and the ticker is
    omitted from the audit (false positive).  If the ticker has no data, it's
    a real concern and it's reported.

    Returns dict with three sorted lists:
      yfinance_dead, fred_persistent_errors, other_warnings
    """
    import re

    log_path = ROOT / "pipeline.log"
    if not log_path.exists():
        return {"yfinance_dead": [], "fred_persistent_errors": [], "other_warnings": []}

    text = log_path.read_text()

    # ---------- yfinance ticker failures ----------
    yf_suspects: set[str] = set()
    for m in re.finditer(r'\$([\^A-Z][A-Z0-9.\-^]*[A-Z0-9]):\s*possibly delisted', text):
        yf_suspects.add(m.group(1))
    for m in re.finditer(
        r'Quote not found for symbol:\s*([\^A-Z][A-Z0-9.\-^]*[A-Z0-9])', text
    ):
        yf_suspects.add(m.group(1))
    for m in re.finditer(
        r'^([\^A-Z][A-Z0-9.\-^]+):\s*Period \'max\' is invalid', text, re.M
    ):
        yf_suspects.add(m.group(1))

    # Cross-check against latest comp_hist row to filter transient warnings.
    yfinance_dead = sorted(_yfinance_truly_dead(yf_suspects))

    # ---------- FRED final failures ----------
    fred_final: set[tuple[str, str]] = set()
    # Match: "[FRED] HTTP 400 on FRED/SERIES — skipping"  OR
    #        "[FRED] HTTP 400 on SERIES — skipping"
    for m in re.finditer(
        r'\[FRED\]\s+HTTP\s+(\d{3})\s+on\s+(?:FRED/)?([A-Z0-9_/.\-]+)\s+—\s+skipping',
        text,
    ):
        fred_final.add((m.group(1), m.group(2)))
    fred_persistent_errors = sorted(f"HTTP {c} on {s}" for c, s in fred_final)

    # ---------- Other source warnings (informational) ----------
    other_warnings: list[str] = []
    # ECB / DBnomics / OECD per-source notable lines
    for pat in [
        r'\[ECB\][^\n]*spread unavailable[^\n]*',
        r'\[ECB\][^\n]*0 (monthly )?obs[^\n]*',
        r'\[OECD\][^\n]*HTTP\s+\d{3}[^\n]*',
        r'\[DBnomics\][^\n]*HTTP\s+\d{3}[^\n]*',
        r'\[ifo\][^\n]*workbook[^\n]*(failed|empty)[^\n]*',
    ]:
        for m in re.finditer(pat, text):
            other_warnings.append(m.group(0).strip())
    # Dedupe while preserving order
    seen: set[str] = set()
    other_warnings = [x for x in other_warnings if not (x in seen or seen.add(x))]

    return {
        "yfinance_dead": yfinance_dead,
        "fred_persistent_errors": fred_persistent_errors,
        "other_warnings": other_warnings,
    }


def _yfinance_truly_dead(suspects: set[str]) -> set[str]:
    """Cross-check suspect yfinance tickers against market_data_comp_hist.csv.

    Returns the subset of suspects that have NO data in the latest non-empty
    observation row of the comp hist — i.e. the warnings are real, not
    transient.  Tickers that appear in the suspect set but DO have recent
    data are omitted (probably fetched successfully on a retry).
    """
    comp_path = DATA / "market_data_comp_hist.csv"
    if not comp_path.exists():
        return suspects  # Can't cross-check; report all

    with comp_path.open(newline="") as f:
        rows = list(csv.reader(f))

    if len(rows) < 12:
        return suspects

    # market_data_comp_hist has 11 metadata-prefix rows + 1 header row + data.
    # Row 0 col 0 is "Ticker ID"; row 0 cols 1+ are tickers.
    header = rows[0]
    tickers = [t.strip() for t in header[1:]]
    ticker_to_idx = {t: i + 1 for i, t in enumerate(tickers)}

    # Last data row
    last_row = rows[-1]
    truly_dead: set[str] = set()
    for sus in suspects:
        idx = ticker_to_idx.get(sus)
        if idx is None or idx >= len(last_row):
            # Ticker isn't even in the comp hist columns → genuinely missing
            truly_dead.add(sus)
            continue
        val = last_row[idx].strip()
        if val == "":
            truly_dead.add(sus)
    return truly_dead


# =============================================================================
# Section B — Static checks (no network)
# =============================================================================

def section_b_static_checks() -> dict:
    """Local sanity checks against the registry CSVs and the Phase E calculator
    code.  Each check returns a list of human-readable issue strings.

    Checks performed:
      - Orphan country codes: every country code referenced in any per-source
        library exists in macro_library_countries.csv.
      - Duplicate indicator ids: every `id` in macro_indicator_library.csv
        appears exactly once.
      - Missing calculators: every indicator id is registered in one of the
        `_*_CALCULATORS` dicts in compute_macro_market.py.
      - Missing _get_col columns: every `_get_col(mu, "X")` literal in the
        calculator code resolves to a column that exists in
        macro_economic_hist.csv.
    """
    return {
        "orphan_country_codes":   _check_orphan_country_codes(),
        "duplicate_indicator_ids": _check_duplicate_indicator_ids(),
        "missing_calculators":    _check_missing_calculators(),
        "missing_columns":        _check_missing_get_col_columns(),
        "registry_drift":         _check_registry_drift(),
    }


def _check_orphan_country_codes() -> list[str]:
    """Every country code referenced in fred / oecd / dbnomics / ifo libraries
    must exist in macro_library_countries.csv."""
    countries_path = DATA / "macro_library_countries.csv"
    if not countries_path.exists():
        return ["macro_library_countries.csv missing — cannot check orphans"]

    with countries_path.open(newline="") as f:
        valid = {row["code"].strip() for row in csv.DictReader(f) if row.get("code")}

    issues: list[str] = []
    for lib_name in ("fred", "dbnomics", "ifo"):
        path = DATA / f"macro_library_{lib_name}.csv"
        if not path.exists():
            continue
        with path.open(newline="") as f:
            for i, row in enumerate(csv.DictReader(f), start=2):  # +2 = header is row 1
                code = (row.get("country") or "").strip()
                if code and code not in valid:
                    issues.append(
                        f"{lib_name}.csv row {i}: country={code!r} not in registry "
                        f"(series_id={row.get('series_id', '?').strip()})"
                    )

    # OECD has the multi-country fan-out via oecd_countries column (e.g. "AUS+CAN+...")
    oecd_path = DATA / "macro_library_oecd.csv"
    if oecd_path.exists():
        with oecd_path.open(newline="") as f:
            for i, row in enumerate(csv.DictReader(f), start=2):
                codes_str = (row.get("oecd_countries") or "").strip()
                if not codes_str:
                    continue
                for code in codes_str.split("+"):
                    code = code.strip()
                    if code and code not in valid:
                        issues.append(
                            f"oecd.csv row {i}: country={code!r} in oecd_countries "
                            f"not in registry (series_id={row.get('series_id', '?').strip()})"
                        )
    return issues


def _check_duplicate_indicator_ids() -> list[str]:
    """Every `id` in macro_indicator_library.csv must be unique."""
    path = DATA / "macro_indicator_library.csv"
    if not path.exists():
        return ["macro_indicator_library.csv missing"]

    seen: dict[str, int] = {}
    issues: list[str] = []
    with path.open(newline="") as f:
        for i, row in enumerate(csv.DictReader(f), start=2):
            ind_id = (row.get("id") or "").strip()
            if not ind_id:
                continue
            if ind_id in seen:
                issues.append(
                    f"duplicate indicator id {ind_id!r} at rows {seen[ind_id]} and {i}"
                )
            else:
                seen[ind_id] = i
    return issues


def _check_missing_calculators() -> list[str]:
    """Every indicator id in macro_indicator_library.csv must be registered as
    a calculator in compute_macro_market.py."""
    lib_path = DATA / "macro_indicator_library.csv"
    code_path = ROOT / "compute_macro_market.py"
    if not (lib_path.exists() and code_path.exists()):
        return []

    with lib_path.open(newline="") as f:
        ind_ids = {
            (row.get("id") or "").strip()
            for row in csv.DictReader(f)
            if (row.get("id") or "").strip()
        }

    code = code_path.read_text()
    # Look for `"<ID>": _calc_...` inside *_CALCULATORS dicts.  Indicator IDs
    # are mixed-case (e.g. EU_Cr1, US_Cr2) so we allow [A-Za-z0-9_].
    import re
    registered = set(re.findall(r'"([A-Za-z][A-Za-z0-9_]*)"\s*:\s*_calc_', code))

    missing = sorted(ind_ids - registered)
    return [f"indicator {ind_id!r} declared in CSV but no calculator dispatch found"
            for ind_id in missing]


def _check_missing_get_col_columns() -> list[str]:
    """Every `_get_col(mu, "X")` / `_get_col(mu_or_dbn, "X")` literal in
    compute_macro_market.py must resolve to a column id that exists in
    macro_economic_hist.csv."""
    code_path = ROOT / "compute_macro_market.py"
    hist_path = DATA / "macro_economic_hist.csv"
    if not (code_path.exists() and hist_path.exists()):
        return []

    code = code_path.read_text()
    import re
    referenced = set(re.findall(r'_get_col\(\s*\w+\s*,\s*"([A-Z][A-Z0-9_]*)"', code))

    # Read column ids from row 1 of the unified hist (Column ID metadata row)
    with hist_path.open(newline="") as f:
        first = next(csv.reader(f))
    hist_cols = {c.strip() for c in first[1:]}

    missing = sorted(referenced - hist_cols)
    return [
        f"_get_col(...,{col!r}) referenced in compute_macro_market.py but column "
        f"absent from macro_economic_hist.csv"
        for col in missing
    ]


def _check_registry_drift() -> list[str]:
    """Every column present in a hist CSV must trace back to a row in the
    matching source-of-truth library CSV. Reports orphans across all three
    library_sync pairs (comp, macro_economic, macro_market) so the operator
    can run `python library_sync.py --confirm` to archive + prune.

    Reuses library_sync's expected/present helpers so the column-derivation
    rules (PR/TR for comp, OECD/WB/IMF country fan-out for macro economic,
    indicator suffixes for macro market) live in one place.
    """
    import library_sync as ls

    pairs = [
        ("market_data_comp_hist.csv", ls.COMP_HIST,       ls._comp_expected,       ls._comp_present),
        ("macro_economic_hist.csv",   ls.MACRO_ECON_HIST, ls._macro_econ_expected, ls._macro_econ_present),
        ("macro_market_hist.csv",     ls.MACRO_MKT_HIST,  ls._macro_mkt_expected,  ls._macro_mkt_present),
    ]

    issues: list[str] = []
    for name, hist_path, expected_fn, present_fn in pairs:
        if not hist_path.exists():
            continue
        with hist_path.open(newline="") as f:
            rows = list(csv.reader(f))
        expected = expected_fn()
        present = present_fn(rows)
        for col_id in sorted(present - expected):
            issues.append(
                f"hist column {col_id!r} present in {name} but no matching "
                f"row in source-of-truth library "
                f"(run: python library_sync.py --confirm)"
            )
    return issues


# =============================================================================
# Section D: History-preservation audit (forward_plan §3.1.1)
# =============================================================================
# Each *_hist.csv has a sister *_hist_x.csv that holds rows displaced by
# source-side floor advancement. Report per-file row counts (live + sister =
# total union), date ranges, and flag any anomalies (sister rows duplicated in
# live, sister missing for an ICE-BofA-bearing file, etc.).

def _read_hist_dates(path: Path, skiprows: int) -> list[str]:
    """Return the list of Date strings in the data section of a hist file."""
    if not path.exists():
        return []
    with path.open(newline="") as f:
        rows = list(csv.reader(f))
    if len(rows) <= skiprows:
        return []
    header = rows[skiprows]
    try:
        date_idx = header.index("Date")
    except ValueError:
        return []
    return [r[date_idx] for r in rows[skiprows + 1:] if len(r) > date_idx and r[date_idx]]


def section_d_history_preservation() -> dict:
    """Report live + sister row counts and date ranges per *_hist.csv pair."""
    pairs = [
        ("market_data_comp_hist.csv",  DATA / "market_data_comp_hist.csv",  11, True),
        ("macro_economic_hist.csv",    DATA / "macro_economic_hist.csv",    14, True),
        ("macro_market_hist.csv",      DATA / "macro_market_hist.csv",       0, False),
    ]
    issues: list[str] = []
    rows: list[dict] = []

    for name, live_path, skip, has_ice_bofa in pairs:
        sister_path = live_path.with_name(live_path.name.replace("_hist.csv", "_hist_x.csv"))

        live_dates = _read_hist_dates(live_path, skip)
        sister_dates = _read_hist_dates(sister_path, skip) if sister_path.exists() else []

        union_dates = set(live_dates) | set(sister_dates)
        overlap = set(live_dates) & set(sister_dates)

        rec = {
            "name": name,
            "live_rows": len(live_dates),
            "sister_exists": sister_path.exists(),
            "sister_rows": len(sister_dates),
            "union_rows": len(union_dates),
            "overlap_rows": len(overlap),
            "live_earliest": min(live_dates) if live_dates else "—",
            "live_latest": max(live_dates) if live_dates else "—",
            "sister_earliest": min(sister_dates) if sister_dates else "—",
            "sister_latest": max(sister_dates) if sister_dates else "—",
        }
        rows.append(rec)

        if has_ice_bofa and not sister_path.exists():
            issues.append(
                f"{name}: ICE-BofA-bearing file has no sister *_hist_x.csv — "
                "history-preservation safeguard not yet active for this file"
            )
        # Sister-row-count regression check: once the sister contains rows,
        # it must never get smaller (it is append-only). Anomaly handled
        # cross-run via per-file row-count history; here we only catch a
        # logical impossibility — sister has fewer rows than live AND every
        # sister date is already in live (ie. sister adds no extension).
        # That state means sister was rewritten as a strict subset of live.
        if (sister_path.exists() and sister_dates and
                len(sister_dates) < len(live_dates) and
                set(sister_dates).issubset(set(live_dates))):
            issues.append(
                f"{name}: sister rows are a strict subset of live "
                f"({len(sister_dates)} ⊂ {len(live_dates)}) — sister "
                "may have been rewritten incorrectly"
            )

    return {"issues": issues, "rows": rows}


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

    # Section D — History preservation (forward_plan §3.1.1)
    d = sections.get("d", {"issues": [], "rows": []})
    n_d = len(d["issues"])
    lines.append(f"--- Section D: History preservation ({n_d} issues) ---")
    for r in d["rows"]:
        sister_part = (
            f"sister={r['sister_rows']:5d} rows ({r['sister_earliest']}→{r['sister_latest']})"
            if r["sister_exists"]
            else "sister=(none)"
        )
        lines.append(
            f"  {r['name']:32s}  live={r['live_rows']:5d} rows "
            f"({r['live_earliest']}→{r['live_latest']})  "
            f"{sister_part}  union={r['union_rows']:5d}"
        )
    if n_d:
        lines.append("")
        for issue in d["issues"]:
            lines.append(f"  ALERT  {issue}")
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
    d = sections.get("d", {"issues": [], "rows": []})
    n_a = sum(len(v) for v in a.values())
    n_b = sum(len(v) for v in b.values())
    n_stale = len(c["stale"]) + len(c["expired"])
    n_d = len(d["issues"])
    total = n_a + n_b + n_stale + n_d

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
        if n_d:
            parts.append(f"{n_d} history-preservation issue{'s' if n_d != 1 else ''}")
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

    # Section D — History preservation summary (forward_plan §3.1.1)
    # Always emit the per-file row-count summary for visibility; emit ALERT
    # bullets only when issues exist.
    if d["rows"]:
        lines.append("<details><summary>History preservation</summary>\n")
        lines.append("\n| File | Live rows | Sister rows | Union | Live range | Sister range |")
        lines.append("|---|---|---|---|---|---|")
        for r in d["rows"]:
            sister_rows = f"{r['sister_rows']:,}" if r["sister_exists"] else "—"
            sister_range = (f"{r['sister_earliest']} → {r['sister_latest']}"
                            if r["sister_exists"] else "—")
            lines.append(
                f"| `{r['name']}` | {r['live_rows']:,} | {sister_rows} | "
                f"{r['union_rows']:,} | {r['live_earliest']} → {r['live_latest']} | "
                f"{sister_range} |"
            )
        if n_d:
            lines.append("\n**ALERTS** ({}):".format(n_d))
            for issue in d["issues"]:
                lines.append(f"- {issue}")
        lines.append("\n</details>\n")

    return "\n".join(lines) + "\n"


def main() -> int:
    quiet = "--quiet" in sys.argv

    sections = {
        "a": section_a_fetch_outcomes(),
        "b": section_b_static_checks(),
        "c": section_c_staleness(),
        "d": section_d_history_preservation(),
    }

    OUT_REPORT.write_text(render_report(sections))
    OUT_COMMENT.write_text(render_comment(sections))

    if not quiet:
        print(OUT_REPORT.read_text())

    return 0  # warning channel — never fail the build


if __name__ == "__main__":
    sys.exit(main())
