"""Offline tests for data_audit's Section F CRITICAL gate (§2.C C8).

The audit is a warning channel except for this one deliberately-narrow class:
(a) a protected-tab output CSV with zero populated value cells, and (b) a
hist CSV that lost >10% of rows/columns vs the committed HEAD version. These
tests pin both detectors — and, just as importantly, pin that the *current
repo state does not trigger them* (the gate must be hard to false-fire).

No network, no API keys — runs in the ci.yml offline gate. Uses a throwaway
git repo in tmp for the shrink-vs-HEAD checks (stdlib + git only).
"""
import csv
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import data_audit as da  # noqa: E402


def _write_csv(path: Path, rows: list[list[str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as f:
        csv.writer(f, lineterminator="\n").writerows(rows)


def _market_rows(n_rows=5, populated=True):
    rows = [["row_id", "Symbol", "Name", "Currency", "Last Price", "Local Perf 1W"]]
    for i in range(n_rows):
        val = ["101.5", "0.2"] if populated else ["", ""]
        rows.append([str(i + 1), f"TK{i}", f"Ticker {i}", "USD"] + val)
    return rows


def _hist_rows(n_data_rows=100, n_cols=10):
    header = ["Date"] + [f"C{i}" for i in range(n_cols - 1)]
    rows = [header]
    for i in range(n_data_rows):
        rows.append([f"2026-{(i % 12) + 1:02d}-01"] + ["1.0"] * (n_cols - 1))
    return rows


class CriticalGateTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="audit_crit_test_"))
        self._old_root, self._old_data = da.ROOT, da.DATA
        da.ROOT = self.tmp
        da.DATA = self.tmp / "data"
        da.DATA.mkdir()
        subprocess.run(["git", "init", "-q"], cwd=self.tmp, check=True)
        subprocess.run(["git", "config", "user.email", "t@t"], cwd=self.tmp, check=True)
        subprocess.run(["git", "config", "user.name", "t"], cwd=self.tmp, check=True)

    def tearDown(self):
        da.ROOT, da.DATA = self._old_root, self._old_data
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _commit_all(self):
        subprocess.run(["git", "add", "-A"], cwd=self.tmp, check=True)
        subprocess.run(["git", "commit", "-q", "-m", "seed"], cwd=self.tmp, check=True)

    # ---- (a) protected-tab output ----
    def test_populated_protected_output_is_clean(self):
        _write_csv(da.DATA / "market_data.csv", _market_rows(populated=True))
        self.assertEqual(da.section_f_critical()["critical"], [])

    def test_all_nan_protected_output_is_critical(self):
        _write_csv(da.DATA / "market_data.csv", _market_rows(populated=False))
        crit = da.section_f_critical()["critical"]
        self.assertEqual(len(crit), 1)
        self.assertIn("market_data.csv", crit[0])
        self.assertIn("EMPTY value cells", crit[0])

    def test_zero_row_protected_output_is_critical(self):
        _write_csv(da.DATA / "market_data.csv",
                   [["row_id", "Symbol", "Last Price"]])
        crit = da.section_f_critical()["critical"]
        self.assertEqual(len(crit), 1)
        self.assertIn("ZERO data rows", crit[0])

    def test_missing_protected_output_is_skipped(self):
        # sentiment_data has no CSV output (legacy tab) — never a finding;
        # a missing market_data.csv means the phase crashed (job already red).
        self.assertEqual(da.section_f_critical()["critical"], [])

    # ---- (b) hist shrink vs HEAD ----
    def test_unchanged_hist_is_clean(self):
        _write_csv(self.tmp / "data/macro_market_hist.csv", _hist_rows())
        self._commit_all()
        self.assertEqual(da.section_f_critical()["critical"], [])

    def test_grown_hist_is_clean(self):
        _write_csv(self.tmp / "data/macro_market_hist.csv", _hist_rows(100, 10))
        self._commit_all()
        _write_csv(self.tmp / "data/macro_market_hist.csv", _hist_rows(120, 12))
        self.assertEqual(da.section_f_critical()["critical"], [])

    def test_small_legitimate_prune_is_clean(self):
        # a library_sync prune of 1 column in 10 (10% exactly) must NOT fire
        _write_csv(self.tmp / "data/macro_market_hist.csv", _hist_rows(100, 10))
        self._commit_all()
        _write_csv(self.tmp / "data/macro_market_hist.csv", _hist_rows(100, 9))
        self.assertEqual(da.section_f_critical()["critical"], [])

    def test_row_halving_is_critical(self):
        _write_csv(self.tmp / "data/macro_economic_hist.csv", _hist_rows(100, 10))
        self._commit_all()
        _write_csv(self.tmp / "data/macro_economic_hist.csv", _hist_rows(50, 10))
        crit = da.section_f_critical()["critical"]
        self.assertEqual(len(crit), 1)
        self.assertIn("macro_economic_hist.csv", crit[0])
        self.assertIn("row count fell", crit[0])

    def test_column_collapse_is_critical(self):
        _write_csv(self.tmp / "data/market_data_comp_hist.csv", _hist_rows(100, 20))
        self._commit_all()
        _write_csv(self.tmp / "data/market_data_comp_hist.csv", _hist_rows(100, 5))
        crit = da.section_f_critical()["critical"]
        self.assertEqual(len(crit), 1)
        self.assertIn("column count fell", crit[0])

    def test_file_new_in_this_run_is_skipped(self):
        # No HEAD version (e.g. a brand-new sister) → check skips, no finding.
        self._seed = _write_csv(self.tmp / "data/other.csv", [["x"]])
        self._commit_all()
        _write_csv(self.tmp / "data/macro_market_hist_x.csv", _hist_rows(5, 3))
        self.assertEqual(da.section_f_critical()["critical"], [])


class RealRepoNoFalseTriggerTest(unittest.TestCase):
    def test_current_repo_state_is_not_critical(self):
        """The gate must be quiet on the actual committed repo right now."""
        self.assertEqual(da.section_f_critical()["critical"], [])


if __name__ == "__main__":
    unittest.main()
