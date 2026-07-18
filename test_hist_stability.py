"""
test_hist_stability.py — C11 hist append-stability (offline gate).

Pins the two mechanisms that collapse daily hist-CSV churn from ~100 % of lines
to only genuinely-changed cells:

  1. stable_hist_column_order — an existing file's physical column order is
     preserved and only new columns are appended, so the non-deterministic
     fan-out column order can no longer rewrite the whole file each run.
  2. canonical float_format in _write_hist_payload — the same value serialises
     identically run-to-run (kills last-ULP repr wobble), so re-writing
     unchanged history is byte-identical.

Network-free: a synthetic hist file in a temp dir for the mechanics, plus a
real-data guard over the committed macro_economic_hist.csv.
"""

import csv
import os
import pathlib
import tempfile
import unittest

import pandas as pd

import library_utils as lu


class TestStableColumnOrder(unittest.TestCase):
    def _write_hist(self, path, header, date_col="Date"):
        # minimal hist file: 1 prefix row + header + 1 data row
        with open(path, "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["Last Updated"] + [""] * (len(header) - 1))
            w.writerow(header)
            w.writerow([("2020-01-03" if c == date_col else "1.0") for c in header])

    def test_no_existing_file_keeps_caller_order(self):
        cols = ["B", "A", "C"]
        self.assertEqual(lu.stable_hist_column_order("/does/not/exist.csv", cols), cols)

    def test_existing_order_preserved_new_appended(self):
        d = tempfile.mkdtemp()
        p = os.path.join(d, "x_hist.csv")
        self._write_hist(p, ["Date", "GBP", "USD", "EUR"])
        # incoming columns shuffled + one new; existing keep file order, new → end
        out = lu.stable_hist_column_order(p, ["EUR", "JPY", "USD", "GBP"], date_col="Date")
        self.assertEqual(out, ["GBP", "USD", "EUR", "JPY"])

    def test_dropped_column_falls_away(self):
        d = tempfile.mkdtemp()
        p = os.path.join(d, "x_hist.csv")
        self._write_hist(p, ["Date", "A", "B", "C"])
        out = lu.stable_hist_column_order(p, ["C", "A"], date_col="Date")
        self.assertEqual(out, ["A", "C"])       # B gone, A/C keep file order


class TestWriterStability(unittest.TestCase):
    def test_idempotent_and_float_canonical(self):
        d = tempfile.mkdtemp()
        p = pathlib.Path(d) / "x_hist.csv"
        prefix = [["Last Updated", "", ""]]
        # a value with full-precision wobble that %.8g must canonicalise
        df = pd.DataFrame({"Date": ["2020-01-03", "2020-01-10"],
                           "A": [102.05590000000001, 1.0 / 3.0],
                           "B": [147119.0, 2.5]})
        lu._write_hist_payload(str(p), df, prefix, "Date")
        first = p.read_text()
        # re-read and re-write → must be byte-identical
        df2 = pd.read_csv(p, skiprows=len(prefix))
        lu._write_hist_payload(str(p), df2, prefix, "Date")
        self.assertEqual(first, p.read_text(), "writer is not idempotent")
        # canonical precision: 8 sig figs, no 15-digit tails
        self.assertIn("102.0559", first)
        self.assertNotIn("102.05590000", first)

    def test_value_fidelity_within_precision(self):
        d = tempfile.mkdtemp()
        p = pathlib.Path(d) / "x_hist.csv"
        df = pd.DataFrame({"Date": ["2020-01-03"], "A": [123.456789012],
                           "B": [0.000123456789]})
        lu._write_hist_payload(str(p), df, None, "Date")
        back = pd.read_csv(p)
        for c in ("A", "B"):
            rel = abs(back[c].iloc[0] - df[c].iloc[0]) / abs(df[c].iloc[0])
            self.assertLess(rel, 1e-7, f"{c} lost too much precision")


class TestRealMacroEconomicHist(unittest.TestCase):
    PATH = "data/macro_economic_hist.csv"

    def test_shuffled_input_restores_committed_order(self):
        if not os.path.exists(self.PATH):
            self.skipTest("committed macro_economic_hist.csv absent")
        n = lu.sniff_hist_prefix_rows(self.PATH, "Date")
        with open(self.PATH, newline="") as f:
            header = list(csv.reader(f))[n]
        data_cols = [c for c in header if c != "Date"]
        import random
        shuffled = data_cols[:]
        random.Random(7).shuffle(shuffled)
        restored = lu.stable_hist_column_order(self.PATH, shuffled, date_col="Date")
        self.assertEqual(restored, data_cols,
                         "committed column order not restored from a shuffled run")


if __name__ == "__main__":
    unittest.main()
