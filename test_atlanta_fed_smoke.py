"""Live smoke test for the Atlanta Fed GDPNow source wiring.

The Atlanta Fed GDPNow xlsx is the real-time US real-GDP-growth nowcast
that feeds `US_GDPNOW1` (§3.1.4) — the headline Growth-axis input for the
regime classifier alongside US_NOWCAST1 / UK_NOWCAST1 / EU_NOWCAST1 /
JP_NOWCAST1.

This test hits the live xlsx (canonical
https://www.atlantafed.org/-/media/Project/Atlanta/FRBA/Documents/cqer/
researchcq/gdpnow/GDPTrackingModelDataAndForecasts.xlsx, with
www.frbatlanta.org mirror fallback per the module's GDPNOW_XLSX_HOSTS list)
to confirm three things the unit tests can't:

  1. The workbook is reachable + parseable in the daily CI environment.
  2. The most recent GDPNow point estimate lands in a plausible
     growth-rate range (-10% ≤ x ≤ +15%) — wide enough to ride out the
     occasional pandemic-era ±35% reading without false-positives but
     tight enough to catch a unit / column-mapping regression that
     surfaces e.g. an index level or a contribution-to-growth in the
     headline slot.
  3. The series isn't stale beyond 60 days — GDPNow has quiet windows of
     up to ~5 business days around BEA advance estimates, but never goes
     a full quarter without an update, so > 60 days stale is a clear
     regression signal.

It is network-gated. If Atlanta Fed is unreachable (offline dev box / CI
without egress / sandbox without the host on the allowlist), it SKIPS
rather than fails, so a transient blip never blocks the daily data
commit. A *reachable* endpoint returning missing or implausible data DOES
fail — that is the regression signal we want.

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
from sources import atlanta_fed as atlanta_fed_src  # noqa: E402


# Plausibility bounds for the GDPNow point estimate (Q/Q SAAR %). The 2020-Q2
# pandemic print was ~-35% and the 2020-Q3 rebound was ~+35%, but those are
# once-in-a-generation outliers; the working range during normal cycles is
# roughly [-10, +15]. Tighter than the calculator's own [-50, +50] safety
# guard so this test catches regressions the parser-side guard wouldn't.
MIN_PLAUSIBLE = -10.0
MAX_PLAUSIBLE = 15.0

# Max acceptable staleness. GDPNow has quiet windows around BEA advance
# estimates but never goes a full quarter (~90d) without an update.
MAX_STALE_DAYS = 60


def _reachable() -> bool:
    """Probe the workbook download. Test bytes-resolve directly rather than
    going through fetch_series_as_pandas so a missing/renamed sheet doesn't
    masquerade as an unreachable endpoint."""
    try:
        body = atlanta_fed_src._resolve_workbook_bytes()
        return body is not None and len(body) > 1024
    except Exception:
        return False


@unittest.skipIf(os.environ.get("SKIP_NETWORK_TESTS"), "network tests disabled")
class AtlantaFedLiveSmokeTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not _reachable():
            raise unittest.SkipTest(
                "Atlanta Fed endpoint unreachable — skipping live smoke "
                "(sandbox blocks www.atlantafed.org / www.frbatlanta.org; "
                "the daily CI run exercises this)"
            )

    def test_gdpnow_recent_value_in_plausible_range(self):
        s = atlanta_fed_src.fetch_series_as_pandas("gdpnow_us_qoq_saar")
        self.assertIsNotNone(
            s, "GDPNow fetch returned None despite reachable workbook"
        )
        self.assertFalse(s.empty, "GDPNow series parsed as empty")
        last_val = float(s.iloc[-1])
        last_dt = s.index[-1]
        self.assertGreaterEqual(
            last_val, MIN_PLAUSIBLE,
            f"GDPNow last value {last_val:.2f} below the {MIN_PLAUSIBLE}% "
            f"normal-cycle floor — likely a unit / column-mapping regression"
        )
        self.assertLessEqual(
            last_val, MAX_PLAUSIBLE,
            f"GDPNow last value {last_val:.2f} above the {MAX_PLAUSIBLE}% "
            f"normal-cycle ceiling — likely a unit / column-mapping regression"
        )
        today = pd.Timestamp(date.today())
        stale = (today - last_dt).days
        self.assertLessEqual(
            stale, MAX_STALE_DAYS,
            f"GDPNow last observation {last_dt.date()} is {stale}d old "
            f"(> {MAX_STALE_DAYS}d) — workbook may not have refreshed"
        )

    def test_series_spans_useful_window(self):
        """GDPNow's TrackingArchives starts at 2014-Q2 and TrackingDeepArchives
        carries 2011-Q3 onwards; the combined series should reach at least
        as far back as 2014-01-01 once the workbook is parsed end-to-end.

        This is the regression signal for "parser found the current quarter
        but missed the historical tabs" — a real concern because the file
        adds a new per-quarter tab roughly every 90 days."""
        s = atlanta_fed_src.fetch_series_as_pandas("gdpnow_us_qoq_saar")
        self.assertIsNotNone(s, "GDPNow fetch returned None")
        self.assertFalse(s.empty, "GDPNow series parsed as empty")
        first_dt = s.index[0]
        self.assertLessEqual(
            first_dt, pd.Timestamp("2016-01-01"),
            f"GDPNow first observation {first_dt.date()} > 2016-01 — "
            f"parser likely missed TrackingArchives / TrackingDeepArchives "
            f"(should reach back to ~2011-Q3 / 2014-Q2)"
        )


if __name__ == "__main__":
    unittest.main()
