"""Live smoke test for the Alpha Vantage source wiring.

Alpha Vantage's free tier allows only 25 requests/day so this test pulls
the OVERVIEW for a SINGLE symbol (SPY) and asserts the response contains
a parseable trailing PE. That's enough to confirm:

  1. ALPHAVANTAGE_API_KEY reaches the runtime;
  2. the auth scheme works against the live endpoint;
  3. PE/forward-PE fields are present in the response shape.

Key-gated and network-gated: SKIPS unless ALPHAVANTAGE_API_KEY is set
and the endpoint is reachable. Rate-limit responses (Note / Information
field) also skip rather than fail, so a quota burn on another tool
sharing the key doesn't block the daily commit.

Set SKIP_NETWORK_TESTS=1 to force-skip.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sources import alpha_vantage as av_src  # noqa: E402


def _have_key() -> bool:
    return bool(os.environ.get("ALPHAVANTAGE_API_KEY", "").strip())


@unittest.skipIf(os.environ.get("SKIP_NETWORK_TESTS"), "network tests disabled")
@unittest.skipUnless(_have_key(), "ALPHAVANTAGE_API_KEY not set — AV smoke skipped")
class AlphaVantageLiveSmokeTest(unittest.TestCase):
    def test_overview_resolves_for_spy(self):
        ratios = av_src.get_pe_ratios("SPY")
        if ratios is None:
            # Rate-limit or transient endpoint outage — already logged to
            # pipeline.log via av_src. Skip rather than fail; the audit
            # tracks the missing snapshot separately.
            self.skipTest("Alpha Vantage SPY fetch returned None — quota or outage")
        self.assertEqual(ratios.get("symbol"), "SPY")
        pe_ttm = ratios.get("pe_ttm")
        self.assertIsNotNone(
            pe_ttm,
            "Alpha Vantage SPY OVERVIEW response missing a parseable PERatio "
            "(forward_plan §3.3 contract). Raw ratios: " + repr(ratios),
        )
        # Wide bound — catches "wrong field / units" regressions, not
        # market moves. SPY trailing PE has historically lived in [12, 35].
        self.assertGreater(pe_ttm, 5.0, f"SPY PERatio implausibly low: {pe_ttm}")
        self.assertLess(pe_ttm, 80.0, f"SPY PERatio implausibly high: {pe_ttm}")


if __name__ == "__main__":
    unittest.main()
