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

(Sections D and E — history preservation and value plausibility — were added
later; Section F below is the §2.C C8 CRITICAL gate.)

Outputs:
    data_audit.txt      — full sorted report, repo-root
    audit_comment.md    — short markdown for posting as a GitHub Issue comment
                          (first line is the one-sentence ISSUE/CLEAN summary)
    data_audit_critical.flag — written ONLY when Section F fired; the
                          update_data.yml commit step reads it to skip the
                          data-file commit (removed again on clean runs)

Exit code: 0 for everything in Sections A–E (warning channel, not a build
gate) — except the deliberately-narrow Section F CRITICAL class (§2.C C8:
protected-tab output empty/all-NaN; hist CSV losing >10% rows/columns vs
HEAD), which exits 2 so the daily workflow withholds the data commit.

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

def _split_meta_and_data(rows: list[list[str]]) -> tuple[list[list[str]], list[list[str]]]:
    """Split raw CSV rows of a macro hist file into (metadata rows, data rows),
    locating the header row (first cell == 'Date') by inspection rather than a
    hardcoded count — the metadata block grew from 14 to 15 rows on 2026-07-08
    ('Last Observation') and both generations must parse. The header row itself
    is dropped. Returns ([], []) if no header row is found."""
    for i, r in enumerate(rows[:40]):
        if r and r[0].strip() == "Date":
            return rows[:i], rows[i + 1:]
    return [], []

# Library names map to the Source string the per-source modules write into the
# unified hist's Source metadata row. Derived from the shared identity table
# (sources.SOURCE_REGISTRY, §2.C C2) — one registration point for new sources.
from sources import LABEL_BY_STEM as SOURCE_BY_LIBRARY  # noqa: E402



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


def load_anchors() -> dict[tuple[str, str], dict]:
    """Walk every per-source library CSV; collect rows marked as historical
    anchors. Returns a dict keyed by (Source, series_id) with values:
        {"is_anchor": True, "next_expected_release": date | None}

    A "historical anchor" is a row whose underlying dataset is published on
    a multi-year cadence (e.g. JST Macrohistory R6 shipped 2021 covering data
    through 2020; the JST team's next release is on their own schedule).
    Marking such a row with `is_historical_anchor=true` in the library CSV
    opts it out of the standard frequency-based staleness check — the data's
    "age" is intrinsic, not a pipeline bug.

    `next_expected_release` (YYYY-MM-DD) gates whether we should be alerting
    on a missing newer release. If today >= that date AND the row hasn't
    refreshed since the previous release, audit reports OVERDUE so the
    operator goes and checks for a new version upstream.
    """
    anchors: dict[tuple[str, str], dict] = {}
    for lib_name, source in SOURCE_BY_LIBRARY.items():
        path = DATA / f"macro_library_{lib_name}.csv"
        if not path.exists():
            continue
        with path.open(newline="") as f:
            for row in csv.DictReader(f):
                sid = row.get("series_id", "").strip()
                flag = row.get("is_historical_anchor", "").strip().lower()
                if not sid or flag not in ("true", "1", "yes"):
                    continue
                ner_raw = row.get("next_expected_release", "").strip()
                ner = parse_date(ner_raw) if ner_raw else None
                anchors[(source, sid)] = {"is_anchor": True, "next_expected_release": ner}
    return anchors


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

    `last_obs` (forward_plan §2.A A15): preferred source is the
    **"Last Observation" metadata row** the bounded-fill writer records —
    the exact date of the column's last *real raw observation*, known at
    write time. This is ground truth: value-change archaeology cannot
    distinguish a held policy rate (real daily observations at an unchanged
    value) from a dead series, which is the false-positive class that forced
    the wide A11 event-driven-rate overrides.

    **Fallback — value-change archaeology** — when the metadata row is
    absent (a pre-2026-07-08 file generation) or the cell is blank (a column
    missing from today's provenance, e.g. an intermittent ifo fetch failure
    where the sister still carries history): the date of the last value
    change in the column. Not simply the last non-null cell, because the
    spine carries (bounded) forward-fill.
    """
    path = DATA / "macro_economic_hist.csv"
    with path.open(newline="") as f:
        rows = list(csv.reader(f))

    meta_rows, data_rows = _split_meta_and_data(rows)
    if not meta_rows or not data_rows:
        return []

    labels = [r[0] for r in meta_rows]
    label_idx = {label: i for i, label in enumerate(labels)}
    lo_idx = label_idx.get("Last Observation")

    n_cols = len(rows[0])

    out: list[dict] = []
    for ci in range(1, n_cols):
        last_obs = ""
        if lo_idx is not None and ci < len(meta_rows[lo_idx]):
            last_obs = meta_rows[lo_idx][ci].strip()
        if not last_obs:
            # Archaeology fallback: date of the last value change.
            prev_val: str | None = None
            for dr in data_rows:
                if ci >= len(dr):
                    continue
                cell = dr[ci].strip()
                if cell == "":
                    continue
                if prev_val is None or cell != prev_val:
                    last_obs = dr[0].strip()
                    prev_val = cell

        out.append({
            "col_id":    meta_rows[label_idx["Column ID"]][ci].strip(),
            "series_id": meta_rows[label_idx["Series ID"]][ci].strip(),
            "source":    meta_rows[label_idx["Source"]][ci].strip(),
            "frequency": meta_rows[label_idx["Frequency"]][ci].strip(),
            "last_obs":  last_obs,
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
    """Return {fresh, stale, expired, anchors_active, anchors_overdue} keyed
    by status.

    Buckets:
      - FRESH/STALE/EXPIRED — standard frequency-based check on the row's age
        vs the per-frequency threshold (or per-row `freshness_override_days`).
      - ANCHORS_ACTIVE — row flagged `is_historical_anchor=true`, no
        `next_expected_release` set OR today < next_expected_release.
        Informational only; the data's age is intrinsic to the dataset.
      - ANCHORS_OVERDUE — anchor row whose `next_expected_release` date has
        passed. Means we should be checking upstream for a newer release
        (e.g. JST R7 if R6 -> R7 should have shipped by the listed date).
    """
    thresholds = load_thresholds()
    overrides = load_overrides()
    anchors = load_anchors()
    series = load_macro_hist()

    fresh: list = []
    stale: list = []
    expired: list = []
    anchors_active: list = []
    anchors_overdue: list = []

    for s in series:
        last_obs = parse_date(s["last_obs"])
        age = (TODAY - last_obs).days if last_obs else None
        key = (s["source"], s["series_id"])

        # Historical-anchor path: skip the frequency-based staleness check
        # entirely; the data's age is intrinsic to the dataset's release
        # cadence. Surface separately so the operator sees them but the
        # standard "stale" bucket isn't polluted with non-bugs.
        if key in anchors:
            ner = anchors[key]["next_expected_release"]
            rec = {**s, "age": age, "next_expected_release": ner.isoformat() if ner else ""}
            if ner is not None and TODAY >= ner:
                anchors_overdue.append(rec)
            else:
                anchors_active.append(rec)
            continue

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

    # Sort STALE/EXPIRED by descending age; anchors by next_expected_release.
    stale.sort(key=lambda r: -(r["age"] if r["age"] is not None else 10**9))
    expired.sort(key=lambda r: -(r["age"] if r["age"] is not None else 10**9))
    anchors_overdue.sort(key=lambda r: r.get("next_expected_release", ""))
    anchors_active.sort(key=lambda r: r.get("next_expected_release", "9999"))
    return {
        "fresh": fresh,
        "stale": stale,
        "expired": expired,
        "anchors_active": anchors_active,
        "anchors_overdue": anchors_overdue,
    }


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

      Declared-primary demotions (§2.C C1, 2026-07-09 — emitted by the
      tier-aware merge in fetch_macro_economic._log_demotion on both the
      snapshot and history paths):
        [FALLBACK] EA_HICP: declared primary estat/... (tier 0) demoted —
        stale 190d (...); serving ecb/... (tier 2, Monthly, last 2026-06-01)
      Every such line is surfaced verbatim: a frozen primary is a reported
      audit issue on day one, not a silent six-month freeze.

    Cross-check: yfinance "delisted" tickers are cross-referenced against the
    latest non-empty observation in market_data_comp_hist.csv.  If a ticker
    has data in the latest row, the warning was transient and the ticker is
    omitted from the audit (false positive).  If the ticker has no data, it's
    a real concern and it's reported.

    Returns dict with four sorted/ordered lists:
      yfinance_dead, fred_persistent_errors, fallback_demotions, other_warnings
    """
    import re

    log_path = ROOT / "pipeline.log"
    if not log_path.exists():
        return {"yfinance_dead": [], "fred_persistent_errors": [],
                "fallback_demotions": [], "other_warnings": []}

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

    # ---------- Declared-primary demotions (§2.C C1) ----------
    fallback_demotions: list[str] = []
    for m in re.finditer(r'\[FALLBACK\][^\n]*', text):
        line = m.group(0).strip()
        if line not in fallback_demotions:
            fallback_demotions.append(line)

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
        "fallback_demotions": fallback_demotions,
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
        "missing_explorer_indicators": _check_missing_explorer_indicators(),
        "registry_drift":         _check_registry_drift(),
        "unadjusted_splits":      _check_unadjusted_splits(),
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
    for lib_name in (
        "fred", "dbnomics", "ifo", "boe", "ecb", "boj", "estat", "nasdaqdl",
        "lbma", "boc", "statcan", "ons", "bundesbank", "abs", "istat", "bls",
        "insee", "bdf", "alpha_vantage", "shiller", "french", "jst",
    ):
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


def _check_missing_explorer_indicators() -> list[str]:
    """Every indicator id in macro_indicator_library.csv must have a matching
    `<id>_raw` column in macro_market_hist.csv (the explorer's `present_ids`
    discovery scans column-name suffixes, so a missing `_raw` column means the
    indicator silently never appears in the explorer or `macro_market.csv`).

    This is the gap forward_plan §3.11 documents: an indicator can be registered
    in the library + a calculator dispatch + REGIME_RULES, but if a daily run
    hasn't happened since the merge — or the calculator silently returned an
    empty Series for the full HIST_START → today window — the hist won't carry
    the column and the explorer skips the indicator without warning. The
    remediation in either case is to trigger an `update_data` workflow_dispatch.
    """
    lib_path = DATA / "macro_indicator_library.csv"
    hist_path = DATA / "macro_market_hist.csv"
    if not (lib_path.exists() and hist_path.exists()):
        return []

    with lib_path.open(newline="") as f:
        ind_ids = [
            (row.get("id") or "").strip()
            for row in csv.DictReader(f)
            if (row.get("id") or "").strip()
        ]

    with hist_path.open(newline="") as f:
        hist_cols = set(next(csv.reader(f)))

    missing = [
        ind for ind in ind_ids
        if f"{ind}_raw" not in hist_cols and ind not in KNOWN_MISSING_INDICATORS
    ]
    return [
        f"indicator {ind!r} present in library but no `{ind}_raw` column in "
        f"macro_market_hist.csv (trigger update_data run, or check calculator "
        f"returned non-empty Series)"
        for ind in missing
    ]


def _check_missing_get_col_columns() -> list[str]:
    """Every `_get_col(mu, "X")` / `_get_col(mu_or_dbn, "X")` literal in
    compute_macro_market.py must resolve to a column id that exists in
    macro_economic_hist.csv.

    Exception: columns in KNOWN_MISSING_COLUMNS are documented permanent
    gaps (per forward_plan.md §1 Known Data Gaps) and have a deliberate
    calculator reference so they wire automatically the day a source
    appears. Suppressing them stops chronic false-positive churn while
    keeping any *new* drift visible.
    """
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

    missing = sorted(referenced - hist_cols - KNOWN_MISSING_COLUMNS)
    return [
        f"_get_col(...,{col!r}) referenced in compute_macro_market.py but column "
        f"absent from macro_economic_hist.csv"
        for col in missing
    ]


# Columns referenced by compute_macro_market.py that are accepted gaps —
# the calculator is left in place so the indicator wires automatically the
# day a source becomes available, but the static-check alert is suppressed
# in the meantime. Every entry here must trace back to forward_plan §1
# Known Data Gaps. Keep this list short.
KNOWN_MISSING_COLUMNS: frozenset = frozenset({
    # No free source for a direct CN 10Y govt yield. Partial proxy in
    # place via the CBON ETF in index_library.csv. Calculator
    # _calc_AS_CN_R1 references CHN_GOVT_10Y so it self-wires the day
    # a source lands. See forward_plan.md §1 Known Data Gaps.
    "CHN_GOVT_10Y",
})


# Indicator ids registered in macro_indicator_library.csv whose `<id>_raw`
# column is permanently absent from macro_market_hist.csv because the
# underlying input has no free source. The calculator + library row are
# left in place so the indicator self-wires the day a source becomes
# available, but the explorer pre-flight alert is suppressed in the
# meantime. Every entry traces back to forward_plan.md §1 Known Data Gaps.
KNOWN_MISSING_INDICATORS: frozenset = frozenset({
    # Euro IG corporate effective yield: FRED BAMLEC0A0RMEY 400s on every
    # call; ECB SDW has no free aggregate Euro IG yield; iBoxx paywalled.
    # Partial proxy via IEAC.L ETF in index_library.csv.
    "EU_Cr1",
    # China–US 10Y rate spread: depends on CHN_GOVT_10Y (no free source —
    # see KNOWN_MISSING_COLUMNS above).
    "AS_CN_R1",
    # Germany ZEW Economic Sentiment: ZEW Mannheim licences the archive;
    # no free API. Substituted by DE_IFO1 + DEU_BUS_CONF.
    "DE_ZEW1",
    # Japan au Jibun Bank Manufacturing PMI: S&P Global proprietary, no
    # free monthly feed. Functionally substituted by JP_TANKAN1.
    "JP_PMI1",
    # Caixin China Manufacturing PMI: S&P Global proprietary. Substituted
    # by CN_PMI1 (OECD BCI for China).
    "CN_PMI2",
})


def _check_unadjusted_splits() -> list[str]:
    """Flag week-over-week price discontinuities in market_data_comp_hist.csv
    that look like a stock split Yahoo's feed never adjusted out (the failure
    mode behind 1306.T's bogus -89% returns).

    yfinance back-adjusts known splits via auto_adjust=True, but its
    corporate-actions feed is patchy for some non-US listings — an unadjusted
    split lands as a single-week jump on an otherwise smooth series,
    poisoning every return window straddling it. Splits happen at any ratio
    (2:1, 3:2, 4:3, 5:4, 7:5, 10:1, …), so the detector must be
    ratio-agnostic.

    Three filters together separate real unadjusted splits from market moves:
      1. Index skip — `^*` tickers are calculations, not securities, so they
         cannot split. Excluded outright.
      2. Clean-ratio match — splits produce *exact* integer-fraction price
         ratios (1/N or M/N for small integers). Market moves coincide with
         one only by accident, especially at the ±SPLIT_TOL tolerance below.
      3. Persistence — the new price level must hold within ±PERSIST_TOL
         over the next PERSIST_WEEKS weeks. A market move that happens to
         land on a clean fraction one week usually drifts off it the next.

    Discontinuities already registered in data/manual_splits.csv are handled
    (library_utils.apply_manual_splits back-adjusts them and
    scripts/backadjust_hist_splits.py corrects stored history), so only
    *unexplained* sustained jumps in the trailing window are reported.
    """
    comp_path = DATA / "market_data_comp_hist.csv"
    if not comp_path.exists():
        return []

    # Registered (ticker, ex_date) pairs to suppress.
    registered: set[tuple[str, str]] = set()
    splits_path = DATA / "manual_splits.csv"
    if splits_path.exists():
        with splits_path.open(newline="") as f:
            for row in csv.DictReader(f):
                tk = (row.get("ticker") or "").strip()
                ex = (row.get("ex_date") or "").strip()
                if tk and ex:
                    registered.add((tk, ex))

    with comp_path.open(newline="") as f:
        rows = list(csv.reader(f))

    # Locate the header row ('Date' in its first two cells) by inspection —
    # the comp metadata block grew 11 → 12 rows on 2026-07-08 (§2.A A16
    # "Last Observation") and both generations must parse.
    hdr_idx = None
    for i, r in enumerate(rows[:40]):
        if "Date" in [c.strip() for c in r[:2]]:
            hdr_idx = i
            break
    if hdr_idx is None or len(rows) <= hdr_idx + 1:
        return []

    ticker_row = rows[0]; variant_row = rows[1]
    data = rows[hdr_idx + 1:]
    # Look back far enough that a jump can have PERSIST_WEEKS of follow-up
    # weeks AND we still see ~8 weeks of usable history before it.
    scan = data[-(8 + 1 + 6):]              # 15 weekly closes

    # A weekly ratio outside this band is the *candidate* jump (catches splits
    # down to ~6:5 = 0.83 / 1.20).
    LO, HI = 0.85, 1.18
    SPLIT_TOL = 0.01                        # match within ±1% of a clean ratio
    PERSIST_WEEKS = 4                       # how long the new level must hold
    PERSIST_TOL = 0.15                      # within ±15% of the post-jump close

    # Clean integer-fraction ratios characteristic of real stock splits
    # (forward + reverse). Restricted to denominators ≤ 5 — i.e. 2:1, 3:1,
    # 4:1, 5:1, …, 20:1 plus the fractional splits 3:2, 4:3, 5:4, 5:2, 5:3
    # and their inverses. Exotic ratios like 5:6 / 6:5 / 7:5 are deliberately
    # excluded because real splits rarely use them and the wider list
    # produced false positives on ~16% ETF market moves (e.g. EWY 0.837).
    _split_ratios: set[float] = set()
    for n in (2, 3, 4, 5, 6, 7, 8, 10, 12, 15, 20):
        _split_ratios.add(1.0 / n)                          # forward 1:N
        _split_ratios.add(float(n))                          # reverse N:1
    for m, n in ((3, 2), (4, 3), (5, 4), (5, 2), (5, 3)):    # fractional M:N
        _split_ratios.add(n / m)                             # forward ratio
        _split_ratios.add(m / n)                             # reverse ratio

    def _looks_like_split(r: float) -> bool:
        return any(abs(r - sr) / sr <= SPLIT_TOL for sr in _split_ratios)

    issues: list[str] = []
    for c in range(2, len(ticker_row)):
        tk = ticker_row[c].strip()
        # Indices (^* tickers in yfinance convention) are calculations, not
        # securities — they cannot split. Skip outright to avoid false
        # positives on vol-index regime shifts (^VIX, ^GVZ, ^OVX, ^VIX3M …).
        if not tk or tk.startswith("^"):
            continue
        var = variant_row[c].strip() if c < len(variant_row) else ""
        if var != "Local":
            continue

        # Build a dense (date, value) series for this column.
        series: list[tuple[str, float]] = []
        for r in scan:
            if c >= len(r):
                continue
            d = r[1].strip()
            v = r[c].strip()
            try:
                cur = float(v)
            except ValueError:
                continue
            if cur > 0:
                series.append((d, cur))

        # Scan for jumps that have at least 2 follow-up weeks for the
        # persistence check.
        for i in range(1, len(series) - 1):
            d_prev, prev_val = series[i - 1]
            d_jump, cur_val  = series[i]
            ratio = cur_val / prev_val
            if LO <= ratio <= HI:
                continue
            if not _looks_like_split(ratio):
                continue
            if (tk, d_jump) in registered:
                continue

            followers = series[i + 1 : i + 1 + PERSIST_WEEKS]
            if len(followers) < 2:           # not enough follow-up to confirm
                continue
            persisted = all(
                abs(v_f / cur_val - 1.0) <= PERSIST_TOL
                for _, v_f in followers
            )
            if not persisted:
                continue

            issues.append(
                f"{tk}: {prev_val:g} → {cur_val:g} ({ratio:.3f}x) at {d_jump}, "
                f"matches clean split ratio + new level held within "
                f"±{int(PERSIST_TOL * 100)}% over the next {len(followers)} weeks "
                f"— possible unadjusted split; add a data/manual_splits.csv row "
                f"and run scripts/backadjust_hist_splits.py"
            )
            break  # one report per ticker — successive weeks would re-fire
    return issues


def _check_registry_drift() -> list[str]:
    """Every column present in a hist CSV must trace back to a row in the
    matching source-of-truth library CSV. Reports orphans across all three
    library_sync pairs (comp, macro_economic, macro_market) so the operator
    can run `python library_sync.py --confirm` to archive + prune.

    Iterates library_sync.SYNC_SPECS (§2.C C6) so the column-derivation
    rules (PR/TR for comp, OECD/WB/IMF country fan-out for macro economic,
    indicator suffixes for macro market) live in one place — a new hist
    pair registered there is automatically drift-checked here.
    """
    import library_sync as ls

    issues: list[str] = []
    for spec in ls.SYNC_SPECS:
        if not spec.hist_path.exists():
            continue
        with spec.hist_path.open(newline="") as f:
            rows = list(csv.reader(f))
        for col_id in sorted(ls._present_ids(spec, rows) - spec.expected()):
            issues.append(
                f"hist column {col_id!r} present in {spec.name} but no matching "
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

def _read_hist_dates(path: Path) -> list[str]:
    """Return the list of Date strings in the data section of a hist file.
    The header row is located by inspection ('Date' in its first two cells),
    so per-file metadata-prefix generations (14 vs 15 rows) both parse."""
    if not path.exists():
        return []
    with path.open(newline="") as f:
        rows = list(csv.reader(f))
    for i, r in enumerate(rows[:40]):
        cells = [c.strip() for c in r[:2]]
        if "Date" in cells:
            date_idx = r.index("Date")
            return [x[date_idx] for x in rows[i + 1:]
                    if len(x) > date_idx and x[date_idx]]
    return []


def section_d_history_preservation() -> dict:
    """Report live + sister row counts and date ranges per *_hist.csv pair."""
    pairs = [
        ("market_data_comp_hist.csv",  DATA / "market_data_comp_hist.csv",  True),
        ("macro_economic_hist.csv",    DATA / "macro_economic_hist.csv",    True),
        ("macro_market_hist.csv",      DATA / "macro_market_hist.csv",      False),
    ]
    issues: list[str] = []
    rows: list[dict] = []

    for name, live_path, has_ice_bofa in pairs:
        sister_path = live_path.with_name(live_path.name.replace("_hist.csv", "_hist_x.csv"))

        live_dates = _read_hist_dates(live_path)
        sister_dates = _read_hist_dates(sister_path) if sister_path.exists() else []

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
# Section E — Value plausibility (forward_plan §2.6)
# =============================================================================
# Catches the class of regression where a column carries a *present, fresh* but
# physically implausible value — e.g. a parser column-mapping bug surfacing a
# GDP subcomponent or an index level in a growth-rate slot. Section C only sees
# staleness; a wrong-but-still-moving value sails straight through it. The
# Atlanta Fed GDPNow parser shipped a ~24% US_GDPNOW1 nowcast on 2026-06-17
# (real value ~3.3%) that no audit section caught — this section is the backstop
# for that whole failure class.
#
# Bands are (min, max), inclusive, on the latest observed value. The built-in
# table below covers the headline growth nowcasts; any per-source library CSV
# row may also declare optional `plausible_min` / `plausible_max` columns to add
# a band declaratively without editing this file.

# col_id -> (min, max). Keep this short and physically motivated.
PLAUSIBILITY_BANDS_BY_COL: dict[str, tuple[float, float]] = {
    # Atlanta Fed GDPNow — Q/Q SAAR real GDP growth (%). Normal-cycle range is
    # ~[-10, +15]; this band is deliberately a touch wider than
    # test_atlanta_fed_smoke's [-10, 15] live-fetch tripwire so the audit (a
    # backstop on the *committed* value) and the smoke test (the tighter live
    # guard) aren't identical channels. A genuine pandemic-scale print (±35)
    # trips this — which is exactly when an operator should look.
    "US_GDPNOW": (-15.0, 20.0),
}


def load_plausibility_bands() -> dict[str, tuple[float, float]]:
    """Built-in bands overlaid with optional per-row `plausible_min` /
    `plausible_max` declarations from any macro_library_*.csv (library wins)."""
    bands = dict(PLAUSIBILITY_BANDS_BY_COL)
    for lib_name in SOURCE_BY_LIBRARY:
        path = DATA / f"macro_library_{lib_name}.csv"
        if not path.exists():
            continue
        with path.open(newline="") as f:
            for row in csv.DictReader(f):
                col = (row.get("col") or "").strip()
                lo = (row.get("plausible_min") or "").strip()
                hi = (row.get("plausible_max") or "").strip()
                if col and lo and hi:
                    try:
                        bands[col] = (float(lo), float(hi))
                    except ValueError:
                        pass
    return bands


def load_latest_macro_values() -> dict[str, dict]:
    """Return {col_id: {series_id, source, value, date}} for the latest
    non-empty cell per data column in macro_economic_hist.csv.

    Unlike load_macro_hist() (which tracks the last *value-change* date for the
    staleness check), this reports the actual most-recent numeric value — the
    quantity the plausibility band is checked against. Non-numeric columns fall
    out silently."""
    path = DATA / "macro_economic_hist.csv"
    with path.open(newline="") as f:
        rows = list(csv.reader(f))
    meta_rows, data_rows = _split_meta_and_data(rows)
    if not meta_rows or not data_rows:
        return {}

    labels = [r[0] for r in meta_rows]
    label_idx = {label: i for i, label in enumerate(labels)}
    n_cols = len(rows[0])

    out: dict[str, dict] = {}
    for ci in range(1, n_cols):
        last_val: str | None = None
        last_date = ""
        for dr in data_rows:
            if ci >= len(dr):
                continue
            cell = dr[ci].strip()
            if cell == "":
                continue
            last_val = cell
            last_date = dr[0].strip()
        if last_val is None:
            continue
        try:
            fval = float(last_val)
        except ValueError:
            continue
        col_id = meta_rows[label_idx["Column ID"]][ci].strip()
        out[col_id] = {
            "series_id": meta_rows[label_idx["Series ID"]][ci].strip(),
            "source":    meta_rows[label_idx["Source"]][ci].strip(),
            "value":     fval,
            "date":      last_date,
        }
    return out


def section_e_plausibility() -> dict:
    """Flag columns whose latest committed value falls outside its plausibility
    band. Returns {"implausible": [ {col_id, series_id, source, value, date,
    min, max}, ... ]}."""
    bands = load_plausibility_bands()
    latest = load_latest_macro_values()
    issues: list[dict] = []
    for col_id, (lo, hi) in sorted(bands.items()):
        rec = latest.get(col_id)
        if rec is None:
            continue
        v = rec["value"]
        if v < lo or v > hi:
            issues.append({
                "col_id":    col_id,
                "series_id": rec["series_id"],
                "source":    rec["source"],
                "value":     v,
                "date":      rec["date"],
                "min":       lo,
                "max":       hi,
            })
    return {"implausible": issues}


# =============================================================================
# Report rendering
# =============================================================================

# =============================================================================
# Section F — CRITICAL hard-fail gate (§2.C C8)
# =============================================================================
# The audit is deliberately a warning channel (exit 0) — EXCEPT for a tiny,
# deliberately-hard-to-trigger CRITICAL class where committing the data would
# bake a catastrophe into git history and downstream Sheets/automations:
#
#   (a) a SHEETS_PROTECTED_TABS output CSV that exists but carries ZERO rows
#       with any value cell — the all-NaN/empty regression class (protected
#       tabs feed the user's downstream trigger.py automations);
#   (b) a hist CSV that lost >10% of its rows or columns vs the committed
#       (HEAD) version — the truncated-rewrite class (hist files are
#       append-mostly; even a big library prune stays far under 10%).
#
# On any CRITICAL finding main() exits 2 and writes data_audit_critical.flag;
# update_data.yml commits only pipeline.log + the audit reports and SKIPS the
# data-file commit, so the bad artefacts never reach main. The (c) idea from
# the review (composite raw unchanged >k months) is intentionally absent:
# C1's [FALLBACK] demotion reporting + Section C EXPIRED already cover that
# signature as loud warnings, and freezes are sometimes upstream-legitimate.

CRITICAL_FLAG = ROOT / "data_audit_critical.flag"
_SHRINK_TOLERANCE = 0.10          # >10% row/col loss vs HEAD is CRITICAL
_HIST_GATED = [
    "data/market_data_comp_hist.csv", "data/market_data_comp_hist_x.csv",
    "data/macro_economic_hist.csv", "data/macro_economic_hist_x.csv",
    "data/macro_market_hist.csv", "data/macro_market_hist_x.csv",
]


def _csv_shape(rows: list[list[str]]) -> tuple[int, int]:
    """(row count, first-row cell count) — a cheap, format-agnostic shape."""
    return len(rows), (len(rows[0]) if rows else 0)


def _committed_shape(relpath: str) -> tuple[int, int] | None:
    """Shape of the HEAD version of relpath, or None when unavailable
    (not a git checkout, file new in this run, git missing). Failures skip
    the check rather than fail it — this gate must never false-trigger."""
    import io
    import subprocess
    try:
        out = subprocess.run(
            ["git", "show", f"HEAD:{relpath}"],
            capture_output=True, cwd=ROOT, timeout=120,
        )
        if out.returncode != 0:
            return None
        return _csv_shape(list(csv.reader(io.StringIO(out.stdout.decode("utf-8")))))
    except Exception:
        return None


def section_f_critical() -> dict:
    """Run the CRITICAL checks. Returns {"critical": [msg, ...]}."""
    critical: list[str] = []

    # (a) protected-tab outputs empty / all-NaN
    from library_utils import SHEETS_PROTECTED_TABS
    for tab in sorted(SHEETS_PROTECTED_TABS):
        path = DATA / f"{tab}.csv"
        if not path.exists():
            continue          # legacy tab with no CSV output (sentiment_data)
        with path.open(newline="") as f:
            rows = list(csv.reader(f))
        header, data_rows = (rows[0] if rows else []), rows[1:]
        if not data_rows:
            critical.append(f"protected output {path.name} has ZERO data rows")
            continue
        # Value region starts at "Last Price" (identity/metadata cols before
        # it are always populated and would mask an all-NaN regression).
        if "Last Price" in header:
            v0 = header.index("Last Price")
            if not any(any(c.strip() for c in r[v0:]) for r in data_rows):
                critical.append(
                    f"protected output {path.name}: all {len(data_rows)} data "
                    f"rows have EMPTY value cells (from column "
                    f"{header[v0]!r} on) — all-NaN regression"
                )

    # (b) hist CSVs shrinking vs the committed version
    for relpath in _HIST_GATED:
        path = ROOT / relpath
        if not path.exists():
            continue
        old = _committed_shape(relpath)
        if old is None:
            continue
        old_rows, old_cols = old
        with path.open(newline="") as f:
            new_rows, new_cols = _csv_shape(list(csv.reader(f)))
        for kind, new_n, old_n in [("row", new_rows, old_rows),
                                   ("column", new_cols, old_cols)]:
            if old_n and new_n < old_n * (1 - _SHRINK_TOLERANCE):
                critical.append(
                    f"{relpath}: {kind} count fell {old_n} → {new_n} "
                    f"(-{(1 - new_n / old_n) * 100:.0f}%, gate "
                    f"{int(_SHRINK_TOLERANCE * 100)}%) vs committed HEAD — "
                    f"truncated rewrite?"
                )

    return {"critical": critical}


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
    n_anchors_active  = len(c.get("anchors_active", []))
    n_anchors_overdue = len(c.get("anchors_overdue", []))
    lines.append(
        f"--- Section C: Value-change staleness "
        f"(FRESH {len(c['fresh'])}  STALE {len(c['stale'])}  EXPIRED {len(c['expired'])}"
        f"  ANCHORS {n_anchors_active}  OVERDUE-ANCHORS {n_anchors_overdue}) ---"
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
    # Anchors-overdue is an actual alert; surface it next to STALE/EXPIRED so
    # the operator sees it. Anchors-active is informational only.
    if n_anchors_overdue:
        lines.append(f"  OVERDUE-ANCHORS ({n_anchors_overdue}) — check upstream for newer release:")
        for r in c["anchors_overdue"]:
            age_str = f"{r['age']}d" if r["age"] is not None else "no_obs"
            lines.append(
                f"    {r['frequency']:10s}  {r['col_id']:32s}  "
                f"src={r['source']:11s}  series={r['series_id']:24s}  "
                f"last_obs={r['last_obs'] or '—':10s}  "
                f"age={age_str:8s}  next_expected_release={r.get('next_expected_release','—')}"
            )
    if n_anchors_active:
        lines.append(
            f"  ANCHORS-ACTIVE ({n_anchors_active}) — historical anchors, "
            f"no frequency-based staleness check (release cadence intrinsic):"
        )
        for r in c["anchors_active"]:
            ner_str = r.get("next_expected_release","") or "—"
            lines.append(
                f"    {r['frequency']:10s}  {r['col_id']:32s}  "
                f"src={r['source']:11s}  series={r['series_id']:24s}  "
                f"last_obs={r['last_obs'] or '—':10s}  "
                f"next_expected_release={ner_str}"
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

    # Section E — Value plausibility
    e = sections.get("e", {"implausible": []})
    n_e = len(e["implausible"])
    lines.append(f"--- Section E: Value plausibility ({n_e} issues) ---")
    if n_e == 0:
        lines.append("  (none)")
    else:
        for r in e["implausible"]:
            lines.append(
                f"  IMPLAUSIBLE  {r['col_id']:32s}  src={r['source']:11s}  "
                f"series={r['series_id']:24s}  value={r['value']:g}  "
                f"band=[{r['min']:g}, {r['max']:g}]  last_obs={r['date'] or '—'}"
            )
    lines.append("")

    # Section F — CRITICAL gate (§2.C C8)
    f_sec = sections.get("f", {"critical": []})
    n_f = len(f_sec["critical"])
    lines.append(f"--- Section F: CRITICAL gate ({n_f} finding(s)) ---")
    if n_f == 0:
        lines.append("  (none)")
    else:
        for item in f_sec["critical"]:
            lines.append(f"  CRITICAL  {item}")
        lines.append("  → audit exits nonzero; the daily workflow SKIPS the "
                     "data-file commit (pipeline.log + reports still committed).")
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
    n_anchors_overdue = len(c.get("anchors_overdue", []))
    n_anchors_active  = len(c.get("anchors_active", []))
    n_d = len(d["issues"])
    e = sections.get("e", {"implausible": []})
    n_e = len(e["implausible"])
    f_sec = sections.get("f", {"critical": []})
    n_f = len(f_sec["critical"])
    total = n_a + n_b + n_stale + n_anchors_overdue + n_d + n_e + n_f

    lines: list[str] = []
    # CRITICAL banner first — this is the one class that blocked the data
    # commit (§2.C C8), so it must be impossible to miss in the Issue thread.
    if n_f:
        lines.append(f"# 🛑 CRITICAL — data commit SKIPPED ({n_f} finding{'s' if n_f != 1 else ''})")
        for item in f_sec["critical"]:
            lines.append(f"> **{item}**")
        lines.append("")
    if total == 0:
        anchor_note = (
            f" (plus {n_anchors_active} historical anchor{'s' if n_anchors_active != 1 else ''} active)"
            if n_anchors_active else ""
        )
        lines.append(f"## Daily audit — {TODAY.isoformat()} — **ALL CLEAN**{anchor_note}")
    else:
        parts: list[str] = []
        if n_a:
            parts.append(f"{n_a} fetch error{'s' if n_a != 1 else ''}")
        if n_stale:
            parts.append(f"{n_stale} stale serie{'s' if n_stale != 1 else ''}")
        if n_anchors_overdue:
            parts.append(f"{n_anchors_overdue} overdue anchor{'s' if n_anchors_overdue != 1 else ''}")
        if n_b:
            parts.append(f"{n_b} static-check failure{'s' if n_b != 1 else ''}")
        if n_d:
            parts.append(f"{n_d} history-preservation issue{'s' if n_d != 1 else ''}")
        if n_e:
            parts.append(f"{n_e} implausible value{'s' if n_e != 1 else ''}")
        if n_f:
            parts.append(f"{n_f} CRITICAL")
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

    # Overdue anchors: real alert — go check upstream for a new release.
    if n_anchors_overdue:
        lines.append("<details open><summary>Overdue historical anchors — check upstream for newer release</summary>\n")
        lines.append("| Series | Source | Last obs | Age | Next expected release |")
        lines.append("|---|---|---|---|---|")
        for r in c["anchors_overdue"][:30]:
            age_str = f"{r['age']}d" if r["age"] is not None else "no_obs"
            lines.append(
                f"| `{r['col_id']}` | {r['source']} | {r['last_obs'] or '—'} | "
                f"{age_str} | {r.get('next_expected_release','—')} |"
            )
        if len(c["anchors_overdue"]) > 30:
            lines.append(f"| _… {len(c['anchors_overdue']) - 30} more in `data_audit.txt`_ |  |  |  |  |")
        lines.append("\n</details>\n")

    # Active anchors: informational only — historical datasets with intrinsic
    # release cadence (e.g. JST Macrohistory R6). Not a bug, but visible so
    # the operator knows they exist.
    if n_anchors_active:
        lines.append("<details><summary>Active historical anchors (informational)</summary>\n")
        lines.append("| Series | Source | Last obs | Next expected release |")
        lines.append("|---|---|---|---|")
        for r in c["anchors_active"][:30]:
            ner = r.get("next_expected_release","") or "—"
            lines.append(
                f"| `{r['col_id']}` | {r['source']} | {r['last_obs'] or '—'} | {ner} |"
            )
        if len(c["anchors_active"]) > 30:
            lines.append(f"| _… {len(c['anchors_active']) - 30} more in `data_audit.txt`_ |  |  |  |")
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

    # Section E — Value plausibility. A breach is a real alert (a fresh but
    # physically-wrong value), so render it open.
    if n_e:
        lines.append("<details open><summary>Implausible values — likely a parser / unit regression</summary>\n")
        lines.append("| Column | Source | Series | Value | Plausible band | Last obs |")
        lines.append("|---|---|---|---|---|---|")
        for r in e["implausible"]:
            lines.append(
                f"| `{r['col_id']}` | {r['source']} | `{r['series_id']}` | "
                f"**{r['value']:g}** | [{r['min']:g}, {r['max']:g}] | {r['date'] or '—'} |"
            )
        lines.append("\n</details>\n")

    return "\n".join(lines) + "\n"


def main() -> int:
    quiet = "--quiet" in sys.argv

    sections = {
        "a": section_a_fetch_outcomes(),
        "b": section_b_static_checks(),
        "c": section_c_staleness(),
        "d": section_d_history_preservation(),
        "e": section_e_plausibility(),
        "f": section_f_critical(),
    }

    OUT_REPORT.write_text(render_report(sections))
    OUT_COMMENT.write_text(render_comment(sections))

    if not quiet:
        print(OUT_REPORT.read_text())

    # §2.C C8: the audit stays a warning channel (exit 0) for Sections A–E;
    # only the deliberately-narrow Section F CRITICAL class fails the build.
    # The flag file is the commit-step contract in update_data.yml — when it
    # exists, only pipeline.log + the audit reports are committed.
    criticals = sections["f"]["critical"]
    if criticals:
        CRITICAL_FLAG.write_text("\n".join(criticals) + "\n")
        return 2
    CRITICAL_FLAG.unlink(missing_ok=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
