"""Regression tests for fetch_macro_economic.build_hist_df freshness merge.

The pipeline loads indicators from 12+ sources, several of which target the
same column name (e.g. JPN_POLICY_RATE on FRED, DB.nomics and BoJ). The merge
in build_hist_df must pick the source whose raw series has the most recent
non-null observation — not whichever source happened to load last.
"""
import os
import sys
import unittest

import pandas as pd

os.environ.setdefault("FRED_API_KEY", "x")
os.environ.setdefault("SHEET_ID", "x")
os.environ.setdefault("GOOGLE_CREDENTIALS_JSON", "{}")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fetch_macro_economic as fme  # noqa: E402


def _indic(source: str, col: str, series: pd.Series, country: str = "JPN") -> dict:
    return {
        "source": source,
        "col": col,
        "country": country,
        "source_id": f"{source}_{col}",
        "name": col,
        "category": "",
        "subcategory": "",
        "concept": "",
        "cycle_timing": "",
        "units": "",
        "frequency": "",
        "notes": "",
        "_series": {col if country else col: series},
    }


class HistMergeFreshnessTest(unittest.TestCase):
    def setUp(self):
        self._orig_hist_for = fme._history_for_indicator
        self._orig_spine = fme.build_friday_spine
        self._orig_start = fme.HIST_START
        fme._history_for_indicator = lambda indic, ifo: indic["_series"]
        fme.build_friday_spine = lambda a, b: pd.date_range(
            "2024-01-05", "2024-02-23", freq="W-FRI"
        )

    def tearDown(self):
        fme._history_for_indicator = self._orig_hist_for
        fme.build_friday_spine = self._orig_spine
        fme.HIST_START = self._orig_start

    def _series(self, dates: list[str], values: list[float]) -> pd.Series:
        return pd.Series(values, index=pd.to_datetime(dates))

    def test_fresher_source_wins_when_loaded_first(self):
        # BoJ has data through 2024-02-16; FRED frozen at 2024-01-12.
        # BoJ loads FIRST — must still own the column after FRED comes through.
        boj = self._series(
            ["2024-01-05", "2024-01-26", "2024-02-16"], [0.25, 0.5, 0.5]
        )
        fred = self._series(["2024-01-05", "2024-01-12"], [0.1, 0.1])
        df, prov = fme.build_hist_df([
            _indic("BoJ", "JPN_POLICY_RATE", boj),
            _indic("FRED", "JPN_POLICY_RATE", fred),
        ])
        self.assertEqual(prov["JPN_POLICY_RATE"]["source"], "BoJ")
        self.assertEqual(df["JPN_POLICY_RATE"].iloc[-1], 0.5)

    def test_fresher_source_wins_when_loaded_last(self):
        # Same data, reverse load order. Same winner.
        boj = self._series(
            ["2024-01-05", "2024-01-26", "2024-02-16"], [0.25, 0.5, 0.5]
        )
        fred = self._series(["2024-01-05", "2024-01-12"], [0.1, 0.1])
        df, prov = fme.build_hist_df([
            _indic("FRED", "JPN_POLICY_RATE", fred),
            _indic("BoJ", "JPN_POLICY_RATE", boj),
        ])
        self.assertEqual(prov["JPN_POLICY_RATE"]["source"], "BoJ")
        self.assertEqual(df["JPN_POLICY_RATE"].iloc[-1], 0.5)

    def test_stale_source_does_not_overwrite_fresh(self):
        # Tie-break rule: when incoming is not strictly newer, existing wins.
        # FRED frozen 2024-01-12 must not overwrite BoJ fresh to 2024-02-16,
        # even if FRED's series carries more rows pre-freeze.
        boj = self._series(["2024-02-09", "2024-02-16"], [0.5, 0.5])
        fred = self._series(
            ["2024-01-05", "2024-01-12"] * 1, [0.1, 0.1]
        )
        df, prov = fme.build_hist_df([
            _indic("BoJ", "JPN_POLICY_RATE", boj),
            _indic("FRED", "JPN_POLICY_RATE", fred),
        ])
        self.assertEqual(prov["JPN_POLICY_RATE"]["source"], "BoJ")

    def test_tie_existing_wins(self):
        # Identical last observation → first to register keeps the column.
        a = self._series(["2024-02-09", "2024-02-16"], [1.0, 1.0])
        b = self._series(["2024-02-09", "2024-02-16"], [2.0, 2.0])
        _, prov = fme.build_hist_df([
            _indic("FRED", "X", a),
            _indic("DB.nomics", "X", b),
        ])
        self.assertEqual(prov["X"]["source"], "FRED")

    def test_metadata_reflects_winner(self):
        # The Source / Series ID metadata rows must describe the *winning*
        # source, not whatever source loaded last (the prior bug).
        boj = self._series(["2024-02-16"], [0.5])
        fred = self._series(["2024-01-12"], [0.1])
        _, prov = fme.build_hist_df([
            _indic("FRED", "JPN_POLICY_RATE", fred),
            _indic("BoJ", "JPN_POLICY_RATE", boj),
        ])
        rows = fme._build_hist_metadata_rows(["JPN_POLICY_RATE"], prov)
        labels = [r[0] for r in rows]
        self.assertEqual(rows[labels.index("Source")][1], "BoJ")
        self.assertEqual(rows[labels.index("Series ID")][1], "BoJ_JPN_POLICY_RATE")


if __name__ == "__main__":
    unittest.main()
