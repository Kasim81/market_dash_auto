"""
test_calculators_parity.py — C7 calculator-integrity gate (offline).

Guards the lasting risk from the C7 split of compute_macro_market.py into a
calculators/ package: a moved calc that references a helper not imported into its
new module raises NameError (which compute_all_indicators would silently swallow
into an empty indicator). Data-independent by design — see
calculators_parity_harness for why the earlier value-hash golden was replaced
(it broke CI on ordinary daily data commits).
"""

import unittest

import calculators_parity_harness as harness
import compute_macro_market as cm


class TestCalculatorIntegrity(unittest.TestCase):
    def test_every_indicator_has_a_callable_calculator(self):
        self.assertGreaterEqual(len(cm.ALL_INDICATOR_IDS), 112)
        missing = [i for i in cm.ALL_INDICATOR_IDS
                   if not callable(cm._ALL_CALCULATORS.get(i))]
        self.assertFalse(missing, f"indicator id(s) with no calculator: {missing}")

    def test_no_calculator_has_import_breakage(self):
        result = harness.classify_calculators()
        broken = {k: v for k, v in result.items() if v.startswith("BROKEN:")}
        self.assertFalse(
            broken,
            "calculator(s) raised an import-class error — a moved calc likely "
            "lost a helper import in the calculators/ package:\n"
            + "\n".join(f"  {k}: {v}" for k, v in sorted(broken.items())),
        )
        no_calc = [k for k, v in result.items() if v == "NO_CALC"]
        self.assertFalse(no_calc, f"indicator(s) with no registered calculator: {no_calc}")


if __name__ == "__main__":
    unittest.main()
