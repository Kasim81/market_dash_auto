"""
test_calculators_parity.py — C7 refactor safety net (offline gate).

Asserts that every one of the 112 macro-market calculators still produces the
exact output frozen in test_fixtures/calculators_parity_golden.json. The golden
was generated from the pre-C7 monolith; the C7 split of compute_macro_market.py
into a calculators/ package must reproduce it byte-for-byte (a pure code move).

Regenerate intentionally with:  python calculators_parity_harness.py

See calculators_parity_harness.py for why each calc is fingerprinted directly
(EMPTY / RAISED:<type> / hash) rather than via the assembled CSV.
"""

import json
import unittest

import calculators_parity_harness as harness


class TestCalculatorParity(unittest.TestCase):
    def test_all_calculators_match_golden(self):
        with open(harness.GOLDEN_PATH, encoding="utf-8") as f:
            golden = json.load(f)
        live = harness.compute_fingerprints()

        self.assertEqual(
            set(golden), set(live),
            "indicator id set changed vs golden:\n"
            f"  only in golden: {sorted(set(golden) - set(live))}\n"
            f"  only in live:   {sorted(set(live) - set(golden))}",
        )

        diffs = [
            f"  {k}: golden={golden[k][:16]}… live={live[k][:16]}…"
            if len(golden[k]) == 64 or len(live[k]) == 64
            else f"  {k}: golden={golden[k]!r} live={live[k]!r}"
            for k in sorted(golden) if golden[k] != live[k]
        ]
        self.assertFalse(
            diffs,
            f"{len(diffs)} calculator(s) diverged from the pre-C7 golden — the "
            "refactor changed behaviour (or a moved calc lost a helper import, "
            "flipping a result to RAISED):\n" + "\n".join(diffs),
        )

    def test_golden_is_meaningfully_populated(self):
        # Guard against a golden that silently degraded to all-EMPTY (which would
        # make the parity assertion vacuous).
        with open(harness.GOLDEN_PATH, encoding="utf-8") as f:
            golden = json.load(f)
        hashed = sum(1 for v in golden.values() if len(v) == 64)
        self.assertGreater(hashed, 100,
                           f"golden has only {hashed} hashed calcs — regenerate it")


if __name__ == "__main__":
    unittest.main()
