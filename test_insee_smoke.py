"""Live smoke test for the INSEE BDM source wiring.

INSEE's BDM web service is open and keyless, and INSEE is the ultimate (primary)
vendor for French series that aggregators (Eurostat, OECD, IMF, World Bank,
DB.nomics) republish. This test hits the live API to confirm the curated French
series fetch recent, plausible data through the same module the pipeline uses.

Network-gated: SKIPS if INSEE is unreachable (or SKIP_NETWORK_TESTS=1), so a
transient outage never turns into a false failure; a reachable endpoint
returning missing/implausible/stale data fails — the regression signal.
"""
import os
import sys
import unittest
from datetime import date

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sources import insee as insee_src  # noqa: E402

# idbank -> (canonical column, low, high, max-stale-days). Quarterly national
# accounts / labour publish with a ~1-quarter lag, so the windows are generous.
CURATED = {
    "SERIES_BDM/001565530": ("FRA_BUS_CONF",     50.0,    150.0,  90),
    "SERIES_BDM/001688527": ("FRA_UNEMPLOYMENT",  0.0,     30.0, 200),
    "SERIES_BDM/011794860": ("FRA_GDP_INDEX",     1.0, 5_000_000.0, 200),
}


def _reachable() -> bool:
    try:
        s = insee_src.fetch_series_as_pandas("SERIES_BDM/001565530")
        return s is not None and not s.empty
    except Exception:
        return False


@unittest.skipIf(os.environ.get("SKIP_NETWORK_TESTS"), "network tests disabled")
class INSEELiveSmokeTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not _reachable():
            raise unittest.SkipTest("INSEE endpoint unreachable — skipping live smoke")

    def test_curated_series_return_recent_data(self):
        today = pd.Timestamp(date.today())
        problems = []
        for sid, (col, lo, hi, max_stale) in CURATED.items():
            s = insee_src.fetch_series_as_pandas(sid, col_name=col)
            if s is None or s.empty:
                problems.append(f"{sid} ({col}): no data returned")
                continue
            last_val = float(s.iloc[-1])
            last_dt = s.index[-1]
            if not (lo <= last_val <= hi):
                problems.append(f"{sid} ({col}): last value {last_val} outside [{lo}, {hi}]")
            stale = (today - last_dt).days
            if stale > max_stale:
                problems.append(
                    f"{sid} ({col}): stale — last obs {last_dt.date()} ({stale}d ago)"
                )
        self.assertFalse(
            problems, "INSEE live fetch problems:\n  " + "\n  ".join(problems)
        )


if __name__ == "__main__":
    unittest.main()
