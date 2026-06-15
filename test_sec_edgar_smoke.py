"""Live smoke test for the SEC EDGAR companyfacts source wiring.

SEC EDGAR is the ultimate (primary) source for US-filer financial-statement
facts — revenue and diluted EPS are read straight from the XBRL companyfacts
API, no aggregator in between. This test exercises the full keyless path the
daily pipeline uses: resolve a ticker → CIK from company_tickers.json, fetch
that company's companyfacts document, and extract the quarterly + annual
revenue and diluted-EPS history.

It confirms three things the offline unit checks can't:

  1. The SEC fair-access User-Agent header is accepted and the endpoints are
     reachable + parseable in the daily CI environment.
  2. NVDA resolves to its known CIK (1045810) and both metrics return a
     non-empty multi-period series.
  3. Every emitted row carries the long/tidy schema downstream consumers rely
     on (ticker, metric, period_end, period_type ∈ {Q,A}, value, unit, fy, fp,
     form, source, retrieved).

It is network-gated — mirrors test_shiller_smoke.py / test_ny_fed_smoke.py.
If EDGAR is unreachable (offline dev box, or a sandbox whose egress allowlist
omits sec.gov — the SEC returns "Host not in allowlist" 403 there) it SKIPS
rather than fails, so a transient blip never blocks the daily data commit. A
*reachable* endpoint returning missing or malformed data DOES fail — that is
the regression signal we want.

Set SKIP_NETWORK_TESTS=1 to force-skip (e.g. in a no-egress unit-test job).
"""
import os
import sys
import unittest

os.environ.setdefault("FRED_API_KEY", "x")
os.environ.setdefault("SHEET_ID", "x")
os.environ.setdefault("GOOGLE_CREDENTIALS_JSON", "{}")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sources import sec_edgar as sec_src  # noqa: E402

NVDA_CIK = 1045810  # NVIDIA Corp — stable CIK, used as the reachability anchor.

_REQUIRED_COLS = [
    "ticker", "metric", "period_end", "period_type", "value", "unit",
    "fy", "fp", "form", "source", "retrieved",
]


def _reachable() -> bool:
    """Probe ticker→CIK resolution directly. We test the resolve path rather
    than going through build_fundamentals_df so a parsing regression doesn't
    masquerade as an unreachable endpoint."""
    try:
        return sec_src.resolve_cik("NVDA") == NVDA_CIK
    except Exception:
        return False


@unittest.skipIf(os.environ.get("SKIP_NETWORK_TESTS"), "network tests disabled")
class SecEdgarLiveSmokeTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not _reachable():
            raise unittest.SkipTest(
                "SEC EDGAR unreachable — skipping live smoke "
                "(sandbox egress allowlists often omit sec.gov, returning a "
                "403 'Host not in allowlist'; the daily CI run exercises this)"
            )
        cls.facts = sec_src.fetch_companyfacts(NVDA_CIK)

    def test_companyfacts_fetched(self):
        self.assertIsNotNone(
            self.facts, "NVDA companyfacts fetch returned None despite reachable CIK resolve"
        )
        self.assertIn("facts", self.facts)
        self.assertIn("us-gaap", self.facts["facts"])

    def test_revenue_series_non_empty(self):
        tags = ["RevenueFromContractWithCustomerExcludingAssessedTax",
                "Revenues", "SalesRevenueNet"]
        points = sec_src.extract_metric(self.facts, tags)
        self.assertTrue(points, "NVDA revenue extraction produced no points")
        self.assertTrue(any(p["period_type"] == "A" for p in points),
                        "NVDA revenue has no annual (A) points")
        self.assertTrue(any(p["period_type"] == "Q" for p in points),
                        "NVDA revenue has no quarterly (Q) points")
        # Revenue is a large positive USD figure.
        self.assertTrue(all(p["value"] > 0 for p in points),
                        "NVDA revenue has non-positive values")

    def test_eps_series_non_empty(self):
        points = sec_src.extract_metric(
            self.facts, ["EarningsPerShareDiluted", "EarningsPerShareBasic"]
        )
        self.assertTrue(points, "NVDA diluted-EPS extraction produced no points")
        self.assertTrue(any(p["period_type"] == "A" for p in points),
                        "NVDA EPS has no annual (A) points")

    def test_build_df_schema(self):
        rows = [r for r in sec_src.load_library() if r["ticker"] == "NVDA"]
        self.assertTrue(rows, "NVDA rows missing from macro_library_sec_edgar.csv")
        df = sec_src.build_fundamentals_df(rows)
        self.assertFalse(df.empty, "build_fundamentals_df returned empty for NVDA")
        self.assertEqual(list(df.columns), _REQUIRED_COLS,
                         "equity_fundamentals schema/column-order regression")
        self.assertEqual(set(df["metric"].unique()), {"revenue", "eps"},
                         "NVDA build missing one of revenue/eps")
        self.assertTrue(set(df["period_type"].unique()) <= {"Q", "A"},
                        "period_type must be Q or A")
        self.assertTrue((df["source"] == "SEC EDGAR").all(),
                        "source column must be 'SEC EDGAR'")


if __name__ == "__main__":
    unittest.main()
