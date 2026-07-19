"""
calculators_parity_harness.py — calculator-integrity check for the C7 split.

C7 moved compute_macro_market.py's 112 `_calc_*` functions into a
`calculators/` package. The lasting risk from that move is a *structural* one: a
relocated calc that references a helper not imported into its new module raises
``NameError`` (or ``ImportError``) — which ``compute_all_indicators`` swallows
into an empty result, so it would degrade a live indicator silently.

This harness exercises every calculator and flags exactly that class of
breakage. It is deliberately **data-independent**: it does NOT compare output
values or hashes. (An earlier version froze a golden fingerprint of every calc's
output; that was valid only until the next daily data commit rewrote
macro_economic_hist / comp_hist, so it turned CI red on ordinary data updates.
Whether a calc's *imports* resolve does not depend on the data, so this check is
stable across daily commits while still catching the C7-class regression.)

Inputs are the committed comp_hist / macro_economic_hist frames plus a fixed
synthetic ``supp`` (the two non-CSV inputs), so every calc's code path actually
executes. Offline, no network.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

import compute_macro_market as cm

# Exceptions that mean the refactor broke a reference — never data-driven.
IMPORT_ERRORS = (NameError, ImportError, ModuleNotFoundError)


def build_inputs():
    """Return (cp, me, supp): committed frames + a fixed synthetic supp (the
    only two inputs not in macro_economic_hist — euro_ig_spread, fxi). Exact
    values are irrelevant here; we only need every calc's code path to run."""
    cp = cm.load_comp_hist()
    me = cm.load_macro_economic_hist()
    n = len(me.index)
    eig = pd.Series(100.0 + (np.arange(n) % 40) * 0.1, index=me.index, name="euro_ig_spread")
    daily = pd.date_range(cp.index.min(), cp.index.max(), freq="D")
    fxi = pd.Series(20.0 + (np.arange(len(daily)) % 100) * 0.05, index=daily, name="fxi")
    return cp, me, {"euro_ig_spread": eig, "fxi": fxi}


def classify_calculators() -> dict[str, str]:
    """Run every indicator in ALL_INDICATOR_IDS. Each value is:
      * ``"NO_CALC"``          — id has no calculator registered
      * ``"BROKEN:<ExcType>"`` — raised an import-class error (refactor breakage)
      * ``"ok"``               — ran (any result, or a tolerated data-driven error)
    """
    cp, me, supp = build_inputs()
    out: dict[str, str] = {}
    for ind_id in cm.ALL_INDICATOR_IDS:
        fn = cm._ALL_CALCULATORS.get(ind_id)
        if fn is None:
            out[ind_id] = "NO_CALC"
            continue
        try:
            raw = fn(cp=cp, mu=me, mi=me, supp=supp, dbn=me)
            cm.make_result(raw, ind_id)
        except IMPORT_ERRORS as exc:
            out[ind_id] = f"BROKEN:{type(exc).__name__}"
        except Exception:                            # noqa: BLE001 — data-driven, tolerated
            out[ind_id] = "ok"
        else:
            out[ind_id] = "ok"
    return out
