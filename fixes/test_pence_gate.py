"""
Unit test for FIX 2 — the `.L` pence divide-by-100 gate (Option A: gate on
currency).

Verifies WITHOUT a full pipeline run (no network) that:
  * `_is_pence_quoted` is True only for London (.L) GBP/GBX/GBp instruments.
  * A EUR-quoted London ETF (~EUR120) is NOT divided by 100.
  * A genuinely pence-quoted GBP London ticker (~2000 pence) IS divided by 100.
  * A low-priced GBP London ticker (~5, median<50) is left alone (unchanged
    behaviour, mirrors HYLH.L).

The end-to-end assertions reproduce the exact 3-line guard from
collect_comp_assets() (fetch_data.py) so we exercise the real gate function
without a live yfinance fetch.
"""
import sys
import os
import types

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# fetch_data.py runs three heavy pipeline phases at IMPORT time (after its
# __main__ guard): fetch_hist.run_comp_hist, fetch_macro_economic.
# run_phase_macro_economic, compute_macro_market.run_phase_e — the last of which
# rewrites data/macro_market*.csv. A unit test must not trigger those, so we
# pre-seed sys.modules with no-op stubs BEFORE importing fetch_data. This keeps
# the test hermetic and side-effect-free (no network, no CSV writes).
for _mod, _fn in (("fetch_hist", "run_comp_hist"),
                  ("fetch_macro_economic", "run_phase_macro_economic"),
                  ("compute_macro_market", "run_phase_e")):
    if _mod not in sys.modules:
        _stub = types.ModuleType(_mod)
        setattr(_stub, _fn, lambda *a, **k: None)
        sys.modules[_mod] = _stub

import fetch_data
from fetch_data import _is_pence_quoted, _should_convert_pence


def _apply_pence_guard(ticker, ccy, series):
    """Faithful reproduction of the fetch_data.collect_comp_assets pence branch:
        is_pence = _is_pence_quoted(ticker, ccy)   # via inst['pence']
        if is_pence:
            median_val = series.dropna().median()
            if _should_convert_pence(ticker, ccy, median_val):
                series = series / 100
    """
    is_pence = _is_pence_quoted(ticker, ccy)
    if is_pence:
        median_val = series.dropna().median()
        if _should_convert_pence(ticker, ccy, median_val):
            series = series / 100
    return series


def _mk(level):
    idx = pd.date_range("2024-01-01", periods=260, freq="B")
    return pd.Series(np.full(len(idx), float(level)), index=idx)


def run():
    failures = []

    # ---- structural gate ----
    gate_cases = [
        (("ISF.L",  "GBP"), True),   # London GBP index ETF
        (("VMID.L", "GBp"), True),   # GBp accepted
        (("XYZ.L",  "GBX"), True),   # GBX accepted
        (("IEAC.L", "EUR"), False),  # London EUR ETF — the misfire we stop
        (("IBGL.L", "EUR"), False),
        (("IFRB.L", "EUR"), False),
        (("IITB.L", "EUR"), False),
        (("HYLH.L", "USD"), False),  # London USD ETF
        (("SPY",    "USD"), False),  # US-listed, no .L
        (("FEZ",    "USD"), False),
    ]
    for (tk, ccy), expected in gate_cases:
        got = _is_pence_quoted(tk, ccy)
        ok = got is expected
        print(f"  _is_pence_quoted({tk!r:10}, {ccy!r:5}) = {got!s:5}  expect {expected!s:5}  {'OK' if ok else 'FAIL'}")
        if not ok:
            failures.append((tk, ccy, got, expected))

    print()

    # ---- decision helper (gate + pence-scale median guard) ----
    helper_cases = [
        (("ISF.L",  "GBP", 2000.0), True),   # pence-scale GBP London -> divide
        (("IEAC.L", "EUR", 120.0),  False),  # EUR London -> currency gate blocks
        (("LOWP.L", "GBP", 5.0),    False),  # GBP London but median<50 -> leave
        (("HYLH.L", "USD", 120.0),  False),  # USD London -> currency gate blocks
        (("SPY",    "GBP", 2000.0), False),  # no .L -> never
    ]
    for (tk, ccy, med), expected in helper_cases:
        got = _should_convert_pence(tk, ccy, med)
        ok = got is expected
        print(f"  _should_convert_pence({tk!r:10}, {ccy!r:5}, {med:7.1f}) = {got!s:5}  expect {expected!s:5}  {'OK' if ok else 'FAIL'}")
        if not ok:
            failures.append((tk, ccy, med, got, expected))

    print()

    # ---- end-to-end division behaviour ----
    # 1. EUR London ETF ~EUR120 -> must NOT be divided.
    s_eur = _mk(120.0)
    out_eur = _apply_pence_guard("IEAC.L", "EUR", s_eur)
    eur_ok = np.isclose(out_eur.iloc[-1], 120.0)
    print(f"  IEAC.L EUR ~120  -> last={out_eur.iloc[-1]:.4f}  (expect 120, NOT /100)  {'OK' if eur_ok else 'FAIL'}")
    if not eur_ok:
        failures.append("EUR .L wrongly divided")

    # 2. GBP London ticker ~2000 pence -> must be divided by 100 -> ~20.
    s_gbp = _mk(2000.0)
    out_gbp = _apply_pence_guard("ISF.L", "GBP", s_gbp)
    gbp_ok = np.isclose(out_gbp.iloc[-1], 20.0)
    print(f"  ISF.L  GBP ~2000 -> last={out_gbp.iloc[-1]:.4f}  (expect 20, IS /100)   {'OK' if gbp_ok else 'FAIL'}")
    if not gbp_ok:
        failures.append("GBP .L not divided")

    # 3. Low-priced GBP London ticker ~5 (median<50) -> left alone (HYLH.L-style).
    s_low = _mk(5.0)
    out_low = _apply_pence_guard("LOWP.L", "GBP", s_low)
    low_ok = np.isclose(out_low.iloc[-1], 5.0)
    print(f"  LOWP.L GBP ~5    -> last={out_low.iloc[-1]:.4f}  (expect 5, median<50 -> left alone)  {'OK' if low_ok else 'FAIL'}")
    if not low_ok:
        failures.append("low GBP .L wrongly divided")

    print()
    if failures:
        print(f"RESULT: FAIL ({len(failures)} problem(s)): {failures}")
        return 1
    print("RESULT: ALL PASS")
    return 0


if __name__ == "__main__":
    sys.exit(run())
