"""Deterministic (offline) regression tests for the Atlanta Fed GDPNow parser.

These guard the two bugs fixed in the 2026-06-17 GDPNow repointing:

  1. The headline series was taken as the *rightmost non-null cell* on a
     TrackingArchives row. The Tracking tabs carry ~30 columns; once the BEA
     advance estimate publishes, the rightmost numeric cell is the
     ``Forecast Error`` column, so a ~0.75 forecast-error shipped as the
     headline nowcast. The parser must select the explicit ``GDP Nowcast``
     column by name.
  2. The live, in-flight quarter lives in the ``CurrentQtrEvolution`` tab
     (paired ``Date``/``GDP*`` column blocks), which the headline-tab allowlist
     excluded — so the regenerated series stopped at the prior quarter's advance
     release and lost the current ~3% nowcast.

No network: synthetic DataFrames shaped like the real workbook tabs.
"""
import os
import sys
import unittest

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sources import atlanta_fed as af  # noqa: E402


def _tracking_frame() -> pd.DataFrame:
    """A TrackingArchives-shaped frame: a real ``GDP Nowcast`` column plus the
    trailing evaluation columns whose rightmost cell is the forecast error."""
    return pd.DataFrame({
        "Forecast Date": ["2026-04-21", "2026-04-29"],
        "PCE": [1.40, 1.40],
        "GDP Nowcast": [1.241028, 1.239175],
        "Final Sales": [0.864199, 0.587980],
        "Advance Estimate From BEA": [1.9901, 1.9901],
        "Days until advance estimate": [9, 1],
        "Forecast Error": [0.749072, 0.750925],  # rightmost numeric — the trap
        "Data releases": ["Retail trade", "Advance Manufacturing"],
    })


def _current_qtr_frame() -> pd.DataFrame:
    """A CurrentQtrEvolution-shaped frame: two side-by-side (Date, Major
    Releases, GDP*) blocks, the second carrying the most-recent observations."""
    return pd.DataFrame({
        "Date": pd.to_datetime(["2026-04-30", "2026-05-15", "2026-05-21"]),
        "Major Releases": ["Initial", "IP", "Housing starts"],
        "GDP*": [3.70, 4.30, 4.26],
        "Date.1": pd.to_datetime(["2026-06-15", "2026-06-17", pd.NaT]),
        "Major Releases.1": ["IP", "Retail sales", None],
        "GDP*.1": [3.02, 3.04, np.nan],
    })


class NowcastColumnSelectionTest(unittest.TestCase):
    def test_selects_gdp_nowcast_not_forecast_error(self):
        s = af._extract_headline_series_from_sheet(_tracking_frame())
        self.assertIsNotNone(s)
        last = float(s.loc[pd.Timestamp("2026-04-29")])
        self.assertAlmostEqual(last, 1.239175, places=5)
        # The forecast-error trap value must NOT be what we picked.
        self.assertNotAlmostEqual(last, 0.750925, places=5)

    def test_find_nowcast_column_matches_header_variants(self):
        for header in ("GDP Nowcast", "gdp nowcast", "GDPNow"):
            df = pd.DataFrame({"Forecast Date": ["2026-04-29"], header: [1.23]})
            self.assertEqual(af._find_nowcast_column(df), header)


class CurrentQuarterTabTest(unittest.TestCase):
    def test_pairs_blocks_and_takes_latest(self):
        s = af._extract_current_quarter_series(_current_qtr_frame())
        self.assertIsNotNone(s)
        # Latest publication date across both blocks is 2026-06-17.
        self.assertEqual(s.index.max(), pd.Timestamp("2026-06-17"))
        self.assertAlmostEqual(float(s.iloc[-1]), 3.04, places=5)
        # Both blocks contribute observations.
        self.assertIn(pd.Timestamp("2026-04-30"), s.index)
        self.assertIn(pd.Timestamp("2026-06-15"), s.index)

    def test_returns_none_for_non_current_quarter_layout(self):
        # A Tracking frame has no Date/GDP* pair, so the current-quarter
        # extractor must decline and let the headline-column path handle it.
        self.assertIsNone(af._extract_current_quarter_series(_tracking_frame()))

    def test_dispatch_prefers_current_quarter_layout(self):
        s = af._extract_headline_series_from_sheet(_current_qtr_frame())
        self.assertIsNotNone(s)
        self.assertEqual(s.index.max(), pd.Timestamp("2026-06-17"))


class FallbackAndClampTest(unittest.TestCase):
    def test_fallback_rightmost_for_unknown_layout(self):
        # No GDP Nowcast / GDP* marker → fallback to rightmost non-null.
        df = pd.DataFrame({
            "Date": pd.to_datetime(["2020-01-03", "2020-01-10"]),
            "OnlyValue": [2.5, 3.1],
        })
        s = af._extract_headline_series_from_sheet(df)
        self.assertIsNotNone(s)
        self.assertAlmostEqual(float(s.iloc[-1]), 3.1, places=5)

    def test_plausibility_band_filters_garbage(self):
        df = pd.DataFrame({
            "Forecast Date": pd.to_datetime(["2020-01-03", "2020-01-10"]),
            "GDP Nowcast": [3.1, 999.0],  # 999 is not a growth rate
        })
        s = af._extract_headline_series_from_sheet(df)
        self.assertIsNotNone(s)
        self.assertNotIn(999.0, list(s.values))
        self.assertEqual(s.index.max(), pd.Timestamp("2020-01-03"))


class HeadlineSheetAllowlistTest(unittest.TestCase):
    def test_allows_headline_tabs(self):
        for name in ("TrackingArchives", "TrackingDeepArchives",
                     "CurrentQtrEvolution", "2026Q3", "Q3 2026"):
            self.assertTrue(af._is_headline_sheet(name), name)

    def test_excludes_subcomponent_and_scorecard_tabs(self):
        for name in ("StateLocal", "Contributions", "TrackRecord",
                     "ContribArchives", "25Q1TrackingHistoryGold", "ReadMe",
                     "Table", "Factor"):
            self.assertFalse(af._is_headline_sheet(name), name)


if __name__ == "__main__":
    unittest.main()
