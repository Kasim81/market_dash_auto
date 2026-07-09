"""Unit tests for the tier-aware, cadence-first, staleness-fallback source
selection wired into fetch_macro_economic (P1 precedence, 2026-06-18), and
for the §2.C C1 declared-primary demotion reporting layered on top of it
(2026-07-09).

NOTE (2026-07-09): originally written as bare pytest-style functions, which
`python -m unittest test_tier_merge` silently collected as 0 tests — the CI
gate never ran them. Converted to unittest.TestCase as part of C1 (the same
latent-gap class as the test_macro_hist_merge fixture fix).
"""
import contextlib
import io
import os
import sys
import unittest
from datetime import date, timedelta

os.environ.setdefault("FRED_API_KEY", "x")
os.environ.setdefault("SHEET_ID", "x")
os.environ.setdefault("GOOGLE_CREDENTIALS_JSON", "{}")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fetch_macro_economic as f  # noqa: E402


def _row(source, col, val, units, freq, last, tier, country="JPN"):
    return {"Country": country, "Col": col, "Source": source, "Latest Value": val,
            "Units": units, "Frequency": freq, "Last Period": last, "_tier": tier,
            "Series ID": f"{source}_SERIES"}


def _dedupe_capturing(rows):
    """Run _dedupe_snapshot_rows capturing stdout (the [FALLBACK] channel)."""
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        out = f._dedupe_snapshot_rows(rows)
    return out, buf.getvalue()


class HelperTest(unittest.TestCase):
    def test_measure_kind(self):
        self.assertEqual(f._measure_kind("Index 2015=100"), "index")
        self.assertEqual(f._measure_kind("% change year-on-year (annual average)"), "rate")
        self.assertEqual(f._measure_kind("Percent"), "rate")
        self.assertEqual(f._measure_kind("% per annum"), "rate")
        self.assertEqual(f._measure_kind("USD millions"), "level")

    def test_period_to_date(self):
        self.assertEqual(f._period_to_date("2024"), date(2024, 12, 31))
        self.assertEqual(f._period_to_date("2026-04"), date(2026, 4, 28))
        self.assertEqual(f._period_to_date("2026-Q2"), date(2026, 6, 28))
        self.assertEqual(f._period_to_date("2026-05-01"), date(2026, 5, 1))
        self.assertIsNone(f._period_to_date(""))


class SelectionPolicyTest(unittest.TestCase):
    def test_cadence_first_same_kind(self):
        # monthly (aggregator, tier1) beats annual (primary-ish, tier1) when both fresh
        rows = [_row("World Bank", "X_CPI_YOY", 2.0, "% YoY", "Annual", "2025", 1),
                _row("OECD", "X_CPI_YOY", 2.1, "% YoY", "Monthly", "2026-04", 1)]
        win = f._dedupe_snapshot_rows(rows)
        self.assertEqual(len(win), 1)
        self.assertEqual(win[0]["Frequency"], "Monthly")

    def test_tier_tiebreak_same_cadence(self):
        # same cadence + kind → lower tier (national) wins over aggregator
        rows = [_row("FRED", "X_UNEMP", 5.0, "Percent", "Monthly", "2026-04", 1),
                _row("ONS", "X_UNEMP", 5.0, "Percent", "Monthly", "2026-04", 0)]
        win = f._dedupe_snapshot_rows(rows)[0]
        self.assertEqual(win["Source"], "ONS")

    def test_stale_finer_yields_to_fresh_coarser(self):
        # a monthly primary frozen ~1yr behind loses to a fresh(er) fallback
        rows = [_row("BoJ", "X_RATE", 0.1, "Percent", "Monthly", "2025-04", 0),
                _row("FRED", "X_RATE", 0.5, "Percent", "Monthly", "2026-04", 1)]
        win = f._dedupe_snapshot_rows(rows)[0]
        # BoJ is stale (>2 months behind FRED's 2026-04) → FRED wins despite tier
        self.assertEqual(win["Source"], "FRED")

    def test_fresh_primary_kept_over_aggregator(self):
        rows = [_row("BoJ", "X_RATE", 0.1, "Percent", "Daily", "2026-04-30", 0),
                _row("FRED", "X_RATE", 0.5, "Percent", "Monthly", "2026-04", 1)]
        win = f._dedupe_snapshot_rows(rows)[0]
        self.assertEqual(win["Source"], "BoJ")  # daily & fresh → finest cadence wins

    def test_sole_candidate_wins_regardless_of_tier(self):
        rows = [_row("World Bank", "IDN_CPI", 3.0, "% YoY", "Annual", "2024", 1)]
        win = f._dedupe_snapshot_rows(rows)[0]
        self.assertEqual(win["Source"], "World Bank")

    def test_definition_collision_falls_back_to_legacy(self):
        # index (monthly, frozen) vs YoY (annual) → kind mix → legacy freshest wins,
        # NOT cadence-first (which would wrongly pick the frozen monthly index).
        rows = [_row("FRED", "JPN_CPI", 105.0, "Index 2015=100", "Monthly", "2021-06", 1),
                _row("World Bank", "JPN_CPI", 2.7, "% change year-on-year", "Annual", "2024", 1)]
        win = f._dedupe_snapshot_rows(rows)[0]
        # WB 2024 is fresher than the frozen 2021 index → YoY served (no regression)
        self.assertEqual(win["Source"], "World Bank")
        self.assertIn("year-on-year", win["Units"])

    def test_no_data_keeps_first(self):
        rows = [_row("FRED", "X", None, "Percent", "Monthly", "", 1),
                _row("ONS", "X", None, "Percent", "Monthly", "", 0)]
        win = f._dedupe_snapshot_rows(rows)[0]
        self.assertEqual(win["Source"], "FRED")  # stable: first appearance when no data


class DemotionReportingTest(unittest.TestCase):
    """§2.C C1: a demoted declared primary must emit a [FALLBACK] line —
    the pipeline.log contract data_audit Section A scrapes."""

    def test_stale_primary_demotion_logged_with_reason(self):
        rows = [_row("BoJ", "X_RATE", 0.1, "Percent", "Monthly", "2025-04", 0),
                _row("FRED", "X_RATE", 0.5, "Percent", "Monthly", "2026-04", 1)]
        win, log = _dedupe_capturing(rows)
        self.assertEqual(win[0]["Source"], "FRED")
        self.assertIn("[FALLBACK]", log)
        self.assertIn("X_RATE", log)
        self.assertIn("BoJ/BoJ_SERIES", log)      # demoted primary named
        self.assertIn("stale", log)                # reason class
        self.assertIn("serving FRED/FRED_SERIES", log)

    def test_no_data_primary_demotion_logged(self):
        rows = [_row("ONS", "X_UNEMP", None, "Percent", "Monthly", "", 0),
                _row("FRED", "X_UNEMP", 5.0, "Percent", "Monthly", "2026-04", 1)]
        win, log = _dedupe_capturing(rows)
        self.assertEqual(win[0]["Source"], "FRED")
        self.assertIn("[FALLBACK]", log)
        self.assertIn("no data", log)

    def test_fresh_primary_win_emits_no_fallback(self):
        rows = [_row("ONS", "X_UNEMP", 5.0, "Percent", "Monthly", "2026-04", 0),
                _row("FRED", "X_UNEMP", 5.0, "Percent", "Monthly", "2026-04", 1)]
        win, log = _dedupe_capturing(rows)
        self.assertEqual(win[0]["Source"], "ONS")
        self.assertNotIn("[FALLBACK]", log)

    def test_equal_tier_freshness_pick_is_not_a_demotion(self):
        # Two tier-1 aggregators: whichever wins, no primary was demoted.
        rows = [_row("OECD", "X_CPI", 2.0, "% YoY", "Monthly", "2026-03", 1),
                _row("IMF", "X_CPI", 2.1, "% YoY", "Monthly", "2026-04", 1)]
        _, log = _dedupe_capturing(rows)
        self.assertNotIn("[FALLBACK]", log)

    def test_finer_cadence_fallback_over_coarser_primary_logged(self):
        # tier-0 quarterly primary vs fresh tier-1 monthly → cadence-first
        # serves the aggregator; that IS a demotion event worth reporting.
        rows = [_row("ABS", "X_CPI", 101.7, "Index", "Quarterly", "2026-Q1", 0),
                _row("OECD", "X_CPI", 102.0, "Index", "Monthly", "2026-04", 1)]
        win, log = _dedupe_capturing(rows)
        self.assertEqual(win[0]["Source"], "OECD")
        self.assertIn("[FALLBACK]", log)
        self.assertIn("finer-cadence", log)

    def test_definition_collision_demotion_names_the_collision(self):
        rows = [_row("ONS", "X_CPI", 105.0, "Index 2015=100", "Monthly", "2021-06", 0),
                _row("World Bank", "X_CPI", 2.7, "% change year-on-year", "Annual", "2024", 1)]
        win, log = _dedupe_capturing(rows)
        self.assertEqual(win[0]["Source"], "World Bank")
        self.assertIn("[FALLBACK]", log)
        self.assertIn("definition collision", log)

    def test_demotion_event_helper_none_when_primary_wins(self):
        cands = [
            {"has_data": True, "kind": "rate", "cad_rank": 2, "cad_days": 31,
             "last": date(2026, 4, 28), "tier": 0, "rank": 1, "order": 0,
             "payload": {}},
            {"has_data": True, "kind": "rate", "cad_rank": 2, "cad_days": 31,
             "last": date(2026, 4, 28), "tier": 1, "rank": 0, "order": 1,
             "payload": {}},
        ]
        win = f._select_winner(cands)
        self.assertEqual(win["tier"], 0)
        self.assertIsNone(f._demotion_event(cands, win))

    def test_demotion_event_counts_extra_primaries(self):
        old = date.today() - timedelta(days=400)
        cands = [
            {"has_data": True, "kind": "rate", "cad_rank": 2, "cad_days": 31,
             "last": old, "tier": 0, "rank": 1, "order": 0, "payload": {}},
            {"has_data": False, "kind": "rate", "cad_rank": 2, "cad_days": 31,
             "last": None, "tier": 0, "rank": 1, "order": 1, "payload": {}},
            {"has_data": True, "kind": "rate", "cad_rank": 2, "cad_days": 31,
             "last": date.today(), "tier": 1, "rank": 0, "order": 2, "payload": {}},
        ]
        win = f._select_winner(cands)
        self.assertEqual(win["tier"], 1)
        event = f._demotion_event(cands, win)
        self.assertIsNotNone(event)
        prim, reason = event
        self.assertTrue(prim["has_data"])          # best primary = the dated one
        self.assertIn("+1 other tier-0", reason)


if __name__ == "__main__":
    unittest.main()
