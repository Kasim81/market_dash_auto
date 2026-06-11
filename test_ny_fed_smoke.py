"""Live smoke test for the New York Fed Staff Nowcast source wiring.

The NY Fed Staff Nowcast xlsx is the real-time US real-GDP-growth nowcast
that feeds `US_NOWCAST1` (§3.1.4) — the second-opinion Growth-axis input
for the regime classifier alongside US_GDPNOW1 (Atlanta Fed GDPNow).

This test hits the live xlsx (canonical
https://www.newyorkfed.org/medialibrary/Research/Interactives/Data/
NowCast/Downloads/New-York-Fed-Staff-Nowcast_download_data.xlsx, per the
module's NYFED_XLSX_HOSTS list) to confirm three things the unit tests
can't:

  1. The workbook is reachable + parseable in the daily CI environment.
  2. The most recent NY Fed nowcast point estimate lands in a plausible
     growth-rate range (-10% <= x <= +15%) — wide enough to ride out the
     occasional pandemic-era +/-35% reading without false-positives but
     tight enough to catch a unit / column-mapping regression that
     surfaces e.g. an index level or a contribution-to-growth in the
     headline slot.
  3. The series isn't stale beyond 60 days — the NY Fed publishes a new
     nowcast weekly during tracking quarters, with quiet windows of up
     to ~5 business days around BEA advance estimates; > 60 days stale
     is a clear regression signal.

It is network-gated. If the NY Fed medialibrary is unreachable (offline
dev box / CI without egress / sandbox without the host on the allowlist),
it SKIPS rather than fails, so a transient blip never blocks the daily
data commit. A *reachable* endpoint returning missing or implausible data
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
from sources import ny_fed as ny_fed_src  # noqa: E402


# Plausibility bounds for the NY Fed nowcast point estimate (Q/Q SAAR %).
# Same window as test_atlanta_fed_smoke — both models target the same
# series; if the readings diverge wildly that's a parser regression on
# one side, not a model-divergence signal worth surfacing here.
MIN_PLAUSIBLE = -10.0
MAX_PLAUSIBLE = 15.0

# Max acceptable staleness. NY Fed publishes weekly during tracking
# quarters, with quiet windows around BEA advance estimates; 60d is the
# same envelope as Atlanta Fed.
MAX_STALE_DAYS = 60


def _reachable() -> bool:
    """Probe the workbook download. Test bytes-resolve directly rather than
    going through fetch_series_as_pandas so a missing/renamed sheet doesn't
    masquerade as an unreachable endpoint."""
    try:
        body = ny_fed_src._resolve_workbook_bytes()
        return body is not None and len(body) > 1024
    except Exception:
        return False


@unittest.skipIf(os.environ.get("SKIP_NETWORK_TESTS"), "network tests disabled")
class NYFedLiveSmokeTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not _reachable():
            raise unittest.SkipTest(
                "NY Fed Nowcast endpoint unreachable — skipping live smoke "
                "(sandbox blocks www.newyorkfed.org; the daily CI run "
                "exercises this)"
            )

    def test_nowcast_recent_value_in_plausible_range(self):
        s = ny_fed_src.fetch_series_as_pandas("nyfed_nowcast_us_qoq_saar")
        self.assertIsNotNone(
            s, "NY Fed Nowcast fetch returned None despite reachable workbook"
        )
        self.assertFalse(s.empty, "NY Fed Nowcast series parsed as empty")
        last_val = float(s.iloc[-1])
        last_dt = s.index[-1]
        self.assertGreaterEqual(
            last_val, MIN_PLAUSIBLE,
            f"NY Fed Nowcast last value {last_val:.2f} below the {MIN_PLAUSIBLE}% "
            f"normal-cycle floor — likely a unit / column-mapping regression"
        )
        self.assertLessEqual(
            last_val, MAX_PLAUSIBLE,
            f"NY Fed Nowcast last value {last_val:.2f} above the {MAX_PLAUSIBLE}% "
            f"normal-cycle ceiling — likely a unit / column-mapping regression"
        )
        today = pd.Timestamp(date.today())
        stale = (today - last_dt).days
        self.assertLessEqual(
            stale, MAX_STALE_DAYS,
            f"NY Fed Nowcast last observation {last_dt.date()} is {stale}d old "
            f"(> {MAX_STALE_DAYS}d) — workbook may not have refreshed"
        )

    def test_series_non_empty_and_recent(self):
        """The NY Fed workbook carries the live model's vintage history;
        the parsed series should be non-empty and reach at least into the
        last 90 days under normal operation."""
        s = ny_fed_src.fetch_series_as_pandas("nyfed_nowcast_us_qoq_saar")
        self.assertIsNotNone(s, "NY Fed Nowcast fetch returned None")
        self.assertFalse(s.empty, "NY Fed Nowcast series parsed as empty")
        self.assertGreaterEqual(
            len(s), 10,
            f"NY Fed Nowcast series only has {len(s)} observation(s) — "
            f"parser likely missed the historical archive section"
        )
        today = pd.Timestamp(date.today())
        last_dt = s.index[-1]
        self.assertLessEqual(
            (today - last_dt).days, 90,
            f"NY Fed Nowcast last observation {last_dt.date()} is "
            f"> 90 days old — endpoint likely stale or parser missing the "
            f"live tab"
        )


if __name__ == "__main__":
    unittest.main()
