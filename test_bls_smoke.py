"""Live smoke test for the BLS source wiring.

BLS is the ultimate (primary) vendor for the US series FRED republishes
(USA_CPI_INDEX, USA_CORE_CPI_INDEX, USA_UNEMPLOYMENT) plus the
USA_AVG_HOURLY_EARN gap column. This test hits the live BLS API (the keyless
v1 GET window is enough) to confirm two things the unit tests can't:

  1. each canonical series actually fetches recent, plausible data, and
  2. that live data, routed through build_hist_df, wins the merge over a
     stale-but-equal-dated FRED aggregator on the same canonical column —
     i.e. the primary-source tie-break fires on real data.

It is network-gated. If BLS is unreachable (offline dev box / CI without
egress), it SKIPS rather than fails, so a transient network blip never blocks
the daily data commit. A *reachable* endpoint returning missing, implausible
or stale data DOES fail — that is the regression signal we want.

Set SKIP_NETWORK_TESTS=1 to force-skip (e.g. in a no-egress unit-test job).
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
from sources import bls as bls_src  # noqa: E402
import fetch_macro_economic as fme  # noqa: E402

# BLS series id -> (canonical column, plausible value range). The bounds are
# deliberately wide: they catch "wrong series / units / empty" regressions, not
# small data revisions.
CANONICAL = {
    "CUSR0000SA0":    ("USA_CPI_INDEX",      50.0, 1000.0),  # CPI-U index, SA
    "CUSR0000SA0L1E": ("USA_CORE_CPI_INDEX", 50.0, 1000.0),  # core CPI index, SA
    "LNS14000000":    ("USA_UNEMPLOYMENT",    0.0,   30.0),  # unemployment rate %
    "CES0500000003":  ("USA_AVG_HOURLY_EARN", 5.0,  200.0),  # avg hourly earnings $
}

# Monthly series publish with a lag; allow generous slack before "stale" fires.
MAX_STALE_DAYS = 120


def _reachable() -> bool:
    try:
        s = bls_src.fetch_series_as_pandas("LNS14000000", recent=True)
        return s is not None and not s.empty
    except Exception:
        return False


@unittest.skipIf(os.environ.get("SKIP_NETWORK_TESTS"), "network tests disabled")
class BLSLiveSmokeTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not _reachable():
            raise unittest.SkipTest("BLS endpoint unreachable — skipping live smoke")

    def test_canonical_series_return_recent_data(self):
        today = pd.Timestamp(date.today())
        problems = []
        for sid, (col, lo, hi) in CANONICAL.items():
            s = bls_src.fetch_series_as_pandas(sid, recent=True)
            if s is None or s.empty:
                problems.append(f"{sid} ({col}): no data returned")
                continue
            last_val = float(s.iloc[-1])
            last_dt = s.index[-1]
            if not (lo <= last_val <= hi):
                problems.append(
                    f"{sid} ({col}): last value {last_val} outside [{lo}, {hi}]"
                )
            stale = (today - last_dt).days
            if stale > MAX_STALE_DAYS:
                problems.append(
                    f"{sid} ({col}): stale — last obs {last_dt.date()} ({stale}d ago)"
                )
        self.assertFalse(
            problems, "BLS live fetch problems:\n  " + "\n  ".join(problems)
        )

    def test_live_bls_wins_tie_over_fred(self):
        # Real fetched BLS unemployment must own USA_UNEMPLOYMENT over a FRED
        # aggregator whose latest observation lands on the SAME date — a true
        # tie that only the primary-source preference can break.
        bls = bls_src.fetch_series_as_pandas("LNS14000000", recent=True)
        if bls is None or bls.empty:
            # This test checks the *merge* logic with live data as input; a
            # transient fetch miss is not a merge regression, so skip rather
            # than fail. (test_canonical_series_return_recent_data is the
            # fetch-reliability signal.)
            self.skipTest("transient BLS fetch miss — merge logic unchanged")
        # FRED frozen to a different value but the identical latest date.
        fred = pd.Series(
            [3.9, 3.9],
            index=[bls.index[-1] - pd.Timedelta(days=31), bls.index[-1]],
        )

        def _indic(source, series):
            return {
                "source": source, "col": "USA_UNEMPLOYMENT", "country": "USA",
                "source_id": f"{source}_UNEMP", "name": "USA_UNEMPLOYMENT",
                "category": "", "subcategory": "", "concept": "",
                "cycle_timing": "", "units": "", "frequency": "", "notes": "",
                "_series": {"USA_UNEMPLOYMENT": series},
            }

        orig_hist, orig_spine = fme._history_for_indicator, fme.build_friday_spine
        fme._history_for_indicator = lambda indic, ifo: indic["_series"]
        fme.build_friday_spine = lambda a, b: pd.date_range(
            bls.index[0], bls.index[-1], freq="W-FRI"
        )
        try:
            # FRED registers first; BLS must still take the column on the tie.
            _, prov = fme.build_hist_df([
                _indic("FRED", fred),
                _indic("BLS", bls),
            ])
        finally:
            fme._history_for_indicator = orig_hist
            fme.build_friday_spine = orig_spine
        self.assertEqual(prov["USA_UNEMPLOYMENT"]["source"], "BLS")


if __name__ == "__main__":
    unittest.main()
