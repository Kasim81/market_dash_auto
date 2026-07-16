"""
test_equity_pe.py — offline tests for the §3.3 equity-P/E orchestration.

Network-free: the yfinance / Alpha Vantage fetchers are dependency-injected, so
the source-chain preference, the drop-on-miss behaviour, and the upsert/dedup
history logic are all exercised without touching the network. Runs in the
ci.yml offline gate.
"""

import pathlib
import tempfile
import unittest

import pandas as pd

from sources import equity_pe as ep


class TestSourceChain(unittest.TestCase):
    def test_yfinance_wins_when_present(self):
        yf = lambda t: {"pe_ttm": 25.0, "pe_forward": 22.0, "name": "SPDR"}
        av = lambda t: {"pe_ttm": 99.0, "pe_forward": 88.0, "name": "AV"}
        row = ep.fetch_pe_row("SPY", "S&P 500", yf_fn=yf, av_fn=av)
        self.assertEqual(row["source"], "yfinance")
        self.assertEqual(row["pe_ttm"], 25.0)
        self.assertEqual(row["name"], "SPDR")

    def test_av_fallback_when_yfinance_misses(self):
        yf = lambda t: None
        av = lambda t: {"pe_ttm": 18.5, "pe_forward": None, "name": "AV name"}
        row = ep.fetch_pe_row("EEM", "MSCI EM", yf_fn=yf, av_fn=av)
        self.assertEqual(row["source"], "alpha_vantage")
        self.assertEqual(row["pe_ttm"], 18.5)
        self.assertIsNone(row["pe_forward"])

    def test_label_used_when_source_name_missing(self):
        yf = lambda t: {"pe_ttm": 10.0, "pe_forward": None, "name": None}
        row = ep.fetch_pe_row("VGK", "FTSE Europe", yf_fn=yf, av_fn=lambda t: None)
        self.assertEqual(row["name"], "FTSE Europe")

    def test_row_dropped_when_all_sources_miss(self):
        row = ep.fetch_pe_row("XXX", "Nothing", yf_fn=lambda t: None, av_fn=lambda t: None)
        self.assertIsNone(row)

    def test_build_snapshot_drops_missing_tickers(self):
        tickers = [("A", "Alpha"), ("B", "Bravo"), ("C", "Charlie")]
        yf = lambda t: {"pe_ttm": 20.0, "pe_forward": None, "name": t} if t != "B" else None
        snap = ep.build_snapshot("2026-07-16", tickers=tickers, yf_fn=yf, av_fn=lambda t: None)
        self.assertEqual({r["ticker"] for r in snap}, {"A", "C"})
        self.assertTrue(all(r["asof_date"] == "2026-07-16" for r in snap))

    def test_coerce_pe_rejects_nonpositive_and_junk(self):
        self.assertEqual(ep._coerce_pe("25.7"), 25.7)
        for bad in (None, "None", "n/a", 0, -3.0, float("nan"), 2e6):
            self.assertIsNone(ep._coerce_pe(bad), bad)


class TestUpsertHistory(unittest.TestCase):
    def _tmp(self):
        d = tempfile.mkdtemp()
        return pathlib.Path(d) / "equity_pe_snapshot.csv"

    def test_accumulates_and_upserts_same_day(self):
        path = self._tmp()
        # day 1
        ep.upsert_snapshot([{"asof_date": "2026-07-16", "ticker": "SPY", "name": "S&P",
                             "pe_ttm": 25.0, "pe_forward": 22.0, "source": "yfinance"}], path)
        # re-run same day with a corrected value → must UPDATE, not duplicate
        out = ep.upsert_snapshot([{"asof_date": "2026-07-16", "ticker": "SPY", "name": "S&P",
                                   "pe_ttm": 26.0, "pe_forward": 22.0, "source": "yfinance"}], path)
        spy = out[(out["asof_date"] == "2026-07-16") & (out["ticker"] == "SPY")]
        self.assertEqual(len(spy), 1)
        self.assertEqual(float(spy.iloc[0]["pe_ttm"]), 26.0)
        # day 2 → history grows
        out = ep.upsert_snapshot([{"asof_date": "2026-07-17", "ticker": "SPY", "name": "S&P",
                                   "pe_ttm": 27.0, "pe_forward": 23.0, "source": "yfinance"}], path)
        self.assertEqual(out["asof_date"].nunique(), 2)
        self.assertEqual(len(out), 2)

    def test_empty_rows_never_wipe_history(self):
        path = self._tmp()
        ep.upsert_snapshot([{"asof_date": "2026-07-16", "ticker": "SPY", "name": "S&P",
                             "pe_ttm": 25.0, "pe_forward": 22.0, "source": "yfinance"}], path)
        out = ep.upsert_snapshot([], path)          # total fetch miss
        self.assertEqual(len(out), 1)
        self.assertTrue(path.exists())

    def test_columns_are_stable(self):
        path = self._tmp()
        ep.upsert_snapshot([{"asof_date": "2026-07-16", "ticker": "SPY", "name": "S&P",
                             "pe_ttm": 25.0, "pe_forward": 22.0, "source": "yfinance"}], path)
        self.assertEqual(list(pd.read_csv(path).columns), ep._COLUMNS)


if __name__ == "__main__":
    unittest.main()
