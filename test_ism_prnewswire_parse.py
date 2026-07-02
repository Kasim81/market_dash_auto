"""
Tests for the ISM PR Newswire fallback parser (sources/ism_prnewswire.py).

The fixture below is a SYNTHETIC ISM-style release, hand-written to mimic the
structure the real parser must handle — it is deliberately NOT a copy of ISM's
copyrighted release text. It exercises the parser's tricky cases:

  * markdown / trademark noise on the headline label ('Manufacturing PMI**®**'),
  * 'Inventories' vs 'Customers' Inventories' (distinct indexes, similar names),
  * prose lines that mention the index names but are not table rows,
  * a trailing 'Months' integer column that must not be read as the value.

Offline / deterministic — no network, no Bright Data credentials required.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sources import ism_prnewswire as ism  # noqa: E402
from sources import brightdata as bd  # noqa: E402

# Synthetic release, structured like the PR Newswire markdown: a summary table
# where each index label sits on its own line immediately above its current
# reading, followed by prior value, change, direction, rate and a trend integer.
SYNTHETIC_MFG = r"""
Some header text and navigation.

The Manufacturing PMI registered 53.3 percent in June, and the New Orders Index
expanded to 56 percent. Prose like this must be ignored by the parser.

INDEX SUMMARY TABLE

Manufacturing PMI\*\*®\*\*

53.3

54.0

-0.7

Growing

Slower

6

New Orders

56.0

56.8

-0.8

Growing

Slower

6

Production

52.2

54.3

-2.1

Growing

Slower

8

Inventories

51.4

49.9

+1.5

Growing

From Contracting

1

Customers' Inventories

42.3

42.7

-0.4

Too Low

Faster

21

Prices

73.0

82.1

-9.1

Increasing

Slower

21

New Orders (detail section)
The New Orders Index expanded in June with a reading of 56 percent ...
"""

SYNTHETIC_LISTING = r"""
[Manufacturing PMI report](/news-releases/manufacturing-pmi-at-53-3-june-2026-ism-manufacturing-pmi-report-302814991.html)
[Services PMI report](/news-releases/services-pmi-at-54-5-may-2026-ism-services-pmi-report-302789082.html)
[Older manufacturing](/news-releases/manufacturing-pmi-at-54-may-2026-ism-manufacturing-pmi-report-302786165.html)
"""


class ParseReportTest(unittest.TestCase):
    def test_manufacturing_values(self):
        vals = ism.parse_report(SYNTHETIC_MFG, ism.MANUFACTURING_COL_MAP)
        self.assertEqual(vals, {
            "ISM_MFG_PMI": 53.3,
            "ISM_MFG_NEWORD": 56.0,
            "ISM_MFG_INVENTORIES": 51.4,
            "ISM_MFG_PRICES": 73.0,
        })

    def test_inventories_not_confused_with_customers_inventories(self):
        vals = ism.parse_report(SYNTHETIC_MFG, ism.MANUFACTURING_COL_MAP)
        # 42.3 is Customers' Inventories — must NOT leak into ISM_MFG_INVENTORIES.
        self.assertEqual(vals["ISM_MFG_INVENTORIES"], 51.4)
        self.assertNotEqual(vals["ISM_MFG_INVENTORIES"], 42.3)

    def test_headline_label_markdown_noise_stripped(self):
        vals = ism.parse_report(SYNTHETIC_MFG, {"Manufacturing PMI": "ISM_MFG_PMI"})
        self.assertEqual(vals.get("ISM_MFG_PMI"), 53.3)

    def test_missing_label_yields_empty(self):
        vals = ism.parse_report("no table here", ism.MANUFACTURING_COL_MAP)
        self.assertEqual(vals, {})


class PeriodFromSlugTest(unittest.TestCase):
    def test_june(self):
        self.assertEqual(
            ism._period_end_from_slug(
                "manufacturing-pmi-at-53-3-june-2026-ism-manufacturing-pmi-report-1.html"
            ),
            "2026-06-30",
        )

    def test_december_end_of_year(self):
        self.assertEqual(
            ism._period_end_from_slug("x-december-2025-ism-y-1.html"), "2025-12-31"
        )

    def test_february_non_leap(self):
        self.assertEqual(
            ism._period_end_from_slug("x-february-2026-ism-y-1.html"), "2026-02-28"
        )

    def test_no_month_returns_none(self):
        self.assertIsNone(ism._period_end_from_slug("no-month-here.html"))


class DiscoveryRegexTest(unittest.TestCase):
    def test_picks_newest_manufacturing(self):
        m = ism._MFG_LINK_RE.search(SYNTHETIC_LISTING)
        self.assertIsNotNone(m)
        self.assertIn("june-2026", m.group(1))

    def test_picks_services(self):
        m = ism._SVC_LINK_RE.search(SYNTHETIC_LISTING)
        self.assertIsNotNone(m)
        self.assertIn("services-pmi", m.group(1))


class GracefulNoCredentialsTest(unittest.TestCase):
    def setUp(self):
        self._saved = os.environ.pop("BRIGHTDATA_API_KEY", None)
        # Clear per-process caches so state doesn't leak across tests.
        ism._REPORT_CACHE.clear()
        ism._LISTING_CACHE = None
        ism._LISTING_FETCHED = False

    def tearDown(self):
        if self._saved is not None:
            os.environ["BRIGHTDATA_API_KEY"] = self._saved

    def test_available_false_without_key(self):
        self.assertFalse(bd.available())

    def test_fetch_latest_returns_none(self):
        self.assertIsNone(ism.fetch_latest("manufacturing"))

    def test_latest_value_for_col_returns_none(self):
        self.assertIsNone(ism.latest_value_for_col("ISM_MFG_PMI"))

    def test_non_ism_col_returns_none(self):
        self.assertIsNone(ism.latest_value_for_col("EU_ESI"))


class FetchLatestWithStubbedUnlockTest(unittest.TestCase):
    """End-to-end discover->fetch->parse with the network call stubbed."""

    def setUp(self):
        os.environ["BRIGHTDATA_API_KEY"] = "stub"
        ism._REPORT_CACHE.clear()
        ism._LISTING_CACHE = None
        ism._LISTING_FETCHED = False
        self._orig = bd.unlock_text

        def fake(url, tag="x", timeout=60):
            if url.endswith("/institute-for-supply-management/"):
                return SYNTHETIC_LISTING
            if "manufacturing-pmi" in url:
                return SYNTHETIC_MFG
            return None

        bd.unlock_text = fake
        ism.brightdata.unlock_text = fake

    def tearDown(self):
        bd.unlock_text = self._orig
        ism.brightdata.unlock_text = self._orig
        os.environ.pop("BRIGHTDATA_API_KEY", None)
        ism._REPORT_CACHE.clear()
        ism._LISTING_CACHE = None
        ism._LISTING_FETCHED = False

    def test_end_to_end(self):
        rep = ism.fetch_latest("manufacturing")
        self.assertIsNotNone(rep)
        self.assertEqual(rep["period"], "2026-06-30")
        self.assertEqual(rep["values"]["ISM_MFG_PMI"], 53.3)
        self.assertEqual(ism.latest_value_for_col("ISM_MFG_PMI"), ("2026-06-30", 53.3))


if __name__ == "__main__":
    unittest.main()
