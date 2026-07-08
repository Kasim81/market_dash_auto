"""Offline regression tests for the 2026-07-08 bounded-fill change.

Covers the three layers of the change:

  1. Writer — fetch_macro_economic._bounded_spine_fill: forward-fill onto
     the Friday spine is capped at each series' fill limit (2x its
     staleness tolerance), measured in days against the *raw* observation
     dates. Interior step-fill between prints is unchanged; a dead series
     visibly ends instead of flatlining forever.
  2. Archive — library_utils sister handling: trailing_bounds clears
     fabricated fill cells from the sister (exactly those beyond
     last-real-obs + limit) while preserving real history; header sniffing
     lets 14-row and 15-row metadata generations coexist.
  3. Consumers — compute_macro_market._to_weekly_friday must not
     re-fabricate the trailing NaNs the writer leaves.

No network, no API keys — runs in the ci.yml offline gate.
"""
import os
import shutil
import sys
import tempfile
import unittest

import pandas as pd

os.environ.setdefault("FRED_API_KEY", "x")
os.environ.setdefault("SHEET_ID", "x")
os.environ.setdefault("GOOGLE_CREDENTIALS_JSON", "{}")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fetch_macro_economic as fme  # noqa: E402
import library_utils as lu  # noqa: E402
import compute_macro_market as cmm  # noqa: E402


def _spine(start, end):
    return pd.date_range(start, end, freq="W-FRI")


class BoundedSpineFillTest(unittest.TestCase):
    def test_interior_fill_unchanged_within_bound(self):
        # Monthly prints; the weeks between prints must fill as before.
        s = pd.Series([1.0, 2.0], index=pd.to_datetime(["2024-01-01", "2024-02-01"]))
        spine = _spine("2024-01-01", "2024-02-09")
        out = fme._bounded_spine_fill(s, spine, limit_days=90)
        # Fridays of January carry the January print; Feb Fridays the Feb print.
        self.assertEqual(out["2024-01-19"], 1.0)
        self.assertEqual(out["2024-02-09"], 2.0)
        self.assertFalse(out.isna().any())

    def test_trailing_fill_stops_at_bound(self):
        # A series that dies keeps filling only for limit_days, then NaN.
        s = pd.Series([5.0], index=pd.to_datetime(["2024-01-01"]))
        spine = _spine("2024-01-01", "2024-12-27")
        out = fme._bounded_spine_fill(s, spine, limit_days=90)
        self.assertEqual(out["2024-03-29"], 5.0)   # 88d old — kept
        self.assertTrue(pd.isna(out["2024-04-05"]))  # 95d old — cleared
        self.assertTrue(out.loc["2024-04-05":].isna().all())

    def test_interior_gap_beyond_bound_also_clears(self):
        # A 6-month hole in a monthly series must not be filled through.
        s = pd.Series([1.0, 9.0],
                      index=pd.to_datetime(["2024-01-01", "2024-08-01"]))
        spine = _spine("2024-01-01", "2024-08-30")
        out = fme._bounded_spine_fill(s, spine, limit_days=90)
        self.assertTrue(pd.isna(out["2024-06-07"]))  # inside the hole, >90d
        self.assertEqual(out["2024-08-30"], 9.0)     # resumes on new data

    def test_leading_nans_preserved(self):
        s = pd.Series([2.0], index=pd.to_datetime(["2024-06-03"]))
        spine = _spine("2024-01-05", "2024-07-05")
        out = fme._bounded_spine_fill(s, spine, limit_days=90)
        self.assertTrue(out.loc[:"2024-05-31"].isna().all())
        self.assertEqual(out["2024-06-07"], 2.0)

    def test_fill_limit_days_from_override_and_defaults(self):
        self.assertEqual(fme._fill_limit_days(
            {"freshness_override_days": 120, "frequency": "Daily"}), 240)
        # No override → 2x the per-frequency default from freshness_thresholds.csv
        self.assertEqual(fme._fill_limit_days(
            {"freshness_override_days": None, "frequency": "Monthly"}), 90)
        self.assertEqual(fme._fill_limit_days(
            {"freshness_override_days": None, "frequency": "Annual"}), 1080)
        # Unknown frequency → 2x the 45d fallback
        self.assertEqual(fme._fill_limit_days(
            {"freshness_override_days": None, "frequency": ""}), 90)


class SnifferTest(unittest.TestCase):
    def _write(self, lines):
        fd, path = tempfile.mkstemp(suffix="_hist.csv")
        with os.fdopen(fd, "w") as f:
            f.write("\n".join(lines) + "\n")
        self.addCleanup(os.unlink, path)
        return path

    def test_sniffs_macro_layout(self):
        path = self._write(["Column ID,A", "Frequency,Monthly", "Date,A",
                            "2024-01-05,1.0"])
        self.assertEqual(lu.sniff_hist_prefix_rows(path), 2)

    def test_sniffs_comp_layout_row_id_first(self):
        path = self._write(["ticker,X", "row_id,Date,X", "1,2024-01-05,1.0"])
        self.assertEqual(lu.sniff_hist_prefix_rows(path), 1)

    def test_no_header_returns_none(self):
        path = self._write(["a,b", "1,2"])
        self.assertIsNone(lu.sniff_hist_prefix_rows(path))


class SisterTrailingBoundTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.dir)
        self.live = os.path.join(self.dir, "unit_hist.csv")
        self.prefix = [["Column ID", "A", "B"], ["Frequency", "Monthly", "Monthly"]]

    def _df(self, dates, a, b):
        return pd.DataFrame({"Date": pd.to_datetime(dates), "A": a, "B": b})

    def _read_sister(self):
        sister = self.live[:-len("_hist.csv")] + "_hist_x.csv"
        n = lu.sniff_hist_prefix_rows(sister)
        return pd.read_csv(sister, skiprows=n)

    def test_fabricated_sister_cells_cleared_real_history_kept(self):
        # Seed: a sister full of pre-change fabricated fill for column A
        # (real obs 2024-01-05, fill repeated to 2024-12-27) while B stays live.
        dates = pd.date_range("2024-01-05", "2024-12-27", freq="W-FRI")
        seed = self._df(dates, [3.0] * len(dates), range(len(dates)))
        lu.write_hist_with_archive(seed, self.live, prefix_rows=self.prefix)

        # Post-change write: A's last real obs is 2024-01-05, limit 90d.
        new = self._df(dates, [3.0] + [float("nan")] * (len(dates) - 1),
                       range(len(dates)))
        lu.write_hist_with_archive(
            new, self.live, prefix_rows=self.prefix,
            trailing_bounds={"A": ("2024-01-05", 90)},
        )
        sis = self._read_sister()
        sis["Date"] = pd.to_datetime(sis["Date"])
        beyond = sis[sis["Date"] > pd.Timestamp("2024-01-05") + pd.Timedelta(days=90)]
        within = sis[sis["Date"] <= pd.Timestamp("2024-01-05") + pd.Timedelta(days=90)]
        self.assertTrue(beyond["A"].isna().all(),
                        "fabricated fill beyond the bound must be cleared")
        self.assertTrue(within["A"].notna().all(),
                        "real observation and in-bound fill must be preserved")
        self.assertTrue(sis["B"].notna().all(),
                        "unbounded columns must be untouched")

    def test_sister_with_older_prefix_generation_still_parses(self):
        # Sister written with a 2-row prefix; a later write arrives with a
        # 3-row prefix (the metadata block grew). The append must sniff the
        # sister's own generation rather than misparse.
        dates = ["2024-01-05", "2024-01-12"]
        lu.write_hist_with_archive(self._df(dates, [1.0, 2.0], [1, 2]),
                                   self.live, prefix_rows=self.prefix)
        new_prefix = self.prefix + [["Last Observation", "2024-01-12", "2024-01-12"]]
        lu.write_hist_with_archive(
            self._df(["2024-01-05", "2024-01-12", "2024-01-19"],
                     [1.0, 2.0, 3.0], [1, 2, 3]),
            self.live, prefix_rows=new_prefix,
        )
        sis = self._read_sister()
        self.assertEqual(len(sis), 3)
        self.assertEqual(list(sis.columns), ["Date", "A", "B"])


class ToWeeklyFridayTest(unittest.TestCase):
    def test_trailing_nans_not_refabricated(self):
        # A hist column with bounded-fill NaNs at the tail: the helper must
        # return a series ending at the last real value, not refill to the end.
        idx = pd.date_range("2024-01-05", "2024-06-28", freq="W-FRI")
        vals = [1.0] * 10 + [float("nan")] * (len(idx) - 10)
        s = pd.Series(vals, index=idx)
        out = cmm._to_weekly_friday(s)
        self.assertEqual(out.index.max(), idx[9])
        self.assertFalse(out.isna().any())

    def test_interior_monthly_fill_still_works(self):
        s = pd.Series([1.0, 2.0], index=pd.to_datetime(["2024-01-01", "2024-02-01"]))
        out = cmm._to_weekly_friday(s)
        self.assertEqual(out["2024-01-19"], 1.0)
        self.assertEqual(out.iloc[-1], 2.0)


if __name__ == "__main__":
    unittest.main()


class SectionCLastObservationTest(unittest.TestCase):
    """forward_plan §2.A A15 — data_audit.load_macro_hist prefers the
    'Last Observation' metadata row (writer ground truth) and falls back to
    value-change archaeology when the row is absent or the cell is blank."""

    def setUp(self):
        import data_audit
        from pathlib import Path
        self.da = data_audit
        self._orig_data = data_audit.DATA
        self.dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.dir)
        data_audit.DATA = Path(self.dir)
        self.addCleanup(setattr, data_audit, "DATA", self._orig_data)

    def _write_hist(self, lines):
        with open(os.path.join(self.dir, "macro_economic_hist.csv"), "w") as f:
            f.write("\n".join(lines) + "\n")

    # HELD is a constant-valued live series (e.g. a held policy rate):
    # archaeology dates it at its last value CHANGE (2024-01-05), but the
    # writer knows real observations kept arriving (Last Observation
    # 2024-03-01). DEAD is a genuinely dead series with fill.
    _BASE = [
        "Column ID,HELD,DEAD",
        "Series ID,H1,D1",
        "Source,BoC,FRED",
        "Frequency,Daily,Monthly",
    ]
    _DATA = [
        "Date,HELD,DEAD",
        "2024-01-05,2.25,1.0",
        "2024-02-02,2.25,1.0",
        "2024-03-01,2.25,1.0",
    ]

    def test_metadata_row_wins_over_archaeology(self):
        self._write_hist(self._BASE
                         + ["Last Observation,2024-03-01,2024-01-05"]
                         + self._DATA)
        out = {r["col_id"]: r for r in self.da.load_macro_hist()}
        self.assertEqual(out["HELD"]["last_obs"], "2024-03-01",
                         "held-rate real obs date must come from metadata")
        self.assertEqual(out["DEAD"]["last_obs"], "2024-01-05")

    def test_blank_metadata_cell_falls_back_to_archaeology(self):
        self._write_hist(self._BASE
                         + ["Last Observation,,2024-01-05"]
                         + self._DATA)
        out = {r["col_id"]: r for r in self.da.load_macro_hist()}
        # archaeology: HELD's last value change is the first data row
        self.assertEqual(out["HELD"]["last_obs"], "2024-01-05")

    def test_old_generation_without_row_falls_back(self):
        self._write_hist(self._BASE + self._DATA)
        out = {r["col_id"]: r for r in self.da.load_macro_hist()}
        self.assertEqual(out["HELD"]["last_obs"], "2024-01-05")
        self.assertEqual(out["DEAD"]["last_obs"], "2024-01-05")
