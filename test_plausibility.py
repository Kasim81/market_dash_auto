"""
test_plausibility.py — A9 data-credibility gate (offline, over committed CSVs).

Two layers:

  1. TestFamilyBands — pins the `_family_default_band` unit→band classification
     so a future edit can't silently mis-family a column (e.g. route a policy
     rate into the YoY band).

  2. TestCommittedDataPlausibility — runs the full Section E plausibility check
     over the CURRENTLY COMMITTED data/macro_economic_hist.csv and asserts every
     column's latest value sits inside its band. This is the "runs regularly as
     its own check" half of A9: because CI (.github/workflows/ci.yml) fires on
     every pull_request AND every push to main — including the daily data
     commit — a credibility regression (a sign flip, an x100/÷100 unit error, a
     wrong-column mapping: the Atlanta-Fed-24%-nowcast class) is caught here even
     when the daily fetch step itself "succeeds". A PR that would introduce one
     is BLOCKED; a direct daily data push that introduces one turns this check
     red for operator attention (the daily audit's Section E stays a warning-only
     channel — the escalation split is deliberate).

Network-free and key-free: reads only in-repo CSVs. Uses stdlib unittest.
"""

import unittest

import data_audit as da


class TestFamilyBands(unittest.TestCase):
    """`_family_default_band` classifies each series family to a sane band."""

    def _band(self, units, concept="", sub="", col=""):
        return da._family_default_band(units, concept, sub, col)

    def test_yoy_growth(self):
        lo, hi = self._band("Percent Change YoY", "Inflation", "CPI", "JPN_CPI_YOY")
        self.assertLess(lo, 0)
        self.assertGreaterEqual(hi, 100)   # room for volatile trade / high-inflation

    def test_policy_rate_allows_negative(self):
        lo, hi = self._band("Percent", "Rates / Yields", "Policy Rate", "EA_DEPOSIT_RATE")
        self.assertLessEqual(lo, 0)        # ECB/BoJ negative-rate history
        self.assertGreaterEqual(hi, 25)

    def test_yield_family(self):
        self.assertIsNotNone(self._band("% per annum", "Rates / Yields",
                                        "Government Yields", "ITA_BTP_10Y"))

    def test_net_balance_survey(self):
        lo, hi = self._band("Balance (% points)", "Sentiment / Survey", "", "EU_IND_CONF")
        self.assertEqual((lo, hi), (-100.0, 100.0))

    def test_sentiment_composite_spans_both_normalisations(self):
        # "normal value = 100" FRED/OECD confidence is heterogeneous (balances
        # AND centred-100), so the band must contain both -42 and +127.
        lo, hi = self._band("Composite indicator (normal value = 100)",
                            "Sentiment / Survey", "Business Sentiment", "DEU_BUS_CONF")
        self.assertLessEqual(lo, -50)
        self.assertGreaterEqual(hi, 130)

    def test_diffusion_pmi(self):
        lo, hi = self._band("Diffusion Index (50 = neutral)", "Survey", "PMI", "ISM_MFG_PMI")
        self.assertGreaterEqual(lo, 0)
        self.assertLessEqual(hi, 100)

    def test_index_level_growth(self):
        self.assertIsNotNone(self._band("Index 2020=100", "Growth", "Real Activity",
                                        "DEU_IND_PROD"))

    def test_level_family_has_no_static_band(self):
        # Nominal levels / prices trend across orders of magnitude → no family
        # band (per-column only), so they never false-positive.
        self.assertIsNone(self._band("USD (monthly value level)", "External / Trade",
                                     "Trade", "CHN_EXPORTS"))
        self.assertIsNone(self._band("GBP millions (level)", "Money / Liquidity",
                                     "Money Supply", "GBR_M2"))


class TestCommittedDataPlausibility(unittest.TestCase):
    """Every committed macro_economic column's latest value is inside its band."""

    def test_no_implausible_committed_values(self):
        result = da.section_e_plausibility()
        bad = result["implausible"]
        if bad:
            lines = [
                f"  {r['col_id']} = {r['value']:g} outside band "
                f"[{r['min']:g}, {r['max']:g}] (src={r['source']}, "
                f"series={r['series_id']}, last_obs={r['date']})"
                for r in sorted(bad, key=lambda r: r["col_id"])
            ]
            self.fail(
                "Section E flagged implausible committed value(s) — a sign flip, "
                "unit (x100/÷100) error, or wrong-column mapping, OR a family band "
                "that needs tightening/widening in data_audit._family_default_band "
                "/ the column's plausible_min|max:\n" + "\n".join(lines)
            )

    def test_bands_cover_a_meaningful_share_of_columns(self):
        # Guard against a refactor silently disabling the family-default layer
        # (which would drop coverage back to the ~20 explicitly-declared bands).
        bands = da.load_plausibility_bands()
        latest = da.load_latest_macro_values()
        covered = sum(1 for c in latest if c in bands)
        self.assertGreater(
            covered, 120,
            f"plausibility coverage collapsed to {covered}/{len(latest)} columns — "
            "the family-default layer is probably disabled",
        )


if __name__ == "__main__":
    unittest.main()
