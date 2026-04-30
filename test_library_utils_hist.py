"""Unit tests for library_utils.write_hist_with_archive / load_hist_with_archive.

Covers the §3.1.1 history-preservation contract:
  - First write with no live file (no shrinkage to detect).
  - Rolling-window source: row count stable, earliest date walks forward → archive triggers.
  - Pure extension (new latest date appended): no archive.
  - Mixed columns: only rolling columns trigger archive; stable columns leave sister untouched.
  - Sister is append-only and deduped by date.
  - load_hist_with_archive unions live + sister with live winning on overlap.
"""
import os
import shutil
import tempfile
import unittest

import pandas as pd

from library_utils import (
    write_hist_with_archive,
    load_hist_with_archive,
    _sister_path,
)


class HistArchiveTest(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.path = os.path.join(self.tmpdir, "x_hist.csv")
        self.sister = _sister_path(self.path)

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    @staticmethod
    def _df(dates, ice=None, fred=None):
        d = {"Date": pd.to_datetime(dates)}
        if ice is not None:
            d["ICE_HY"] = ice
        if fred is not None:
            d["FRED_T10Y"] = fred
        return pd.DataFrame(d)

    def test_first_write_no_sister(self):
        df = self._df(["2020-01-01", "2020-02-01", "2020-03-01"], ice=[4.5, 4.6, 4.7])
        write_hist_with_archive(df, self.path)
        self.assertTrue(os.path.exists(self.path))
        self.assertFalse(os.path.exists(self.sister))

    def test_rolling_window_triggers_archive(self):
        # T0: live has 5 months of ICE_HY
        write_hist_with_archive(
            self._df(["2020-01-01", "2020-02-01", "2020-03-01", "2020-04-01", "2020-05-01"],
                     ice=[1.0, 2.0, 3.0, 4.0, 5.0]),
            self.path,
        )
        # T1: source rolls forward by 2 months — same row count, floor advances
        write_hist_with_archive(
            self._df(["2020-03-01", "2020-04-01", "2020-05-01", "2020-06-01", "2020-07-01"],
                     ice=[3.0, 4.0, 5.0, 6.0, 7.0]),
            self.path,
        )
        self.assertTrue(os.path.exists(self.sister))
        sister_df = pd.read_csv(self.sister)
        sister_df["Date"] = pd.to_datetime(sister_df["Date"])
        # Sister should hold the two displaced rows (2020-01 and 2020-02)
        self.assertEqual(sorted(sister_df["Date"].dt.strftime("%Y-%m-%d").tolist()),
                         ["2020-01-01", "2020-02-01"])
        self.assertEqual(sorted(sister_df["ICE_HY"].tolist()), [1.0, 2.0])

    def test_pure_extension_no_archive(self):
        write_hist_with_archive(
            self._df(["2020-01-01", "2020-02-01"], ice=[1.0, 2.0]),
            self.path,
        )
        write_hist_with_archive(
            self._df(["2020-01-01", "2020-02-01", "2020-03-01"], ice=[1.0, 2.0, 3.0]),
            self.path,
        )
        self.assertFalse(os.path.exists(self.sister),
                         "sister should not exist when earliest date is unchanged")

    def test_mixed_columns_only_rolling_archived(self):
        # Live: FRED stable from 2010, ICE from 2010 too
        write_hist_with_archive(
            self._df(["2010-01-01", "2015-01-01", "2020-01-01"],
                     ice=[1.0, 2.0, 3.0],
                     fred=[10.0, 11.0, 12.0]),
            self.path,
        )
        # New: FRED still from 2010 (stable), ICE rolls to start at 2020-01-01
        write_hist_with_archive(
            self._df(["2010-01-01", "2015-01-01", "2020-01-01"],
                     ice=[None, None, 3.0],
                     fred=[10.0, 11.0, 12.0]),
            self.path,
        )
        # ICE rolled forward 10 years; archive should hold rows where ICE was non-null
        # in the dropped range [2010-01-01, 2020-01-01)
        self.assertTrue(os.path.exists(self.sister))
        sister_df = pd.read_csv(self.sister)
        sister_df["Date"] = pd.to_datetime(sister_df["Date"])
        self.assertEqual(sorted(sister_df["Date"].dt.strftime("%Y-%m-%d").tolist()),
                         ["2010-01-01", "2015-01-01"])
        # Both rows in the archive carry ICE_HY (the rolling column) plus FRED_T10Y
        # values from the original live (incidentally captured — that's fine).
        self.assertEqual(sorted(sister_df["ICE_HY"].tolist()), [1.0, 2.0])

    def test_sister_append_only(self):
        # First roll
        write_hist_with_archive(
            self._df(["2020-01-01", "2020-02-01", "2020-03-01"], ice=[1.0, 2.0, 3.0]),
            self.path,
        )
        write_hist_with_archive(
            self._df(["2020-02-01", "2020-03-01", "2020-04-01"], ice=[2.0, 3.0, 4.0]),
            self.path,
        )
        # Sister has 2020-01-01
        df1 = pd.read_csv(self.sister)
        # Second roll — another month displaced
        write_hist_with_archive(
            self._df(["2020-03-01", "2020-04-01", "2020-05-01"], ice=[3.0, 4.0, 5.0]),
            self.path,
        )
        df2 = pd.read_csv(self.sister)
        df2["Date"] = pd.to_datetime(df2["Date"])
        self.assertEqual(sorted(df2["Date"].dt.strftime("%Y-%m-%d").tolist()),
                         ["2020-01-01", "2020-02-01"])
        self.assertEqual(sorted(df2["ICE_HY"].tolist()), [1.0, 2.0])

    def test_load_unions_live_and_sister(self):
        write_hist_with_archive(
            self._df(["2020-01-01", "2020-02-01", "2020-03-01", "2020-04-01"],
                     ice=[1.0, 2.0, 3.0, 4.0]),
            self.path,
        )
        write_hist_with_archive(
            self._df(["2020-03-01", "2020-04-01", "2020-05-01", "2020-06-01"],
                     ice=[3.0, 4.0, 5.0, 6.0]),
            self.path,
        )
        unioned = load_hist_with_archive(self.path)
        unioned["Date"] = pd.to_datetime(unioned["Date"])
        self.assertEqual(unioned["Date"].dt.strftime("%Y-%m-%d").tolist(),
                         ["2020-01-01", "2020-02-01", "2020-03-01",
                          "2020-04-01", "2020-05-01", "2020-06-01"])
        self.assertEqual(unioned["ICE_HY"].tolist(), [1.0, 2.0, 3.0, 4.0, 5.0, 6.0])

    def test_load_no_sister_returns_live(self):
        write_hist_with_archive(
            self._df(["2020-01-01", "2020-02-01"], ice=[1.0, 2.0]),
            self.path,
        )
        df = load_hist_with_archive(self.path)
        self.assertEqual(len(df), 2)

    def test_prefix_rows_preserved(self):
        prefix = [["MetaA", "alpha", "beta"], ["MetaB", "gamma", "delta"]]
        write_hist_with_archive(
            self._df(["2020-01-01", "2020-02-01"], ice=[1.0, 2.0]),
            self.path,
            prefix_rows=prefix,
        )
        with open(self.path) as f:
            head = [next(f) for _ in range(2)]
        self.assertIn("MetaA", head[0])
        self.assertIn("MetaB", head[1])
        # Roll forward → archive
        write_hist_with_archive(
            self._df(["2020-02-01", "2020-03-01"], ice=[2.0, 3.0]),
            self.path,
            prefix_rows=prefix,
        )
        with open(self.sister) as f:
            head = [next(f) for _ in range(2)]
        self.assertIn("MetaA", head[0])
        self.assertIn("MetaB", head[1])

    def test_invalid_path(self):
        with self.assertRaises(ValueError):
            _sister_path("data/foo.csv")


if __name__ == "__main__":
    unittest.main()
