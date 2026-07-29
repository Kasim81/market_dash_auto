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

import pandas as pd

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

    def test_tier0_quarterly_primary_now_beats_tier1_monthly(self):
        """Owner policy 2026-07-27: prefer the primary over an aggregator.

        Previously cadence-first served the tier-1 monthly aggregator here and
        emitted a demotion event. Under tier-first the tier-0 national primary
        wins (quarterly still clears the cadence floor), so there is nothing to
        demote. Where the aggregator's better frequency is genuinely wanted the
        answer is to register it as its OWN series — see the
        FRA_UNEMPLOYMENT / FRA_UNEMPLOYMENT_OECD split.
        """
        rows = [_row("ABS", "X_CPI", 101.7, "Index", "Quarterly", "2026-Q1", 0),
                _row("OECD", "X_CPI", 102.0, "Index", "Monthly", "2026-04", 1)]
        win, log = _dedupe_capturing(rows)
        self.assertEqual(win[0]["Source"], "ABS")
        self.assertNotIn("[FALLBACK]", log)

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


class CadenceFloorTest(unittest.TestCase):
    """Annual never serves a column that registers a sub-annual source.

    The 2026-07-27 live incident: `CHE_CPI_YOY` swapped from the monthly
    OECD/DB.nomics series to the World Bank **annual** series (both tier 1),
    rewriting 3,678 of 4,153 history rows and truncating the series start from
    1956 to 1961. Under the owner policy ("annual data is of extremely limited
    value"; floor of quarterly) the annual candidate is structurally
    ineligible, so the swap cannot happen at all — no detector required.
    """

    def _che_rows(self, monthly_value):
        return [
            _row("DB.nomics", "CHE_CPI_YOY", monthly_value, "Percent Change YoY",
                 "Monthly", "2026-05-31", 1, country="CHE"),
            _row("World Bank", "CHE_CPI_YOY", 0.154,
                 "% change year-on-year (annual average)", "Annual",
                 "2025-12-31", 1, country="CHE"),
        ]

    def test_annual_cannot_take_over_from_a_silent_monthly(self):
        """The exact live regression — the column holds instead of flipping."""
        out, _ = _dedupe_capturing(self._che_rows(None))    # monthly has no data
        self.assertEqual(out[0]["Source"], "DB.nomics")
        self.assertNotEqual(out[0]["Source"], "World Bank")

    def test_healthy_finer_source_serves(self):
        out, log = _dedupe_capturing(self._che_rows(0.61))
        self.assertEqual(out[0]["Source"], "DB.nomics")
        self.assertNotIn("[FALLBACK]", log)

    def test_annual_cannot_take_over_from_a_stale_monthly(self):
        """Even 900d stale, the sub-annual source keeps the column."""
        stale = (date.today() - timedelta(days=900)).isoformat()
        rows = [
            _row("DB.nomics", "X_CPI_YOY", 1.0, "% YoY", "Monthly", stale, 1),
            _row("World Bank", "X_CPI_YOY", 2.0, "% YoY", "Annual",
                 (date.today() - timedelta(days=20)).isoformat(), 1),
        ]
        out, _ = _dedupe_capturing(rows)
        self.assertEqual(out[0]["Source"], "DB.nomics")

    def test_annual_still_serves_when_it_is_the_only_source(self):
        """The floor is relative: annual-only columns are unaffected."""
        rows = [_row("World Bank", "IDN_CPI_YOY", 3.0, "% YoY", "Annual", "2024", 1)]
        out, _ = _dedupe_capturing(rows)
        self.assertEqual(out[0]["Source"], "World Bank")

    def test_quarterly_clears_the_floor(self):
        """Quarterly is the floor, not below it — it beats an annual sibling."""
        rows = [_row("ABS", "AUS_GDP_GROWTH", 1.2, "% YoY", "Quarterly",
                     "2026-Q1", 0, country="AUS"),
                _row("IMF", "AUS_GDP_GROWTH", 2.4, "% YoY", "Annual",
                     "2031-12-31", 1, country="AUS")]
        out, _ = _dedupe_capturing(rows)
        self.assertEqual(out[0]["Source"], "ABS")


class TierFirstTest(unittest.TestCase):
    """Primary beats aggregator; cadence is the tiebreak within a tier."""

    def test_primary_wins_even_at_coarser_cadence(self):
        rows = [_row("INSEE", "FRA_UNEMPLOYMENT", 8.1, "Percent (SA)",
                     "Quarterly", "2026-03-28", 0, country="FRA"),
                _row("OECD", "FRA_UNEMPLOYMENT", 8.2, "Percent (SA)",
                     "Monthly", "2026-05-31", 1, country="FRA")]
        out, log = _dedupe_capturing(rows)
        self.assertEqual(out[0]["Source"], "INSEE")
        self.assertNotIn("[FALLBACK]", log)      # primary won — nothing demoted

    def test_cadence_still_breaks_ties_within_a_tier(self):
        rows = [_row("OECD", "X_CPI", 2.0, "% YoY", "Quarterly", "2026-Q1", 1),
                _row("IMF SDMX", "X_CPI", 2.1, "% YoY", "Monthly", "2026-05", 1)]
        out, _ = _dedupe_capturing(rows)
        self.assertEqual(out[0]["Source"], "IMF SDMX")

    def test_stale_primary_still_yields_to_fresher_fallback(self):
        """Tier-first must not disarm the staleness gate."""
        rows = [_row("BoJ", "X_RATE", 0.1, "Percent", "Monthly", "2025-04", 0),
                _row("FRED", "X_RATE", 0.5, "Percent", "Monthly", "2026-04", 1)]
        out, log = _dedupe_capturing(rows)
        self.assertEqual(out[0]["Source"], "FRED")
        self.assertIn("[FALLBACK]", log)

    def test_winner_at_finest_cadence_is_not_an_event(self):
        cands = [
            {"has_data": True, "kind": "rate", "cad_rank": 2, "cad_days": 31,
             "last": date.today(), "tier": 1, "rank": 2, "order": 0, "payload": {}},
            {"has_data": True, "kind": "rate", "cad_rank": 4, "cad_days": 366,
             "last": date.today(), "tier": 1, "rank": 2, "order": 1, "payload": {}},
        ]
        win = f._select_winner(cands)
        self.assertEqual(win["cad_rank"], 2)
        self.assertIsNone(f._demotion_event(cands, win))

    def test_tier_demotion_still_takes_precedence(self):
        """A real tier demotion keeps its own reason, not the cadence one."""
        rows = [
            _row("ONS", "X_RATE", None, "% YoY", "Monthly", "2026-05-31", 0),
            _row("FRED", "X_RATE", 1.0, "% YoY", "Monthly", "2026-05-31", 1),
        ]
        out, log = _dedupe_capturing(rows)
        self.assertEqual(out[0]["Source"], "FRED")
        self.assertIn("[FALLBACK]", log)
        self.assertNotIn("CADENCE DEGRADED", log)


class ForecastDateTest(unittest.TestCase):
    """A future-dated observation is a projection, not freshness.

    Regression cover for the 2026-07-23 daily-audit finding: IMF DataMapper
    publishes annual forecasts years ahead of the last actual, and those rows
    were setting the group's "freshest" mark — pushing the real national
    quarterly primaries past the 2x-cadence staleness gate so the forecast
    won. `_eff_last` clamps future dates to today for every freshness
    comparison.
    """

    def test_eff_last_clamps_future_only(self):
        past = date.today() - timedelta(days=200)
        future = date.today() + timedelta(days=2000)
        self.assertEqual(f._eff_last(past), past)          # actuals untouched
        self.assertEqual(f._eff_last(future), date.today())
        self.assertIsNone(f._eff_last(None))

    def test_annual_forecast_does_not_demote_quarterly_primary(self):
        """The live AUS_GDP_GROWTH / ITA_GDP_GROWTH signature."""
        actual = date.today() - timedelta(days=148)        # ~last quarter's print
        forecast = date(date.today().year + 5, 12, 31)     # IMF projection
        rows = [
            _row("ABS", "AUS_GDP_GROWTH", 1.2, "% YoY", "Quarterly",
                 actual.isoformat(), 0, country="AUS"),
            _row("IMF", "AUS_GDP_GROWTH", 2.4, "% YoY", "Annual",
                 forecast.isoformat(), 1, country="AUS"),
        ]
        out, log = _dedupe_capturing(rows)
        self.assertEqual(len(out), 1)
        # the national quarterly actual wins on cadence, not the projection
        self.assertEqual(out[0]["Source"], "ABS")
        self.assertNotIn("[FALLBACK]", log)

    def test_genuinely_stale_primary_still_demoted(self):
        """The clamp must not disarm the staleness gate for real observations."""
        stale = date.today() - timedelta(days=900)
        fresh = date.today() - timedelta(days=10)
        rows = [
            _row("ISTAT", "X_IND_PROD", 1.0, "% YoY", "Monthly",
                 stale.isoformat(), 0),
            _row("OECD", "X_IND_PROD", 1.5, "% YoY", "Monthly",
                 fresh.isoformat(), 1),
        ]
        out, log = _dedupe_capturing(rows)
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["Source"], "OECD")
        self.assertIn("[FALLBACK]", log)

    def test_forecast_wins_when_it_is_the_only_candidate(self):
        """Clamping affects ranking only — a lone forecast row still serves."""
        forecast = date(date.today().year + 5, 12, 31)
        cands = [{
            "has_data": True, "kind": "rate", "cad_rank": 4, "cad_days": 366,
            "last": forecast, "tier": 1, "rank": 2, "order": 0, "payload": {},
        }]
        self.assertIs(f._select_winner(cands), cands[0])

    def test_two_forecasts_tiebreak_falls_to_tier(self):
        """Both clamped to today -> freshness ties, so tier decides."""
        forecast = date(date.today().year + 5, 12, 31)
        cands = [
            {"has_data": True, "kind": "rate", "cad_rank": 4, "cad_days": 366,
             "last": forecast, "tier": 2, "rank": 2, "order": 0, "payload": {}},
            {"has_data": True, "kind": "rate", "cad_rank": 4, "cad_days": 366,
             "last": forecast, "tier": 0, "rank": 1, "order": 1, "payload": {}},
        ]
        self.assertEqual(f._select_winner(cands)["tier"], 0)


if __name__ == "__main__":
    unittest.main()


class SeamValidationTest(unittest.TestCase):
    """§2.C C16 seam validation, cased on the real Phase 0 survey findings.

    The credentialed survey (run 30495180351) classified 34 contested pairs
    against live data; these assert the gate reproduces its verdicts, so the
    tolerances are pinned to observed behaviour rather than invented numbers.
    """

    @staticmethod
    def _mk(start, n, freq, step=0.0, base=100.0):
        idx = pd.period_range(start=start, periods=n, freq=freq).to_timestamp()
        return pd.Series([base + i * step for i in range(n)], index=idx)

    def test_period_normalisation_bridges_stamping_conventions(self):
        """Month-END vs month-START must still overlap (the USA_UNEMPLOYMENT bug)."""
        end = pd.Series(1.0, index=pd.date_range("2020-01-31", periods=40, freq="ME"))
        start = pd.Series(1.0, index=pd.date_range("2020-01-01", periods=40, freq="MS"))
        a = f._to_period_index(end, "Monthly")
        b = f._to_period_index(start, "Monthly")
        self.assertEqual(len(a.index.intersection(b.index)), 40)

    def test_identical_rate_series_agree(self):
        a = self._mk("2000-01", 60, "M", step=0.01, base=3.0)
        ok, why, scale = f._seam_agreement(a, "Monthly", a.copy(), "Monthly", "rate")
        self.assertTrue(ok, why)
        self.assertEqual(scale, 1.0)

    def test_rate_divergence_is_refused(self):
        a = self._mk("2000-01", 60, "M", base=3.0)
        b = a + 0.9                      # far beyond the 0.15pp tolerance
        ok, why, _ = f._seam_agreement(a, "Monthly", b, "Monthly", "rate")
        self.assertFalse(ok)
        self.assertIn("max|diff|", why)

    def test_index_pure_rebasing_is_accepted_and_rescaled(self):
        """The USA_CPI_INDEX / USA_CORE_CPI_INDEX case (drift 0.0000)."""
        a = self._mk("1990-01", 120, "M", step=0.3, base=100.0)
        b = a * 1.25                     # different base year, constant ratio
        ok, why, scale = f._seam_agreement(a, "Monthly", b, "Monthly", "index")
        self.assertTrue(ok, why)
        self.assertAlmostEqual(scale, 1.25, places=6)
        self.assertIn("rebasing", why)

    def test_index_drift_is_refused(self):
        """The DEU_IND_PROD / JPN_CPI_INDEX class — base AND methodology differ."""
        a = self._mk("1990-01", 120, "M", step=0.3, base=100.0)
        b = a * pd.Series([1.0 + 0.001 * i for i in range(120)], index=a.index)
        ok, why, _ = f._seam_agreement(a, "Monthly", b, "Monthly", "index")
        self.assertFalse(ok)
        self.assertIn("drifts", why)

    def test_thin_overlap_is_refused(self):
        a = self._mk("2020-01", 6, "M", base=2.0)
        ok, why, _ = f._seam_agreement(a, "Monthly", a.copy(), "Monthly", "rate")
        self.assertFalse(ok)
        self.assertIn("overlap", why)

    def test_disjoint_is_refused(self):
        a = self._mk("2010-01", 60, "M", base=2.0)
        b = self._mk("1980-01", 60, "M", base=2.0)
        ok, why, _ = f._seam_agreement(a, "Monthly", b, "Monthly", "rate")
        self.assertFalse(ok)
        self.assertIn("no overlapping periods", why)

    def test_cross_cadence_is_refused_pending_convention(self):
        """9 CADENCE_DIFF pairs are blocked on a declared aggregation
        convention — the gate must refuse rather than guess (C16.1)."""
        m = self._mk("2000-01", 300, "M", base=2.0)
        y = self._mk("2000", 25, "Y", base=2.0)
        ok, why, _ = f._seam_agreement(m, "Monthly", y, "Annual", "rate")
        self.assertFalse(ok)
        self.assertIn("aggregation convention", why)
