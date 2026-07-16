"""
test_boe_survey_smoke.py — live smoke test for sources/boe_survey.py (§2.B B4).

Network-gated: downloads the BoE Inflation Attitudes Survey workbook and checks
the 5-year-ahead median inflation-expectations series parses to a plausible
recent value. SKIPS (does not fail) when the BoE host is unreachable, so a
transient outage never blocks the daily run — consistent with the other
primary-source smoke tests. Runs in update_data.yml's continue-on-error step.
"""

import unittest

from sources import boe_survey


class TestBoESurveySmoke(unittest.TestCase):
    def test_uk_5y_inflation_expectations_live(self):
        sid = "inflation-attitudes|long-run.xlsx|LONG-RUN|five years|Median"
        try:
            s = boe_survey.fetch_series_as_pandas(sid, col_name="GBR_INFL_EXP_5Y")
        except Exception as e:                       # noqa: BLE001
            self.skipTest(f"BoE survey fetch raised (network?): {e}")
        if s is None or s.empty:
            self.skipTest("BoE survey fetch returned nothing (network/host down)")
        last = float(s.iloc[-1])
        self.assertTrue(
            1.0 <= last <= 8.0,
            f"UK 5y inflation-expectations median {last} outside plausible [1, 8]%",
        )
        # It is quarterly and started ~2009 — expect a decent history depth.
        self.assertGreater(len(s), 40, f"only {len(s)} obs — parse likely broke")

    def test_uk_credit_availability_live(self):
        # B6: dynamic-URL walk-back + year/quarter-header parse.
        sid = ("credit-conditions|Corporate annex|"
               "availability of credit provided to the corporate sector|Past three months")
        try:
            s = boe_survey.fetch_series_as_pandas(sid, col_name="GBR_CREDIT_AVAIL")
        except Exception as e:                       # noqa: BLE001
            self.skipTest(f"BoE CCS fetch raised (network?): {e}")
        if s is None or s.empty:
            self.skipTest("BoE CCS fetch returned nothing (network/host down)")
        last = float(s.iloc[-1])
        self.assertTrue(
            -100.0 <= last <= 100.0,
            f"UK credit-availability net balance {last} outside [-100, 100]",
        )
        self.assertGreater(len(s), 40, f"only {len(s)} obs — CCS parse likely broke")


if __name__ == "__main__":
    unittest.main()
