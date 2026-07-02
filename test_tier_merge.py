"""Unit tests for the tier-aware, cadence-first, staleness-fallback source
selection wired into fetch_macro_economic (P1 precedence, 2026-06-18)."""
import fetch_macro_economic as f


# ---- measure-kind classification ----
def test_measure_kind():
    assert f._measure_kind("Index 2015=100") == "index"
    assert f._measure_kind("% change year-on-year (annual average)") == "rate"
    assert f._measure_kind("Percent") == "rate"
    assert f._measure_kind("% per annum") == "rate"
    assert f._measure_kind("USD millions") == "level"


# ---- period parsing ----
def test_period_to_date():
    from datetime import date
    assert f._period_to_date("2024") == date(2024, 12, 31)
    assert f._period_to_date("2026-04") == date(2026, 4, 28)
    assert f._period_to_date("2026-Q2") == date(2026, 6, 28)
    assert f._period_to_date("2026-05-01") == date(2026, 5, 1)
    assert f._period_to_date("") is None


def _row(source, col, val, units, freq, last, tier, country="JPN"):
    return {"Country": country, "Col": col, "Source": source, "Latest Value": val,
            "Units": units, "Frequency": freq, "Last Period": last, "_tier": tier}


# ---- selection policy ----
def test_cadence_first_same_kind():
    # monthly (aggregator, tier1) beats annual (primary, tier0) when both fresh
    rows = [_row("World Bank", "X_CPI_YOY", 2.0, "% YoY", "Annual", "2025", 1),
            _row("OECD", "X_CPI_YOY", 2.1, "% YoY", "Monthly", "2026-04", 1)]
    win = f._dedupe_snapshot_rows(rows)
    assert len(win) == 1 and win[0]["Frequency"] == "Monthly"


def test_tier_tiebreak_same_cadence():
    # same cadence + kind → lower tier (national) wins over aggregator
    rows = [_row("FRED", "X_UNEMP", 5.0, "Percent", "Monthly", "2026-04", 1),
            _row("ONS", "X_UNEMP", 5.0, "Percent", "Monthly", "2026-04", 0)]
    win = f._dedupe_snapshot_rows(rows)[0]
    assert win["Source"] == "ONS"


def test_stale_finer_yields_to_fresh_coarser():
    # a monthly primary frozen ~1yr behind loses to a fresh(er) fallback
    rows = [_row("BoJ", "X_RATE", 0.1, "Percent", "Monthly", "2025-04", 0),
            _row("FRED", "X_RATE", 0.5, "Percent", "Monthly", "2026-04", 1)]
    win = f._dedupe_snapshot_rows(rows)[0]
    # BoJ is stale (>2 months behind FRED's 2026-04) → FRED wins despite tier
    assert win["Source"] == "FRED"


def test_fresh_primary_kept_over_aggregator():
    rows = [_row("BoJ", "X_RATE", 0.1, "Percent", "Daily", "2026-04-30", 0),
            _row("FRED", "X_RATE", 0.5, "Percent", "Monthly", "2026-04", 1)]
    win = f._dedupe_snapshot_rows(rows)[0]
    assert win["Source"] == "BoJ"  # daily & fresh → finest cadence wins


def test_sole_candidate_wins_regardless_of_tier():
    rows = [_row("World Bank", "IDN_CPI", 3.0, "% YoY", "Annual", "2024", 1)]
    win = f._dedupe_snapshot_rows(rows)[0]
    assert win["Source"] == "World Bank"


def test_definition_collision_falls_back_to_legacy():
    # index (monthly, frozen) vs YoY (annual) → kind mix → legacy freshest wins,
    # NOT cadence-first (which would wrongly pick the frozen monthly index).
    rows = [_row("FRED", "JPN_CPI", 105.0, "Index 2015=100", "Monthly", "2021-06", 1),
            _row("World Bank", "JPN_CPI", 2.7, "% change year-on-year", "Annual", "2024", 1)]
    win = f._dedupe_snapshot_rows(rows)[0]
    # WB 2024 is fresher than the frozen 2021 index → YoY served (no regression)
    assert win["Source"] == "World Bank" and "year-on-year" in win["Units"]


def test_no_data_keeps_first():
    rows = [_row("FRED", "X", None, "Percent", "Monthly", "", 1),
            _row("ONS", "X", None, "Percent", "Monthly", "", 0)]
    win = f._dedupe_snapshot_rows(rows)[0]
    assert win["Source"] == "FRED"  # stable: first appearance when no data
