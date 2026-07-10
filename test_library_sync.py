"""Offline tests for library_sync's generic SyncSpec machinery (§2.C C6).

library_sync mutates committed history files — the reason C6 collapsed the
three copy-pasted per-pair helper trios into one generic path is that
identical logic in three copies is where a fix applied to two of three
creates a subtle data bug (it happened: the comp archiver learned
header-sniffing on 2026-07-08, the macro_economic one kept a hardcoded
``rows[15:]`` and archived the "Date" header row as data after the 14→15
metadata-row growth). These tests pin the generic behaviour on synthetic
files in all three layouts.

No network, no API keys — runs in the ci.yml offline gate.
"""
import csv
import os
import shutil
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import library_sync as ls  # noqa: E402


def _write(path: Path, rows: list[list[str]]) -> None:
    with path.open("w", newline="") as f:
        csv.writer(f, lineterminator="\n").writerows(rows)


def _read(path: Path) -> list[list[str]]:
    with path.open(newline="") as f:
        return list(csv.reader(f))


def _comp_rows() -> list[list[str]]:
    """market_data_comp_hist layout, post-A16 generation (12 metadata rows)."""
    rows = [["", "Ticker ID", "SPY", "SPY", "AGG", "AGG"]]
    for label in ["Name", "Region", "Asset Class", "Currency", "Sub Class",
                  "Weight", "Benchmark", "Provider", "Expense", "Last Updated",
                  "Last Observation"]:
        rows.append(["", label, "", "", "", ""])
    rows.append(["row_id", "Date", "SPY_Local", "SPY_USD", "AGG_Local", "AGG_USD"])
    rows.append(["1", "2026-06-26", "500.0", "500.0", "98.0", "98.0"])
    rows.append(["2", "2026-07-03", "501.0", "501.0", "98.5", "98.5"])
    return rows


def _macro_econ_rows() -> list[list[str]]:
    """macro_economic_hist layout, post-A14 generation (15 metadata rows)."""
    rows = [["Column ID", "KEEP_ME", "ORPHAN_X"]]
    for label in ["Series ID", "Source", "Indicator", "Country", "Country Name",
                  "Region", "Category", "Subcategory", "Concept", "cycle_timing",
                  "Units", "Frequency", "Last Updated", "Last Observation"]:
        rows.append([label, "", ""])
    rows.append(["Date", "KEEP_ME", "ORPHAN_X"])
    rows.append(["2026-06-26", "1.0", "9.0"])
    rows.append(["2026-07-03", "1.1", "9.1"])
    return rows


def _macro_mkt_rows() -> list[list[str]]:
    """macro_market_hist layout (header-only, no metadata prefix)."""
    return [
        ["Date", "US_G1_raw", "US_G1_zscore", "US_G1_regime", "US_G1_fwd_regime",
         "GONE_raw", "GONE_zscore", "GONE_regime", "GONE_fwd_regime"],
        ["2026-06-26", "1", "0.5", "EXPANSION", "EXPANSION", "2", "0.1", "SLOWDOWN", "SLOWDOWN"],
        ["2026-07-03", "2", "0.6", "EXPANSION", "EXPANSION", "3", "0.2", "SLOWDOWN", "SLOWDOWN"],
    ]


class SyncSpecMachineryTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="libsync_test_"))
        self._old_root, self._old_archive = ls.ROOT, ls.ARCHIVE
        ls.ROOT = self.tmp
        ls.ARCHIVE = self.tmp / "_archived_columns"

    def tearDown(self):
        ls.ROOT, ls.ARCHIVE = self._old_root, self._old_archive
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _spec(self, name, rows, expected, id_start_col, sister_rows=None):
        hist = self.tmp / name
        _write(hist, rows)
        if sister_rows is not None:
            _write(self.tmp / name.replace("_hist.csv", "_hist_x.csv"), sister_rows)
        return ls.SyncSpec(name, hist, lambda: expected, id_start_col)

    # ---- header location across layouts ----
    def test_locate_data_header_all_layouts(self):
        self.assertEqual(ls._locate_data_header(_comp_rows()), 12)
        self.assertEqual(ls._locate_data_header(_macro_econ_rows()), 15)
        self.assertEqual(ls._locate_data_header(_macro_mkt_rows()), 0)

    # ---- present ids ----
    def test_present_ids_respects_start_col(self):
        self.assertEqual(ls._present_ids(
            ls.SyncSpec("x", Path("x"), lambda: set(), 2), _comp_rows()),
            {"SPY", "AGG"})
        self.assertEqual(ls._present_ids(
            ls.SyncSpec("x", Path("x"), lambda: set(), 1), _macro_econ_rows()),
            {"KEEP_ME", "ORPHAN_X"})

    # ---- dry-run never mutates ----
    def test_dry_run_reports_but_does_not_mutate(self):
        spec = self._spec("market_data_comp_hist.csv", _comp_rows(), {"SPY"}, 2)
        before = _read(spec.hist_path)
        n = ls.sync(spec, confirm=False)
        self.assertEqual(n, 1)                       # AGG is the orphan
        self.assertEqual(_read(spec.hist_path), before)
        self.assertFalse(ls.ARCHIVE.exists())

    # ---- comp confirm: paired _Local/_USD columns drop together ----
    def test_comp_confirm_archives_and_drops_both_columns(self):
        spec = self._spec("market_data_comp_hist.csv", _comp_rows(), {"SPY"}, 2,
                          sister_rows=_comp_rows())
        n = ls.sync(spec, confirm=True)
        self.assertEqual(n, 1)
        new_rows = _read(spec.hist_path)
        self.assertNotIn("AGG", new_rows[0])
        self.assertEqual(len(new_rows[0]), 4)        # "", Ticker ID, SPY, SPY
        # archive holds Date + both AGG columns, data rows only
        arch = ls.ARCHIVE / f"market_data_comp_hist__AGG__{date.today().isoformat()}.csv"
        self.assertTrue(arch.exists())
        arows = _read(arch)
        self.assertEqual(arows[0], ["Date", "AGG_Local", "AGG_USD"])
        self.assertEqual(arows[1], ["2026-06-26", "98.0", "98.0"])
        self.assertEqual(len(arows), 3)
        # sister mirrored to the same schema
        sister = _read(self.tmp / "market_data_comp_hist_x.csv")
        self.assertNotIn("AGG", sister[0])

    # ---- macro_econ confirm: the C6 header-generation bug fix ----
    def test_macro_econ_archive_excludes_header_row_on_15_row_generation(self):
        spec = self._spec("macro_economic_hist.csv", _macro_econ_rows(),
                          {"KEEP_ME"}, 1)
        n = ls.sync(spec, confirm=True)
        self.assertEqual(n, 1)
        arch = ls.ARCHIVE / f"macro_economic_hist__ORPHAN_X__{date.today().isoformat()}.csv"
        arows = _read(arch)
        self.assertEqual(arows[0], ["Date", "ORPHAN_X"])
        # exactly the 2 data rows — the "Date,..." header row must NOT appear
        # as data (the pre-C6 hardcoded rows[15:] bug on 15-metadata files)
        self.assertEqual(len(arows), 3)
        self.assertEqual(arows[1][0], "2026-06-26")
        # live file keeps the survivor
        new_rows = _read(spec.hist_path)
        self.assertEqual(new_rows[0], ["Column ID", "KEEP_ME"])

    # ---- macro_mkt confirm: 4 suffix columns drop as a unit ----
    def test_macro_mkt_confirm_drops_all_four_suffix_columns(self):
        expected = {f"US_G1{s}" for s in ls.INDICATOR_SUFFIXES}
        spec = self._spec("macro_market_hist.csv", _macro_mkt_rows(), expected, 1)
        n = ls.sync(spec, confirm=True)
        self.assertEqual(n, 4)                       # each GONE_* id is an orphan
        new_rows = _read(spec.hist_path)
        self.assertEqual(len(new_rows[0]), 5)        # Date + 4 US_G1 columns
        self.assertFalse([c for c in new_rows[0] if c.startswith("GONE")])

    # ---- registry sanity ----
    def test_sync_specs_registry_shape(self):
        self.assertEqual(len(ls.SYNC_SPECS), 3)
        names = [s.name for s in ls.SYNC_SPECS]
        self.assertEqual(names, ["market_data_comp_hist.csv",
                                 "macro_economic_hist.csv",
                                 "macro_market_hist.csv"])
        for s in ls.SYNC_SPECS:
            self.assertTrue(callable(s.expected))


if __name__ == "__main__":
    unittest.main()
