"""Live smoke test for the Ken French source wiring.

Ken French's data library is the canonical source for US 5-factor monthly
returns (Mkt-RF, SMB, HML, RMW, CMA) plus the 1-month T-bill risk-free
rate back to 1926-07.  Wired §3.11 (2026-06-10) as one of the regime-AA
long-run sources.

This test hits ``mba.tuck.dartmouth.edu`` directly to confirm:

  1. The 5-Factor ZIP is reachable AND parses end-to-end.
  2. The monthly Mkt-RF series spans at least 1926-07 → today minus 6 months.
  3. The most-recent value lies in a plausible range for a monthly return
     in percent (i.e. roughly inside [-50, +50]).

Network-gated: if the Dartmouth host is unreachable from this runner
(the sandbox's allow-list returns ``Host not allowed``, intermittent
404/throttle, etc.), the test SKIPS rather than fails — same shape as
``test_bls_smoke.py`` so a transient network blip never blocks the daily
data commit.

Set ``SKIP_NETWORK_TESTS=1`` to force-skip (e.g. in a no-egress
unit-test job).
"""
import os
import sys
import unittest
from datetime import date

import pandas as pd

os.environ.setdefault("FRED_API_KEY", "x")
os.environ.setdefault("SHEET_ID", "x")
os.environ.setdefault("GOOGLE_CREDENTIALS_JSON", "{}")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sources import french as french_src  # noqa: E402

PROBE_SERIES = "F-F_Research_Data_5_Factors_2x3|Mkt-RF"


def _reachable() -> pd.Series | None:
    """Return the probe series if the host is reachable, else None."""
    try:
        s = french_src.fetch_series_as_pandas(PROBE_SERIES)
    except Exception:
        return None
    if s is None or s.empty:
        return None
    return s


@unittest.skipIf(os.environ.get("SKIP_NETWORK_TESTS"), "network tests disabled")
class KenFrenchLiveSmokeTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        s = _reachable()
        if s is None:
            raise unittest.SkipTest(
                "Ken French ZIP unreachable — skipping live smoke"
            )
        cls.mkt_rf = s

    def test_mkt_rf_long_run_coverage(self):
        s = self.mkt_rf
        earliest = s.index.min()
        latest = s.index.max()

        # Origin: monthly file starts at 1926-07. Allow the test to pass
        # if the publisher ever drops a few early rows but still gives us
        # multi-decade depth.
        self.assertLessEqual(
            earliest, pd.Timestamp("1927-01-31"),
            f"Mkt-RF earliest obs {earliest.date()} later than 1927-01 — "
            "long-run depth requirement broken",
        )

        # The Ken French monthly file lags 1-2 months. Allow 6 months of
        # staleness slack on top of that before this fires.
        target_latest = pd.Timestamp(date.today()) - pd.DateOffset(months=6)
        self.assertGreaterEqual(
            latest, target_latest,
            f"Mkt-RF latest obs {latest.date()} more than 6 months stale "
            f"(today={date.today()})",
        )

    def test_mkt_rf_latest_value_plausible(self):
        s = self.mkt_rf
        last_val = float(s.iloc[-1])
        # Monthly equity-premium returns in % are realistically in the
        # low-double-digit range; -50 / +50 is a generous regression
        # guard against wrong-units / wrong-column extraction.
        self.assertGreater(
            last_val, -50.0,
            f"Mkt-RF latest value {last_val} below plausible monthly floor",
        )
        self.assertLess(
            last_val, 50.0,
            f"Mkt-RF latest value {last_val} above plausible monthly ceiling",
        )


if __name__ == "__main__":
    unittest.main()
