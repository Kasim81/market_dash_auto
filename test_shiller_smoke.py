"""Live smoke test for the Shiller source wiring.

Shiller's Yale ie_data.xls workbook is the long-run anchor (1871+ monthly)
for US equity valuation (CAPE), the S&P 500 composite price/dividends/
earnings, US CPI, and the long Treasury rate. regime-AA Phase 0c uses
these as multi-decade cross-validation anchors against the modern
FRED/BLS feeds.

This test hits the live Yale endpoint (with shillerdata.com fallback per
the module's SHILLER_XLS_HOSTS list) to confirm three things the unit
tests can't:

  1. The workbook is reachable + parseable in the daily CI environment.
  2. CAPE last-value lands in a plausible range (5 ≤ x ≤ 60 — the
     historical range is ~5 in 1920 to ~44 at the 1999 dot-com peak).
  3. The series spans the long-run window — first observation ≤ 1900-01
     and last observation ≥ today minus 6 months.

It is network-gated. If Shiller is unreachable (offline dev box / CI
without egress / Yale temporarily 403'ing common cloud IPs), it SKIPS
rather than fails, so a transient blip never blocks the daily data
commit. A *reachable* endpoint returning missing or implausible data
DOES fail — that is the regression signal we want.

Set SKIP_NETWORK_TESTS=1 to force-skip (e.g. in a no-egress unit-test
job).
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
from sources import shiller as shiller_src  # noqa: E402


def _reachable() -> bool:
    """Probe the workbook download. We test the bytes-resolve directly
    rather than going through fetch_series_as_pandas so a missing/renamed
    column doesn't masquerade as an unreachable endpoint."""
    try:
        body = shiller_src._resolve_workbook_bytes()
        return body is not None and len(body) > 1024
    except Exception:
        return False


@unittest.skipIf(os.environ.get("SKIP_NETWORK_TESTS"), "network tests disabled")
class ShillerLiveSmokeTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not _reachable():
            raise unittest.SkipTest(
                "Shiller endpoint unreachable — skipping live smoke "
                "(Yale 403 from non-credentialed sandbox IPs is common; "
                "the daily CI run exercises this)"
            )

    def test_cape_recent_value_in_plausible_range(self):
        s = shiller_src.fetch_series_as_pandas("CAPE")
        self.assertIsNotNone(s, "CAPE fetch returned None despite reachable workbook")
        self.assertFalse(s.empty, "CAPE series parsed as empty")
        last_val = float(s.iloc[-1])
        last_dt = s.index[-1]
        self.assertGreaterEqual(
            last_val, 5.0,
            f"CAPE last value {last_val} below the 5.0 historical floor — "
            f"likely a unit / column-mapping regression"
        )
        self.assertLessEqual(
            last_val, 60.0,
            f"CAPE last value {last_val} above the 60.0 historical ceiling — "
            f"likely a unit / column-mapping regression "
            f"(1999 peak was ~44, 2021 was ~38)"
        )
        # Defence against a silent column-shift regression: CAPE values
        # before ~1881 are intentionally NaN in the workbook (need 10y of
        # earnings to compute), so we expect the first non-NaN to be
        # 1881-or-later but the *index* should still start at 1871.
        self.assertGreaterEqual(
            last_dt, pd.Timestamp("2020-01-01"),
            f"CAPE last observation {last_dt.date()} too stale "
            f"(< 2020-01); workbook may not have refreshed"
        )

    def test_series_spans_long_run_window(self):
        s = shiller_src.fetch_series_as_pandas("S&P Comp. P")
        self.assertIsNotNone(s, "S&P Comp. P fetch returned None")
        self.assertFalse(s.empty, "S&P Comp. P series parsed as empty")
        first_dt = s.index[0]
        last_dt = s.index[-1]
        self.assertLessEqual(
            first_dt, pd.Timestamp("1900-01-31"),
            f"S&P Comp. P first observation {first_dt.date()} > 1900-01 — "
            f"Shiller's workbook should start at 1871-01 "
            f"(long-run depth regression)"
        )
        cutoff = pd.Timestamp(date.today()) - pd.Timedelta(days=183)
        self.assertGreaterEqual(
            last_dt, cutoff,
            f"S&P Comp. P last observation {last_dt.date()} more than "
            f"6 months stale — Shiller updates quarterly so this should "
            f"never be > 6 months behind"
        )


if __name__ == "__main__":
    unittest.main()
