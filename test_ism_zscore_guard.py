"""
CP-05 regression tests: the ISM z-score corruption and the guards added for it.

Background. In September 2026 the weekly signal engine put ISM Manufacturing at
the top of the article with z = +3.63 and a 13-week peak of 5.75 sigma. Nothing
was wrong with the reading itself — August 2026 really did print 54.6 — but the
DB.nomics ISM mirror had published ~10 on a 0-100 diffusion index from 2025-09
and then stopped entirely after 2025-12. The plausibility guard correctly
dropped the ~10s, which left the column ending in August 2025 with one lone
recent point spliced on top. `_to_weekly_friday` then forward-filled ~40
constant weeks across the hole, the 156-week rolling sigma collapsed from ~2.3
to 1.04, and a real reading scored six sigma.

Three things are tested here, one per layer of the fix:

  1. `_to_weekly_friday` bounds its interior forward-fill, so a dead feed can
     no longer fabricate a flat run that crushes sigma.
  2. `sources.ism_prnewswire` persists every official release point it parses,
     and `_maybe_ism_fallback` overlays the whole store on the mirror — so a
     month the mirror never delivered stays filled on the next run.
  3. `compute_macro_market.zscore_sanity_warnings` flags any macro z beyond
     ±4, so a future scaling/splice/window fault is loud rather than silent.

Offline and deterministic — no network, no Bright Data credentials.
"""

import os
import re
import sys
import tempfile
import unittest

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from calculators.common import (  # noqa: E402
    _to_weekly_friday, _rolling_zscore, _WEEKLY_FFILL_LIMIT,
)
from sources import ism_prnewswire as ism  # noqa: E402

STORE_CSV = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                         "data", "ism_release_history.csv")

# ISM diffusion indexes live in [0, 100]; in practice every print since 1948
# sits well inside this. Used to sanity-check the shipped store.
_DIFFUSION_LO, _DIFFUSION_HI = 25.0, 95.0


def _monthly(start: str, values: list[float]) -> pd.Series:
    """Month-end series, the shape DB.nomics observations land in."""
    idx = pd.date_range(start, periods=len(values), freq="ME")
    return pd.Series(values, index=idx, dtype=float)


class TestBoundedWeeklyFill(unittest.TestCase):
    """Layer 1: the resampler must not bridge a hole wider than a quarter."""

    def test_monthly_gaps_still_fill(self):
        """The normal case — weeks between monthly prints — is unchanged."""
        s = _monthly("2024-01-31", [50.0, 51.0, 52.0, 53.0])
        w = _to_weekly_friday(s)
        self.assertFalse(w.isna().any(), "monthly→weekly fill should leave no NaN")
        self.assertEqual(w.iloc[-1], 53.0)

    def test_quarterly_gaps_still_fill(self):
        """Quarterly series (~13 weeks apart) must survive the bound."""
        idx = pd.date_range("2024-03-31", periods=6, freq="QE")
        s = pd.Series([1.0, 2.0, 3.0, 4.0, 5.0, 6.0], index=idx)
        w = _to_weekly_friday(s)
        self.assertFalse(w.isna().any(), "quarterly gaps must still bridge")

    def test_long_interior_hole_is_not_bridged(self):
        """A dead-feed hole reads as NaN instead of a fabricated flat run."""
        early = _monthly("2024-01-31", [48.0, 48.5, 48.7])
        late = pd.Series([54.6], index=pd.DatetimeIndex(["2025-08-31"]))
        w = _to_weekly_friday(pd.concat([early, late]))
        hole = w.loc["2024-08-01":"2025-07-31"]
        self.assertTrue(hole.isna().all(),
                        "a 12-month hole must stay NaN, not forward-fill")
        self.assertEqual(w.dropna().iloc[-1], 54.6, "the real point still lands")

    def test_fill_limit_is_a_quarter(self):
        """The bound is 13 weekly rows; the 14th stays NaN."""
        s = pd.Series([50.0], index=pd.DatetimeIndex(["2024-01-05"]))
        tail = pd.Series([51.0], index=pd.DatetimeIndex(["2025-01-03"]))
        w = _to_weekly_friday(pd.concat([s, tail]))
        filled = w.loc["2024-01-05":"2024-12-31"].notna().sum()
        self.assertEqual(filled, _WEEKLY_FFILL_LIMIT + 1,
                         "anchor plus exactly 13 filled rows")

    def test_unbounded_opt_out_still_available(self):
        """ffill_limit=None restores the old behaviour for callers that want it."""
        early = _monthly("2024-01-31", [48.0])
        late = pd.Series([54.6], index=pd.DatetimeIndex(["2025-08-31"]))
        w = _to_weekly_friday(pd.concat([early, late]), ffill_limit=None)
        self.assertFalse(w.isna().any())


class TestSigmaCollapseRegression(unittest.TestCase):
    """Layer 1, the actual CP-05 numbers: a fabricated flat run crushes sigma."""

    def _corrupt_shape(self):
        """Reproduce the September 2026 column: real ISM prints through
        2025-08, an 12-month hole, then a genuine 54.6."""
        hist = _monthly("2023-01-31", [
            47.4, 47.7, 46.5, 47.1, 46.9, 46.0, 46.4, 46.4, 49.0, 46.7, 46.7, 47.4,
            49.1, 47.8, 50.3, 49.2, 48.7, 48.5, 46.8, 47.2, 47.2, 46.5, 48.4, 49.3,
            50.9, 50.3, 49.0, 48.7, 48.5, 49.0, 48.0, 48.7,
        ])
        late = pd.Series([54.6], index=pd.DatetimeIndex(["2026-08-31"]))
        return pd.concat([hist, late])

    def test_unbounded_fill_produces_an_absurd_zscore(self):
        """Documents the bug: the old code really did generate >5 sigma."""
        w = _to_weekly_friday(self._corrupt_shape(), ffill_limit=None)
        z = _rolling_zscore(w).dropna()
        self.assertGreater(z.iloc[-1], 4.0,
                           "unbounded fill should reproduce the CP-05 blow-up")

    def test_bounded_fill_keeps_sigma_realistic(self):
        """With the hole left as NaN, sigma reflects real dispersion."""
        w = _to_weekly_friday(self._corrupt_shape())
        sigma = w.rolling(156, min_periods=52).std().dropna().iloc[-1]
        self.assertGreater(sigma, 1.2,
                           "sigma must not collapse toward a single repeated value")

    def test_backfilled_history_yields_a_credible_zscore(self):
        """The real fix: with the missing months restored, a 54.6 print is a
        normal expansion signal, not a six-sigma event."""
        full = _monthly("2023-01-31", [
            47.4, 47.7, 46.5, 47.1, 46.9, 46.0, 46.4, 46.4, 49.0, 46.7, 46.7, 47.4,
            49.1, 47.8, 50.3, 49.2, 48.7, 48.5, 46.8, 47.2, 47.2, 46.5, 48.4, 49.3,
            50.9, 50.3, 49.0, 48.7, 48.5, 49.0, 48.0, 48.7, 49.1, 48.7, 48.2, 47.9,
            52.6, 52.4, 52.7, 52.7, 54.0, 53.3, 55.6, 54.6,
        ])
        z = _rolling_zscore(_to_weekly_friday(full)).dropna()
        self.assertLess(abs(z.iloc[-1]), 4.0,
                        "a complete history must keep ISM inside the sanity band")


class TestReleaseStore(unittest.TestCase):
    """Layer 2: release points persist across runs."""

    def test_round_trip(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "store.csv")
            self.assertTrue(ism.record_release_point("ISM_MFG_PMI", "2026-08-31", 54.6, "rel-a", path=p))
            self.assertTrue(ism.record_release_point("ISM_MFG_PMI", "2026-07", 55.6, "rel-b", path=p))
            self.assertEqual(ism.history_for_col("ISM_MFG_PMI", path=p),
                             [("2026-07", 55.6), ("2026-08", 54.6)])

    def test_rerecording_same_value_is_a_noop(self):
        """The daily job must not rewrite the file 30 times a month."""
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "store.csv")
            ism.record_release_point("ISM_MFG_PMI", "2026-08-31", 54.6, path=p)
            self.assertFalse(ism.record_release_point("ISM_MFG_PMI", "2026-08-31", 54.6, path=p))

    def test_revision_overwrites_in_place(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "store.csv")
            ism.record_release_point("ISM_MFG_PMI", "2026-08", 54.6, path=p)
            self.assertTrue(ism.record_release_point("ISM_MFG_PMI", "2026-08", 54.8, path=p))
            self.assertEqual(ism.history_for_col("ISM_MFG_PMI", path=p), [("2026-08", 54.8)])

    def test_missing_store_is_not_an_error(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "absent.csv")
            self.assertEqual(ism.load_release_history(path=p), {})
            self.assertEqual(ism.history_for_col("ISM_MFG_PMI", path=p), [])


class TestShippedStoreIntegrity(unittest.TestCase):
    """Layer 2: the seeded store must stay plausible and gap-free."""

    @classmethod
    def setUpClass(cls):
        cls.store = ism.load_release_history()

    def test_covers_the_columns_the_mirror_lost(self):
        for col in ("ISM_MFG_PMI", "ISM_SVC_PMI", "ISM_MFG_NEWORD",
                    "ISM_MFG_INVENTORIES", "ISM_MFG_PRICES"):
            self.assertIn(col, self.store, f"{col} missing from the release store")

    def test_values_are_diffusion_indexes(self):
        """Catches the exact failure mode that started CP-05: a value on the
        wrong scale (the mirror's ~10, or a percentage read as an index)."""
        for col, months in self.store.items():
            for month, val in months.items():
                self.assertTrue(_DIFFUSION_LO <= val <= _DIFFUSION_HI,
                                f"{col} {month}={val} is not a plausible diffusion index")

    def test_no_month_gaps_within_each_column(self):
        """A store with holes would re-open the sigma-collapse hazard."""
        for col, months in self.store.items():
            periods = sorted(pd.Period(m, freq="M") for m in months)
            expected = pd.period_range(periods[0], periods[-1], freq="M")
            self.assertEqual(len(periods), len(expected),
                             f"{col} has month gaps between "
                             f"{periods[0]} and {periods[-1]}")

    def test_store_meets_the_dbnomics_plausibility_band(self):
        """Same band the fetch layer applies to the mirror, applied to us."""
        lib = pd.read_csv("data/macro_library_dbnomics.csv")
        bands = {r.col: (r.plausible_min, r.plausible_max)
                 for r in lib.itertuples() if r.col in self.store}
        for col, months in self.store.items():
            lo, hi = bands.get(col, (None, None))
            if lo is None or pd.isna(lo):
                continue
            for month, val in months.items():
                self.assertTrue(lo <= val <= hi,
                                f"{col} {month}={val} outside [{lo}, {hi}]")


class TestReleaseStoreIsPersisted(unittest.TestCase):
    """Layer 2, the deployment half: the store only works if the daily job
    commits it.

    `record_release_point` writes to the runner's working copy. The daily
    workflow stages an explicit allowlist of paths rather than `git add -A`, so
    a file missing from that list is written every run and thrown away every
    run. The sister archives had exactly this bug until 2026-07-08 and it went
    unnoticed for months, because the happy path is silent — the only symptom
    is history that never accumulates.

    For this store the symptom would be CP-05 coming back: months between the
    last committed row and the current release quietly missing, sigma
    collapsing, and a real print scoring six sigma.
    """

    WORKFLOW = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            ".github", "workflows", "update_data.yml")

    def test_daily_job_stages_the_release_store(self):
        with open(self.WORKFLOW, encoding="utf-8") as fh:
            wf = fh.read()
        staged = re.findall(r"git add -f (\S+)", wf)
        self.assertIn("data/ism_release_history.csv", staged,
                      "the daily job must stage data/ism_release_history.csv, "
                      "or every newly scraped ISM release point is discarded "
                      "when the runner is torn down")

    def test_store_is_not_gitignored(self):
        """A staged-but-ignored file still needs -f; belt and braces."""
        gitignore = os.path.join(os.path.dirname(self.WORKFLOW), "..", "..", ".gitignore")
        gitignore = os.path.normpath(gitignore)
        if not os.path.exists(gitignore):
            self.skipTest("no .gitignore")
        with open(gitignore, encoding="utf-8") as fh:
            patterns = [ln.strip() for ln in fh if ln.strip() and not ln.startswith("#")]
        self.assertNotIn("data/ism_release_history.csv", patterns)


class TestZScoreSanityGuard(unittest.TestCase):
    """Layer 3: an implausible z must be flagged, never silently published."""

    @classmethod
    def setUpClass(cls):
        import compute_macro_market as cmm
        cls.cmm = cmm

    def _snapshot(self, rows):
        return pd.DataFrame(rows)

    def test_flags_the_cp05_reading(self):
        snap = self._snapshot([
            {"id": "US_PMI1", "zscore": 5.89, "zscore_peak_abs_13w": 5.89,
             "raw": 54.6, "last_date": "2026-09-04"},
        ])
        hits = self.cmm.zscore_sanity_warnings(snap)
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0]["id"], "US_PMI1")

    def test_flags_a_peak_even_when_current_z_has_receded(self):
        """The article quoted a 3.63 current z against a 5.75 13-week peak —
        the peak alone has to trip the guard."""
        snap = self._snapshot([
            {"id": "US_PMI1", "zscore": 3.63, "zscore_peak_abs_13w": 5.75,
             "raw": 54.6, "last_date": "2026-09-04"},
        ])
        hits = self.cmm.zscore_sanity_warnings(snap)
        self.assertEqual(len(hits), 1)
        self.assertIn("13w peak", hits[0]["reason"])

    def test_flags_large_negative_z(self):
        snap = self._snapshot([
            {"id": "X", "zscore": -4.8, "zscore_peak_abs_13w": 4.8,
             "raw": 1.0, "last_date": "2026-09-04"},
        ])
        self.assertEqual(len(self.cmm.zscore_sanity_warnings(snap)), 1)

    def test_normal_readings_pass(self):
        snap = self._snapshot([
            {"id": "A", "zscore": 2.30, "zscore_peak_abs_13w": 3.20,
             "raw": 54.6, "last_date": "2026-09-04"},
            {"id": "B", "zscore": -1.9, "zscore_peak_abs_13w": 2.0,
             "raw": 0.0, "last_date": "2026-09-04"},
        ])
        self.assertEqual(self.cmm.zscore_sanity_warnings(snap), [])

    def test_blank_and_missing_values_are_ignored(self):
        """Insufficient-data rows carry '' — they must not crash the guard."""
        snap = self._snapshot([
            {"id": "A", "zscore": "", "zscore_peak_abs_13w": "",
             "raw": "", "last_date": ""},
            {"id": "B", "zscore": np.nan, "zscore_peak_abs_13w": np.nan,
             "raw": "", "last_date": ""},
        ])
        self.assertEqual(self.cmm.zscore_sanity_warnings(snap), [])

    def test_empty_snapshot_is_safe(self):
        self.assertEqual(self.cmm.zscore_sanity_warnings(pd.DataFrame()), [])
        self.assertEqual(self.cmm.zscore_sanity_warnings(None), [])

    def test_threshold_is_configurable(self):
        snap = self._snapshot([
            {"id": "A", "zscore": 2.5, "zscore_peak_abs_13w": 2.5,
             "raw": 1.0, "last_date": "2026-09-04"},
        ])
        self.assertEqual(self.cmm.zscore_sanity_warnings(snap), [])
        self.assertEqual(len(self.cmm.zscore_sanity_warnings(snap, limit=2.0)), 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
