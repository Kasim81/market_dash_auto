"""Deterministic (offline) regression tests for the e-Stat time parsing.

These guard the two bugs fixed in the 2026-06-15 JPN_IND_PROD / JPN_MACH_ORDERS
repointing: ``_parse_estat_time`` previously assumed a ``YYYYMM0000`` monthly
@time layout that never matches live data (so every monthly series parsed to
zero observations), and ``parse_response`` could not resolve tables whose @time
field is an opaque sequence code (e.g. METI's IIP table 0004052177) whose human
period label lives in CLASS_INF.

No network: synthetic getStatsData payloads only.
"""
import os
import sys
import unittest
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sources import estat  # noqa: E402


class ParseEstatTime(unittest.TestCase):
    def test_monthly_10digit(self):
        # Live e-Stat monthly 時間軸 codes: YYYY + "00" + MM + MM.
        self.assertEqual(estat._parse_estat_time("2026000303"), date(2026, 3, 1))
        self.assertEqual(estat._parse_estat_time("1985000101"), date(1985, 1, 1))
        self.assertEqual(estat._parse_estat_time("1985001212"), date(1985, 12, 1))

    def test_annual_marker(self):
        self.assertEqual(estat._parse_estat_time("2025000000"), date(2025, 12, 31))

    def test_bare_yyyymm_label(self):
        # CLASS_INF period labels e-Stat returns for opaque-coded tables.
        self.assertEqual(estat._parse_estat_time("202603"), date(2026, 3, 1))

    def test_non_period_returns_none(self):
        self.assertIsNone(estat._parse_estat_time("付加生産ウエイト"))
        self.assertIsNone(estat._parse_estat_time(""))


def _doc(values, time_class):
    return {"GET_STATS_DATA": {"STATISTICAL_DATA": {
        "CLASS_INF": {"CLASS_OBJ": [{"@id": "time", "CLASS": time_class}]},
        "DATA_INF": {"VALUE": values},
    }}}


class ParseResponse(unittest.TestCase):
    def test_period_encoded_time(self):
        # Machinery-orders style: @time is itself a period code.
        doc = _doc(
            [{"@time": "2026000303", "$": "1010890.9"},
             {"@time": "2026000202", "$": "999000.0"}],
            [{"@code": "2026000303", "@name": "Mar. 2026"},
             {"@code": "2026000202", "@name": "Feb. 2026"}],
        )
        obs = estat.parse_response(doc, "x")
        self.assertEqual([d for d, _ in obs],
                         [date(2026, 2, 1), date(2026, 3, 1)])

    def test_opaque_time_resolved_via_label(self):
        # IIP style: @time is an opaque sequence code; the period label
        # (and a non-period "weight" row that must be skipped) live in CLASS_INF.
        doc = _doc(
            [{"@time": "0100100", "$": "10000"},      # 付加生産ウエイト weight row -> skip
             {"@time": "0519500", "$": "102.4"},
             {"@time": "0519700", "$": "102.0"}],
            [{"@code": "0100100", "@name": "付加生産ウエイト"},
             {"@code": "0519500", "@name": "202602"},
             {"@code": "0519700", "@name": "202603"}],
        )
        obs = estat.parse_response(doc, "x")
        self.assertEqual(obs, [(date(2026, 2, 1), 102.4), (date(2026, 3, 1), 102.0)])


if __name__ == "__main__":
    unittest.main()
