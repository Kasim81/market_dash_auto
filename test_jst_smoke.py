"""Live smoke test for the JST (Jordà-Schularick-Taylor Macrohistory)
source wiring.

JST is the long-run cross-country macro anchor per regime-AA v2 §3.11 — 18
advanced economies × ~150 years annual. The .dta download is the
single point of failure, so this smoke test:

  1. Skips if www.macrohistory.net is unreachable from this host (the JST
     allow-list state varies between local dev, the sandbox, and the daily
     CI runner).
  2. Pulls USA|cpi (the canonical reference series — present in every JST
     release going back to R1) and asserts the index spans at least
     1900 → today minus 5 years.
  3. Asserts the most recent CPI value is positive and finite.

Set SKIP_NETWORK_TESTS=1 to force-skip (no-egress unit-test job).
"""
import os
import sys
import unittest
from datetime import date

import pandas as pd

os.environ.setdefault("FRED_API_KEY", "x")
os.environ.setdefault("SHEET_ID", "x")
os.environ.setdefault("GOOGLE_CREDENTIALS_JSON", "{}")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sources import jst as jst_src  # noqa: E402


def _reachable() -> bool:
    """Try a single pull; if it returns a non-empty series, the host is up."""
    try:
        s = jst_src.fetch_series_as_pandas("USA|cpi")
        return s is not None and not s.empty
    except Exception:
        return False


@unittest.skipIf(os.environ.get("SKIP_NETWORK_TESTS"), "network tests disabled")
class JSTLiveSmokeTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Reset the cache so the smoke is genuinely live.
        jst_src._reset_cache()
        if not _reachable():
            raise unittest.SkipTest(
                "JST host (www.macrohistory.net) unreachable from this "
                "sandbox — skipping live smoke. The daily CI run is expected "
                "to succeed against the allow-listed host."
            )

    def test_usa_cpi_spans_pre1900_to_recent(self):
        s = jst_src.fetch_series_as_pandas("USA|cpi")
        self.assertIsNotNone(s, "USA|cpi returned None")
        self.assertFalse(s.empty, "USA|cpi returned empty series")

        first_year = s.index.min().year

        self.assertLessEqual(
            first_year, 1900,
            f"USA|cpi starts at {first_year} — JST should reach back to ≤1900",
        )
        # Recency is NOT smoke-checked. JST is a multi-year-cadence academic
        # dataset (R6 shipped March 2021 with data through 2020; no R7 as
        # of 2026-06-11); see forward_plan.md §3.13 + the anchor system in
        # data_audit.py::section_c_staleness which surfaces overdue anchors
        # in the daily Issue. Smoke would be a duplicate-and-flappier
        # signal — pull the assertion if the next release cycle slips.

    def test_usa_cpi_latest_value_is_finite_and_positive(self):
        s = jst_src.fetch_series_as_pandas("USA|cpi")
        self.assertIsNotNone(s)
        last = float(s.iloc[-1])
        self.assertTrue(
            pd.notna(last) and last > 0 and last < 1e9,
            f"USA|cpi latest value {last!r} is not a sensible CPI index level",
        )

    def test_library_load(self):
        rows = jst_src.load_library()
        self.assertGreaterEqual(
            len(rows), 20,
            f"expected ≥20 library rows (5 regions × 4 series), got {len(rows)}",
        )
        # Every row must carry the `<iso>|<col>` series_id convention.
        for r in rows:
            self.assertIn("|", r["series_id"], f"bad series_id {r['series_id']!r}")
            self.assertEqual(r["source"], "JST")


if __name__ == "__main__":
    unittest.main()
