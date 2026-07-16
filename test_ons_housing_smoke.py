"""
test_ons_housing_smoke.py — live smoke test for sources/ons_housing.py (§2.B B7).

Network-gated: exercises the two-step ONS beta /data -> XLSX fetch for the UK
"Indicators of house building" workbook and checks the latest quarterly
dwellings-started value is a plausible level. SKIPS on network failure so a
transient ONS outage never blocks the daily run. Runs in update_data.yml's
continue-on-error step.
"""

import unittest

from sources import ons_housing


class TestONSHousingSmoke(unittest.TestCase):
    def test_uk_dwellings_started_live(self):
        uri = ("/peoplepopulationandcommunity/housing/datasets/"
               "ukhousebuildingpermanentdwellingsstartedandcompleted/current")
        sid = f"{uri}|1a|Started - All Dwellings"
        try:
            s = ons_housing.fetch_series_as_pandas(sid, col_name="GBR_DWELLINGS_STARTED")
        except Exception as e:                       # noqa: BLE001
            self.skipTest(f"ONS Housing fetch raised (network?): {e}")
        if s is None or s.empty:
            self.skipTest("ONS Housing fetch returned nothing (network/host down)")
        last = float(s.iloc[-1])
        # UK quarterly dwelling starts have run ~20k-90k across the series' life.
        self.assertTrue(
            5_000 <= last <= 150_000,
            f"UK dwellings started {last:,.0f} outside plausible [5k, 150k]",
        )
        self.assertGreater(len(s), 100, f"only {len(s)} obs — parse likely broke")


if __name__ == "__main__":
    unittest.main()
