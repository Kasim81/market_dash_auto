"""
Regression tests for the DB.nomics plausibility guard.

Motivation: the DB.nomics ISM Manufacturing PMI mirror shipped physically
impossible values (~10 for a 0-100 diffusion index) across late 2025, and the
pipeline ingested them verbatim because nothing validated ranges. These tests
lock in the two guard channels:

  1. Fetch-time filter (sources.dbnomics.filter_plausible) drops out-of-band
     observations so the corruption can't reach the committed history.
  2. Library-declared bands (plausible_min / plausible_max on
     macro_library_dbnomics.csv) are surfaced by the loader and picked up by
     data_audit Section E — the committed-value backstop.

Offline / deterministic — no network.
"""

import os
import sys
import unittest

os.environ.setdefault("FRED_API_KEY", "x")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sources import dbnomics as dbn  # noqa: E402
import data_audit  # noqa: E402


class FilterPlausibleTest(unittest.TestCase):
    def test_drops_out_of_band_keeps_last_good(self):
        # The exact shape of the real regression: a good head then a corrupted
        # sub-20 tail. The guard should keep only the plausible head.
        obs = [
            ("2025-07", 48.0), ("2025-08", 48.7),
            ("2025-09", 11.1), ("2025-10", 10.0), ("2025-12", 10.3),
        ]
        kept = dbn.filter_plausible(obs, 20.0, 80.0, "ISM_MFG_PMI")
        self.assertEqual(kept, [("2025-07", 48.0), ("2025-08", 48.7)])

    def test_upper_bound(self):
        obs = [("2025-01", 55.0), ("2025-02", 250.0)]
        self.assertEqual(
            dbn.filter_plausible(obs, 20.0, 80.0, "X"), [("2025-01", 55.0)]
        )

    def test_none_bounds_is_passthrough(self):
        obs = [("2025-01", 5.0), ("2025-02", 999.0)]
        self.assertEqual(dbn.filter_plausible(obs, None, None, "X"), obs)

    def test_one_sided_bound(self):
        obs = [("2025-01", 5.0), ("2025-02", 30.0)]
        # floor only
        self.assertEqual(
            dbn.filter_plausible(obs, 20.0, None, "X"), [("2025-02", 30.0)]
        )
        # ceiling only
        self.assertEqual(
            dbn.filter_plausible(obs, None, 20.0, "X"), [("2025-01", 5.0)]
        )

    def test_boundaries_inclusive(self):
        obs = [("a", 20.0), ("b", 80.0)]
        self.assertEqual(dbn.filter_plausible(obs, 20.0, 80.0, "X"), obs)


class LibraryBandTest(unittest.TestCase):
    def test_loader_surfaces_ism_bands(self):
        lib = {r["col"]: r for r in dbn.load_library()}
        row = lib["ISM_MFG_PMI"]
        # Bands widened to [15, 99] so real ISM values (Prices Paid reached ~92
        # in 2021, ~18 in 2008) are never clipped, while the ~10 flatline
        # corruption is still caught.
        self.assertEqual(row["plausible_min"], 15.0)
        self.assertEqual(row["plausible_max"], 99.0)

    def test_prices_band_does_not_clip_2021_highs(self):
        # Regression: the original [20, 80] band dropped legitimate 2021-22
        # Prices Paid readings (81-92). [15, 99] must keep them.
        lib = {r["col"]: r for r in dbn.load_library()}
        lo, hi = lib["ISM_MFG_PRICES"]["plausible_min"], lib["ISM_MFG_PRICES"]["plausible_max"]
        for real in (81.2, 85.7, 87.1, 92.1):
            self.assertTrue(lo <= real <= hi, f"{real} wrongly outside band")

    def test_rows_without_band_are_none(self):
        lib = {r["col"]: r for r in dbn.load_library()}
        # A non-diffusion DB.nomics row should carry no band.
        row = lib["DEU_CPI_YOY"]
        self.assertIsNone(row["plausible_min"])
        self.assertIsNone(row["plausible_max"])


class AuditSectionEWiringTest(unittest.TestCase):
    def test_bands_reach_audit(self):
        bands = data_audit.load_plausibility_bands()
        self.assertEqual(bands.get("ISM_MFG_PMI"), (15.0, 99.0))

    def test_section_e_flags_implausible(self):
        # Inject a corrupted latest value and confirm Section E catches it.
        orig = data_audit.load_latest_macro_values
        data_audit.load_latest_macro_values = lambda: {
            "ISM_MFG_PMI": {
                "series_id": "ISM/pmi/pm", "source": "DB.nomics",
                "value": 10.3, "date": "2026-01-02",
            }
        }
        try:
            issues = data_audit.section_e_plausibility()["implausible"]
        finally:
            data_audit.load_latest_macro_values = orig
        flagged = {i["col_id"] for i in issues}
        self.assertIn("ISM_MFG_PMI", flagged)

    def test_section_e_passes_committed_history(self):
        # The committed history must be clean after the cleanup.
        issues = data_audit.section_e_plausibility()["implausible"]
        self.assertNotIn("ISM_MFG_PMI", {i["col_id"] for i in issues})


if __name__ == "__main__":
    unittest.main()
