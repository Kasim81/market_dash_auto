"""Offline regression tests for scripts/source_probe.py (§2.C C16.1).

The probe exists to answer data-layer questions the dev sandbox cannot: it
runs on the GitHub runner where the API keys live and where bfs.admin.ch /
cbs.nl / ec.europa.eu are reachable. Two things about it are worth pinning.

1. TEMPLATE CLONING MUST NOT INHERIT ROW-SPECIFIC VALIDITY BANDS. To fetch an
   *unregistered* candidate series id through a source's real history handler,
   the probe clones a registered row of that source and overrides source_id.
   The first run cloned a DB.nomics ISM row, inherited its plausible band of
   [15, 99], and silently dropped 761 of 844 CPI observations — then reported
   the 83 survivors as though they were the series. This is the repo's
   recurring bug class (a guard that stays in form but not in function, and
   reports success) pointed at the diagnostic instead of the pipeline, so it
   gets a test.

2. THE `http` MODE IS HOST-ALLOWLISTED. That job carries every repository
   secret in its environment; an arbitrary-URL fetch is not a trade worth
   making for a diagnostic's convenience.

No network, no API keys — runs in the ci.yml offline gate.
"""

import importlib.util
import os
import pathlib
import sys
import unittest

os.environ.setdefault("FRED_API_KEY", "x")
os.environ.setdefault("SHEET_ID", "x")
os.environ.setdefault("GOOGLE_CREDENTIALS_JSON", "{}")

ROOT = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

_spec = importlib.util.spec_from_file_location(
    "source_probe", ROOT / "scripts" / "source_probe.py")
probe = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(probe)


class TemplateCloneTest(unittest.TestCase):
    """A cloned template must carry the source's shape, not the row's limits."""

    def test_plausibility_bands_are_not_inherited(self):
        # DB.nomics is the case that actually bit: its ISM rows carry
        # [15, 99] bands, and the loader hands the first row back as template.
        indic = probe._template_indic("DB.nomics")
        self.assertIsNone(indic.get("plausible_min"),
                          "cloned template inherited plausible_min — it will "
                          "silently clip the probed series")
        self.assertIsNone(indic.get("plausible_max"),
                          "cloned template inherited plausible_max — it will "
                          "silently clip the probed series")

    def test_some_dbnomics_row_really_does_carry_a_band(self):
        # Non-vacuity: if no DB.nomics row had a band, the test above would
        # pass for the wrong reason and stop protecting anything.
        from sources import dbnomics
        banded = [r for r in dbnomics.load_library()
                  if r.get("plausible_min") is not None
                  or r.get("plausible_max") is not None]
        self.assertTrue(banded,
                        "no DB.nomics row carries a plausibility band, so "
                        "test_plausibility_bands_are_not_inherited is vacuous")

    def test_structural_fields_survive_the_clone(self):
        # The whole reason to clone rather than hand-build is that the source's
        # history handler reads fields the probe does not know about. Dropping
        # too much would defeat that.
        indic = probe._template_indic("DB.nomics")
        self.assertEqual(indic.get("source"), "DB.nomics")
        self.assertIn("frequency", indic)
        self.assertIn("units", indic)
        self.assertIn("country", indic)

    def test_unknown_source_aborts(self):
        with self.assertRaises(SystemExit):
            probe._template_indic("No Such Source")


class HttpAllowlistTest(unittest.TestCase):
    def test_allowlist_is_not_empty_and_excludes_the_open_internet(self):
        self.assertTrue(probe._ALLOWED_HOSTS)
        for host in ("example.com", "github.com", "api.openai.com", ""):
            self.assertNotIn(host, probe._ALLOWED_HOSTS)

    def test_offlist_host_is_refused_without_fetching(self):
        probe._lines.clear()
        # No network: a refusal must happen before any request is attempted.
        probe.mode_http({"url": "https://example.com/whatever"})
        joined = "\n".join(probe._lines)
        self.assertIn("REFUSED", joined)
        self.assertIn("allowlist", joined)

    def test_blocked_hosts_the_track_needs_are_on_the_list(self):
        # These are the hosts the sandbox 403s at CONNECT; the probe exists
        # largely to reach them.
        for host in ("odata4.cbs.nl", "www.pxweb.bfs.admin.ch", "ec.europa.eu"):
            self.assertIn(host, probe._ALLOWED_HOSTS)


class SpecResolutionTest(unittest.TestCase):
    def test_col_lookup_finds_registered_rows(self):
        legs = probe._resolve({"col": "ITA_CPI_YOY"})
        self.assertTrue(legs)
        sources_found = {indic["source"] for _, indic in legs}
        self.assertIn("ISTAT", sources_found,
                      "the ISTAT national primary should serve ITA_CPI_YOY")

    def test_fanout_sibling_is_matched(self):
        # A row registered as col=UNEMPLOYMENT serves CAN_UNEMPLOYMENT etc.;
        # resolving the served name must find it.
        legs = probe._resolve({"col": "CAN_UNEMPLOYMENT"})
        self.assertTrue(legs, "fan-out sibling lookup found nothing")

    def test_leg_without_col_or_series_id_aborts(self):
        with self.assertRaises(SystemExit):
            probe._resolve({"source": "ISTAT"})

    def test_unknown_col_aborts(self):
        with self.assertRaises(SystemExit):
            probe._resolve({"col": "NO_SUCH_COLUMN_XYZ"})


class DecimalsTest(unittest.TestCase):
    """Precision detection is what surfaced the CAN/ITA 1-dp finding."""

    def test_detects_one_decimal_publication(self):
        import pandas as pd
        s = pd.Series([2.8, 1.3, -0.9, 3.4],
                      index=pd.date_range("2026-01-31", periods=4, freq="ME"))
        self.assertEqual(probe._decimals(s), 1)

    def test_detects_full_precision(self):
        import pandas as pd
        s = pd.Series([2.815177, 1.349948],
                      index=pd.date_range("2026-01-31", periods=2, freq="ME"))
        self.assertGreaterEqual(probe._decimals(s), 6)

    def test_integers_report_zero(self):
        import pandas as pd
        s = pd.Series([2.0, 3.0],
                      index=pd.date_range("2026-01-31", periods=2, freq="ME"))
        self.assertEqual(probe._decimals(s), 0)


if __name__ == "__main__":
    unittest.main()
