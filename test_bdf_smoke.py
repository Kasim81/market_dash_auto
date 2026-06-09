"""Live smoke test for the Banque de France (Webstat) source wiring.

Banque de France is the ultimate (primary) producer of French MFI interest-rate
and monetary statistics. Webstat needs a credential (client id, and possibly a
secret), so this test is BOTH key-gated and network-gated: it SKIPS unless
BDF_API_KEY is set and the endpoint is reachable. That means it stays dormant in
local/unit runs and only fires on the credentialed daily CI run.

Because the curated Webstat series keys are PROVISIONAL (the catalogue needs
auth and could not be validated when they were written), this test deliberately
asserts only that each series resolves to non-empty data — that is exactly the
"do the keys + auth work?" question the first credentialed run must answer.
Tighten the bounds once the keys are confirmed.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sources import bdf as bdf_src  # noqa: E402

CURATED = {
    "MIR1/M.FR.B.A2C.A.R.A.2250.EUR.N": "FRA_LOAN_RATE_HOUSE",
    "MIR1/M.FR.B.A2A.A.R.A.2240.EUR.N": "FRA_LOAN_RATE_NFC",
}


def _have_key() -> bool:
    return bool(os.environ.get("BDF_API_KEY", "").strip())


@unittest.skipUnless(_have_key(), "BDF_API_KEY not set — Webstat smoke skipped")
class BdFLiveSmokeTest(unittest.TestCase):
    def test_curated_series_resolve(self):
        problems = []
        for sid, col in CURATED.items():
            try:
                s = bdf_src.fetch_series_as_pandas(sid, col_name=col)
            except Exception as e:  # network/parse — treat as resolution failure
                problems.append(f"{sid} ({col}): raised {type(e).__name__}: {e}")
                continue
            if s is None or s.empty:
                problems.append(f"{sid} ({col}): no data — verify the Webstat key")
        self.assertFalse(
            problems,
            "Banque de France series did not resolve (provisional keys may need "
            "correction):\n  " + "\n  ".join(problems),
        )


if __name__ == "__main__":
    unittest.main()
