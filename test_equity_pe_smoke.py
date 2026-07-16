"""
test_equity_pe_smoke.py — live smoke test for the §3.3 equity-P/E chain.

Network-gated: resolves SPY's trailing P/E through the real yfinance → Alpha
Vantage chain and checks it is a plausible equity-index multiple. SKIPS (never
fails) when no source yields data — yfinance's .info path is blocked from the
build sandbox and Alpha Vantage may be keyless/rate-limited there, so a miss is
an environment condition, not a regression. Runs in update_data.yml's
continue-on-error smoke step, where the real values are validated.
"""

import unittest

from sources import equity_pe


class TestEquityPESmoke(unittest.TestCase):
    def test_spy_pe_live(self):
        try:
            row = equity_pe.fetch_pe_row("SPY", "S&P 500")
        except Exception as e:                       # noqa: BLE001
            self.skipTest(f"equity P/E fetch raised (network?): {e}")
        if row is None:
            self.skipTest("no P/E source resolved SPY (sandbox: yfinance .info "
                          "blocked / AV keyless) — validated on CI")
        pe = row["pe_ttm"] if row["pe_ttm"] is not None else row["pe_forward"]
        self.assertIsNotNone(pe, "row present but both P/E fields empty")
        self.assertTrue(
            3.0 <= pe <= 100.0,
            f"SPY P/E {pe} outside plausible equity-index range [3, 100] "
            f"(source={row['source']})",
        )


if __name__ == "__main__":
    unittest.main()
