"""
test_ons_rti_smoke.py — live smoke test for sources/ons_rti.py (§2.B B8).

Network-gated: exercises the two-step ONS beta /data -> XLSX fetch for PAYE RTI
payrolled-employee counts and checks the latest value is a plausible UK
employment level (~25-35 million). SKIPS on network failure so a transient ONS
outage never blocks the daily run. Runs in update_data.yml's continue-on-error
step.
"""

import unittest

from sources import ons_rti


class TestONSRTISmoke(unittest.TestCase):
    def test_uk_payrolls_live(self):
        uri = ("/employmentandlabourmarket/peopleinwork/earningsandworkinghours/"
               "datasets/realtimeinformationstatisticsreferencetableseasonally"
               "adjusted/current")
        sid = f"{uri}|1. Payrolled employees (UK)|Payrolled employees"
        try:
            s = ons_rti.fetch_series_as_pandas(sid, col_name="GBR_PAYROLLS")
        except Exception as e:                       # noqa: BLE001
            self.skipTest(f"ONS RTI fetch raised (network?): {e}")
        if s is None or s.empty:
            self.skipTest("ONS RTI fetch returned nothing (network/host down)")
        last = float(s.iloc[-1])
        self.assertTrue(
            25e6 <= last <= 35e6,
            f"UK payrolled employees {last:,.0f} outside plausible [25M, 35M]",
        )
        self.assertGreater(len(s), 100, f"only {len(s)} obs — parse likely broke")


if __name__ == "__main__":
    unittest.main()
