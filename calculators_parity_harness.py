"""
calculators_parity_harness.py — byte-identical safety net for the C7 refactor.

C7 splits compute_macro_market.py's 112 `_calc_*` functions into a
`calculators/` package with **zero behaviour change**. This harness pins that:
it runs every calculator over the committed comp_hist / macro_economic_hist
frames plus a *fixed synthetic* ``supp`` (the only two non-CSV inputs —
``euro_ig_spread`` and ``fxi``) and reduces each indicator's output to a stable
fingerprint. The set of fingerprints is frozen into
``test_fixtures/calculators_parity_golden.json``; ``test_calculators_parity.py``
asserts the live run still reproduces it exactly.

Why fingerprint each calc directly (not just the assembled CSV): a refactor that
forgets to import a helper into a calc's new module raises ``NameError`` *inside*
``compute_all_indicators``' per-indicator ``try/except``, which silently degrades
the indicator to an empty frame. A golden built only from non-empty outputs
would not notice. Here each calc's fingerprint is a hash **or** the literal
``"EMPTY"`` **or** ``"RAISED:<ExcType>"`` — so an import break flips
``EMPTY``/``<hash>`` → ``RAISED:NameError`` and the parity test fails loudly.

Deterministic + offline: no network, fixed synthetic supp, committed CSV inputs.
"""

from __future__ import annotations

import hashlib
import json
import pathlib

import numpy as np
import pandas as pd

import compute_macro_market as cm

GOLDEN_PATH = pathlib.Path(__file__).parent / "test_fixtures" / "calculators_parity_golden.json"


def build_inputs():
    """Return (cp, me, supp) — the committed frames + a fixed synthetic supp.

    ``supp`` carries the only two inputs not in macro_economic_hist
    (``euro_ig_spread`` from ECB, ``fxi`` from yfinance). Real values are
    network-sourced and non-reproducible, so the harness substitutes fixed,
    positive, deterministically-varying series spanning the data range — enough
    to drive ``_calc_EU_Cr1`` and ``_calc_AS_CN_G3`` to non-empty output without
    any network. Parity is about code-move neutrality, so the exact numbers do
    not matter, only that they are identical across the before/after runs — and
    a committed constant guarantees that.
    """
    cp = cm.load_comp_hist()
    me = cm.load_macro_economic_hist()

    # euro_ig_spread: weekly, on the macro frame's own index. Deterministic ramp.
    n = len(me.index)
    eig = pd.Series(100.0 + (np.arange(n) % 40) * 0.1, index=me.index, name="euro_ig_spread")

    # fxi: a daily positive price series over the comp-hist span. Deterministic.
    daily = pd.date_range(cp.index.min(), cp.index.max(), freq="D")
    fxi = pd.Series(20.0 + (np.arange(len(daily)) % 100) * 0.05, index=daily, name="fxi")

    return cp, me, {"euro_ig_spread": eig, "fxi": fxi}


def _fingerprint_frame(df: pd.DataFrame) -> str:
    """Stable digest of a make_result frame (raw/zscore + regime/fwd_regime + index)."""
    h = hashlib.sha256()
    for col in ("raw", "zscore"):
        if col in df.columns:
            vals = "|".join("nan" if pd.isna(x) else f"{float(x):.8f}" for x in df[col])
            h.update(f"{col}:{vals}\n".encode())
    for col in ("regime", "fwd_regime"):
        if col in df.columns:
            vals = "|".join("" if pd.isna(x) else str(x) for x in df[col])
            h.update(f"{col}:{vals}\n".encode())
    h.update(("idx:" + "|".join(d.isoformat() for d in df.index)).encode())
    return h.hexdigest()


def compute_fingerprints() -> dict[str, str]:
    """Fingerprint every indicator in ALL_INDICATOR_IDS. Each value is a sha256
    hex digest, or ``"EMPTY"``, or ``"NO_CALC"``, or ``"RAISED:<ExcType>"``."""
    cp, me, supp = build_inputs()
    out: dict[str, str] = {}
    for ind_id in cm.ALL_INDICATOR_IDS:
        fn = cm._ALL_CALCULATORS.get(ind_id)
        if fn is None:
            out[ind_id] = "NO_CALC"
            continue
        try:
            raw = fn(cp=cp, mu=me, mi=me, supp=supp, dbn=me)
            df = cm.make_result(raw, ind_id)
        except Exception as exc:                     # noqa: BLE001
            out[ind_id] = f"RAISED:{type(exc).__name__}"
            continue
        out[ind_id] = "EMPTY" if (df is None or df.empty) else _fingerprint_frame(df)
    return out


def write_golden() -> dict[str, str]:
    fps = compute_fingerprints()
    GOLDEN_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(GOLDEN_PATH, "w", encoding="utf-8") as f:
        json.dump(fps, f, indent=2, sort_keys=True)
        f.write("\n")
    return fps


if __name__ == "__main__":
    fps = write_golden()
    n_hash = sum(1 for v in fps.values() if len(v) == 64)
    n_empty = sum(1 for v in fps.values() if v == "EMPTY")
    n_raise = sum(1 for v in fps.values() if v.startswith("RAISED:"))
    n_nocalc = sum(1 for v in fps.values() if v == "NO_CALC")
    print(f"wrote {GOLDEN_PATH} — {len(fps)} indicators: "
          f"{n_hash} hashed, {n_empty} empty, {n_raise} raised, {n_nocalc} no-calc")
