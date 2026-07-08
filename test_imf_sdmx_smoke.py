"""Live smoke test for the IMF Data Portal SDMX source wiring (§2.A A1).

`sources/imf_sdmx.py` talks to api.imf.org (the platform that replaced
dataservices.imf.org in the IMF's 2025 data.imf.org migration) and serves
the China inflation cluster: `CHN_CPI_YOY` (feeds `CN_INFL1` headline) and
`CHN_CPI_INDEX`. This test hits the live API to confirm what the unit
tests can't:

  1. The SDMX-CSV endpoint is reachable + parseable in the daily CI
     environment.
  2. The latest CHN CPI YoY lands in a plausible band (-10% <= x <= +30%)
     — wide enough for any real Chinese inflation print, tight enough to
     catch a unit / column-mapping regression (e.g. an index level in the
     YoY slot).
  3. The series isn't stale beyond 120 days — the IMF refreshes the CPI
     dataset monthly (observed lag ~1-2 months behind the NBS release);
     >120 days means the dataset has stalled the way the FRED OECD-MEI
     mirror did (frozen 2025-04), which is exactly the regression this
     source was wired to escape.

It is network-gated: if api.imf.org is unreachable it SKIPS rather than
fails, so a transient blip never blocks the daily data commit. A
*reachable* endpoint returning missing or implausible data DOES fail.

Set SKIP_NETWORK_TESTS=1 to force-skip (e.g. in a no-egress unit-test job).
"""
import os
import sys
import unittest
from datetime import date

os.environ.setdefault("FRED_API_KEY", "x")
os.environ.setdefault("SHEET_ID", "x")
os.environ.setdefault("GOOGLE_CREDENTIALS_JSON", "{}")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sources import imf_sdmx as imf_sdmx_src  # noqa: E402

CHN_CPI_YOY_ID = "IMF.STA,CPI/CHN.CPI._T.YOY_PCH_PA_PT.M"
PLAUSIBLE_LO, PLAUSIBLE_HI = -10.0, 30.0
MAX_STALENESS_DAYS = 120

# §3.18 regime-aa monthly-growth backfill (2026-07-08): the PI and QNEA
# dataflows now carry DEU/FRA/NLD/CHE industrial production and five
# quarterly real-GDP levels. One representative series per dataflow keeps
# the smoke cost low while still catching a dataflow-level stall (the PI
# JPN member is already frozen at 2023-11, so per-dataflow health is not
# hypothetical). Staleness bounds mirror the library rows'
# freshness_override_days (150 monthly / 210 quarterly).
DEU_IND_PROD_ID = "IMF.STA,PI/DEU.IND.SA_IX.M"
DEU_GDP_ID = "IMF.STA,QNEA/DEU.B1GQ.Q.SA.XDC.Q"
PI_MAX_STALENESS_DAYS = 150
QNEA_MAX_STALENESS_DAYS = 210


def _network_available() -> bool:
    if os.environ.get("SKIP_NETWORK_TESTS"):
        return False
    try:
        import requests
        requests.head("https://api.imf.org", timeout=10)
        return True
    except Exception:
        return False


@unittest.skipUnless(_network_available(), "api.imf.org unreachable — skipping live smoke test")
class ImfSdmxSmokeTest(unittest.TestCase):
    def test_library_loads(self):
        lib = imf_sdmx_src.load_library()
        self.assertGreaterEqual(len(lib), 2)
        cols = {r["col"] for r in lib}
        self.assertIn("CHN_CPI_YOY", cols)
        self.assertIn("CHN_CPI_INDEX", cols)

    def test_chn_cpi_yoy_live_plausible_fresh(self):
        s = imf_sdmx_src.fetch_series_as_pandas(CHN_CPI_YOY_ID, col_name="CHN_CPI_YOY")
        self.assertIsNotNone(s, "IMF SDMX returned no data for CHN CPI YoY")
        self.assertGreater(len(s), 300, "unexpectedly short history (should span 1994+)")
        last_val = float(s.iloc[-1])
        self.assertTrue(
            PLAUSIBLE_LO <= last_val <= PLAUSIBLE_HI,
            f"CHN CPI YoY {last_val} outside plausible band "
            f"[{PLAUSIBLE_LO}, {PLAUSIBLE_HI}] — unit/mapping regression?",
        )
        age_days = (date.today() - s.index[-1].date()).days
        self.assertLessEqual(
            age_days, MAX_STALENESS_DAYS,
            f"CHN CPI YoY last obs {s.index[-1].date()} is {age_days}d old — "
            f"the IMF CPI dataset appears to have stalled",
        )

    def test_pi_deu_ind_prod_live_deep_fresh(self):
        s = imf_sdmx_src.fetch_series_as_pandas(DEU_IND_PROD_ID, col_name="DEU_IND_PROD")
        self.assertIsNotNone(s, "IMF SDMX returned no data for DEU industrial production")
        self.assertLessEqual(
            s.index[0].year, 1960,
            f"PI DEU history starts {s.index[0].date()} — the deep backfill "
            f"(1958-01 verified at wiring) has been truncated",
        )
        last_val = float(s.iloc[-1])
        self.assertTrue(
            10.0 <= last_val <= 250.0,
            f"DEU IP index {last_val} outside plausible band — unit/mapping regression?",
        )
        age_days = (date.today() - s.index[-1].date()).days
        self.assertLessEqual(
            age_days, PI_MAX_STALENESS_DAYS,
            f"PI DEU last obs {s.index[-1].date()} is {age_days}d old — the "
            f"Production Indexes dataflow appears to have stalled (the JPN "
            f"member already froze at 2023-11)",
        )

    def test_qnea_deu_gdp_live_plausible_fresh(self):
        s = imf_sdmx_src.fetch_series_as_pandas(DEU_GDP_ID, col_name="DEU_GDP_INDEX")
        self.assertIsNotNone(s, "IMF SDMX returned no data for DEU quarterly real GDP")
        self.assertLessEqual(s.index[0].year, 1992, "QNEA DEU history truncated (1991-Q1 at wiring)")
        last_val = float(s.iloc[-1])
        self.assertTrue(
            2e11 <= last_val <= 2e12,
            f"DEU real GDP level {last_val:.3e} outside plausible band "
            f"(~7.7e11 EUR/quarter at wiring) — unit or scale regression?",
        )
        age_days = (date.today() - s.index[-1].date()).days
        self.assertLessEqual(
            age_days, QNEA_MAX_STALENESS_DAYS,
            f"QNEA DEU last obs {s.index[-1].date()} is {age_days}d old — the "
            f"QNEA dataflow appears to have stalled",
        )


if __name__ == "__main__":
    unittest.main()
