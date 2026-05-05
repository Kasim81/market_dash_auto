"""
Equation library for `Data_Pipeline_Project_Report.docx`.

Each function returns a fully-wrapped `<m:oMath>` OMML string ready to
pass directly to `_omml.add_inline_equation` or
`_omml.add_display_equation`.

Conventions (per OMML typographic standards):

  * single letters (r, x, t, z, y, β, μ, σ) — italic (default).
  * multi-letter labels (USD, local, FX, ticker symbols, "median")
    — pass with `plain=True` so they render upright.
  * function names (log, sign, max) — `func()` sets `plain_name=True`
    automatically.

The equation labels in this module match the labels used in the
report body so cross-references stay resolvable.
"""

import _omml as M


# ── helpers local to this module ────────────────────────────────────────

def _R(t):
    """Italic single-symbol run (shorthand)."""
    return M.run(t)


def _P(t):
    """Plain (upright) multi-letter run."""
    return M.run(t, plain=True)


def _OP(s):
    """Operator / punctuation run — no styling override."""
    return M.run(s)


def _z():
    return _R("z")


def _z_at(offset_label):
    """z_{t-Δ} for a given offset label."""
    return M.sub(_z(), _P(offset_label))


def _abs_z(offset_label=None):
    z = _z() if offset_label is None else _z_at(offset_label)
    return M.abs_(z)


# ── §3 / §5 — pipeline mechanics ─────────────────────────────────────────

def usd_return():
    """Eq. r_USD identity — FX-adjusted return composition."""
    r_usd   = M.sub(_R("r"), _P("USD"))
    r_local = M.sub(_R("r"), _P("local"))
    r_fx    = M.sub(_R("r"), _P("FX"))
    return M.oMath(
        r_usd, _OP("="),
        M.paren(_P("1+") + r_local),
        M.paren(_P("1+") + r_fx),
        _OP("−1"),
    )


def pence_correction():
    """LSE pence correction — piecewise on .L suffix and median."""
    x_prime = M.sup(_R("x"), _R("′"))
    case_div = (
        M.frac(_R("x"), _P("100"))
        + _P(",   if ticker ends ‘.L’ and median(x) > 50")
    )
    case_id = (
        _R("x")
        + _P(",   otherwise")
    )
    return M.oMath(
        x_prime, _OP("="),
        M.cases(case_div, case_id),
    )


def friday_spine():
    """Friday-spine alignment — S^F_t = S(τ), τ ≤ t."""
    s_f = M.subsup(_R("S"), _R("t"), _P("F"))
    rhs = _R("S") + M.paren(_R("τ"))
    where = (
        _P(",   τ = max")
        + M.paren(_P("s ≤ t : S(s) defined"))
    )
    return M.oMath(s_f, _OP("="), rhs, where)


# ── §6 — Phase E core methodology ────────────────────────────────────────

def rolling_zscore():
    """Rolling z-score: z_t = (x_t − μ_W(t)) / σ_W(t)."""
    z_t   = M.sub(_z(), _R("t"))
    x_t   = M.sub(_R("x"), _R("t"))
    mu_W  = M.sub(_R("μ"), _R("W"))
    sg_W  = M.sub(_R("σ"), _R("W"))
    num   = x_t + _OP("−") + mu_W + M.paren(_R("t"))
    den   = sg_W + M.paren(_R("t"))
    return M.oMath(
        z_t, _OP("="), M.frac(num, den),
    )


def zscore_window():
    """μ_W(t) = (1/W) Σ x_{t-i}, i = 0..W-1, with W = 156, min_periods = 52."""
    mu  = M.sub(_R("μ"), _R("W")) + M.paren(_R("t"))
    sum_body = M.sub(_R("x"), _R("t−i"))
    sigma = M.sum_over(
        _R("i"),
        _P("i=0"),
        _P("W−1"),
        sum_body,
    )
    rhs = M.frac(_P("1"), _R("W")) + sigma
    note = _P(",   W = 156,   min_periods = 52")
    return M.oMath(mu, _OP("="), rhs, note)


def log_ratio():
    """Generic log-ratio indicator: I_t = log(N_t / D_t)."""
    I_t = M.sub(_R("I"), _R("t"))
    N_t = M.sub(_R("N"), _R("t"))
    D_t = M.sub(_R("D"), _R("t"))
    return M.oMath(
        I_t, _OP("="),
        M.func("log", M.frac(N_t, D_t)),
    )


def sum_log_ratio():
    """Composite log-ratio: I_t = (1/k) Σ log(N_{i,t}/D_{i,t})."""
    I_t   = M.sub(_R("I"), _R("t"))
    N_it  = M.sub(_R("N"), _P("i,t"))
    D_it  = M.sub(_R("D"), _P("i,t"))
    log_term = M.func("log", M.frac(N_it, D_it))
    sigma = M.sum_over(_R("i"), _P("i=1"), _R("k"), log_term)
    return M.oMath(
        I_t, _OP("="),
        M.frac(_P("1"), _R("k")), sigma,
    )


def arith_diff():
    """Arithmetic-difference indicator: I_t = a_t − b_t."""
    I_t = M.sub(_R("I"), _R("t"))
    a_t = M.sub(_R("a"), _R("t"))
    b_t = M.sub(_R("b"), _R("t"))
    return M.oMath(I_t, _OP("="), a_t, _OP("−"), b_t)


def yoy_monthly():
    """Monthly year-on-year transform: YoY(x_t) = (x_t − x_{t−12})/x_{t−12}."""
    lhs = _P("YoY") + M.paren(M.sub(_R("x"), _R("t")))
    x_t   = M.sub(_R("x"), _R("t"))
    x_t12 = M.sub(_R("x"), _P("t−12"))
    return M.oMath(
        lhs, _OP("="),
        M.frac(x_t + _OP("−") + x_t12, x_t12),
    )


# ── §7 — regime, forward-regime, z-score-trend classification ────────────

def regime_3bucket():
    """Generic 3-bucket regime classifier on z."""
    rhs_pos = _P("L₊") + _P(",   if z > +1")
    rhs_neu = _P("L₀") + _P(",   if |z| ≤ 1")
    rhs_neg = _P("L₋") + _P(",   if z < −1")
    return M.oMath(
        _P("regime") + M.paren(_z()), _OP("="),
        M.cases(rhs_pos, rhs_neu, rhs_neg),
    )


def fwd_slope():
    """Forward-regime slope: β = (z_t − z_{t−8}) / 8."""
    num = M.sub(_z(), _R("t")) + _OP("−") + _z_at("t−8")
    return M.oMath(
        _R("β"), _OP("="),
        M.frac(num, _P("8")),
    )


def fwd_regime():
    """Forward regime — piecewise on β with ±0.15 thresholds."""
    rhs_imp = _P("improving") + _P(",       if β > +0.15")
    rhs_sta = _P("stable")    + _P(",         if |β| ≤ 0.15")
    rhs_det = _P("deteriorating") + _P(",  if β < −0.15")
    return M.oMath(
        _P("fwd_regime"), _OP("="),
        M.cases(rhs_imp, rhs_sta, rhs_det),
    )


def trend_intensifying():
    """Trend = intensifying condition."""
    cond = (
        _abs_z("t") + _OP(">") + _abs_z("t−1")
        + _P("    ∧    ")
        + _abs_z("t") + _OP(">") + _abs_z("t−4")
        + _P("    ∧    ")
        + _abs_z("t") + _OP("≥") + _P("0.9 ·")
        + _P("max") + M.sub(_P(""), _P("[t−13, t]")) + M.abs_(_z())
    )
    return M.oMath(
        _P("intensifying:    "), cond,
    )


def trend_fading():
    """Trend = fading condition."""
    return M.oMath(
        _P("fading:    "),
        _abs_z("t"), _OP("<"), _P("0.9 ·"), _abs_z("t−4"),
    )


def trend_reversing():
    """Trend = reversing condition."""
    sgn_now = _P("sgn") + M.paren(_z_at("t"))
    sgn_pre = _P("sgn") + M.paren(_z_at("t−4"))
    return M.oMath(
        _P("reversing:    "),
        sgn_now, _OP("≠"), sgn_pre,
        _P("    ∧    "),
        _abs_z("t−4"), _OP(">"), _P("0.5"),
    )


# ── §6 — six worked-example indicator formulae ───────────────────────────

def eq_us_g1():
    """US_G1 — Cyclicals vs Defensives: I = log(XLY/XLP)."""
    return M.oMath(
        _R("I"), _OP("="),
        M.func("log", M.frac(_P("XLY"), _P("XLP"))),
    )


def eq_us_g2():
    """US_G2 — Broader Cyclicals vs Defensives: I = log((XLI+XLF)/(XLU+XLP))."""
    return M.oMath(
        _R("I"), _OP("="),
        M.func("log",
               M.frac(_P("XLI") + _OP("+") + _P("XLF"),
                      _P("XLU") + _OP("+") + _P("XLP"))),
    )


def eq_us_r1():
    """US_R1 — Yield curve 10Y−3M: I = y_10Y − y_3M."""
    y10 = M.sub(_R("y"), _P("10Y"))
    y3m = M.sub(_R("y"), _P("3M"))
    return M.oMath(_R("I"), _OP("="), y10, _OP("−"), y3m)


def eq_us_v1():
    """US_V1 — VIX term structure: I = VIX3M − VIX."""
    return M.oMath(
        _R("I"), _OP("="),
        _P("VIX3M"), _OP("−"), _P("VIX"),
    )


def eq_fx_cmd1():
    """FX_CMD1 — Copper / Gold: I = log(copper / gold)."""
    return M.oMath(
        _R("I"), _OP("="),
        M.func("log", M.frac(_P("copper"), _P("gold"))),
    )


def eq_gl_pmi1():
    """GL_PMI1 — Global PMI proxy: I = (1/n) Σ z_i across regions."""
    z_i = M.sub(_z(), _R("i"))
    sigma = M.sum_over(_R("i"), _P("i=1"), _R("n"), z_i)
    return M.oMath(
        _R("I"), _OP("="),
        M.frac(_P("1"), _R("n")), sigma,
    )


def eq_us_r1_regime():
    """US_R1 — yield-curve regime with level override (4-row piecewise)."""
    I_t = M.sub(_R("I"), _R("t"))
    z_t = M.sub(_z(), _R("t"))
    rhs1 = _P("recession-watch") + _P(",   if I_t < 0")
    rhs2 = _P("early-cycle")     + _P(",       if I_t > 0   ∧   z_t > +1")
    rhs3 = _P("mid-cycle")       + _P(",         if I_t > 0   ∧   |z_t| ≤ 1")
    rhs4 = _P("late-cycle")      + _P(",        if I_t > 0   ∧   z_t < −1")
    return M.oMath(
        _P("regime") + M.paren(I_t + _P(", ") + z_t),
        _OP("="),
        M.cases(rhs1, rhs2, rhs3, rhs4),
    )


def eq_us_cr2_regime():
    """US_Cr2 — 5-regime credit-spread classifier."""
    rhs1 = _P("opportunity") + _P(",   if HY_OAS > 800   ∨   z > +2")
    rhs2 = _P("stress")      + _P(",            if HY_OAS > 500   ∧   z > +1")
    rhs3 = _P("normal")      + _P(",          if 400 ≤ HY_OAS ≤ 600   ∧   |z| < 1")
    rhs4 = _P("complacent")  + _P(",   if HY_OAS < 400   ∧   z < −0.5")
    rhs5 = _P("frothy")      + _P(",            if HY_OAS < 300   ∧   z < −1")
    return M.oMath(
        _P("regime"), _OP("="),
        M.cases(rhs1, rhs2, rhs3, rhs4, rhs5),
    )


# ── §8 — operational scaffolding ─────────────────────────────────────────

def staleness_age():
    """age(s) = t_now − t_change(s)."""
    t_now    = M.sub(_R("t"), _P("now"))
    t_change = M.sub(_R("t"), _P("change")) + M.paren(_R("s"))
    return M.oMath(
        _P("age") + M.paren(_R("s")), _OP("="),
        t_now, _OP("−"), t_change,
    )


def staleness_classification():
    """FRESH / STALE / EXPIRED bands relative to per-frequency tolerance T."""
    rhs1 = _P("FRESH")   + _P(",         if age ≤ T")
    rhs2 = _P("STALE")   + _P(",         if T < age ≤ 2T")
    rhs3 = _P("EXPIRED") + _P(",   if age > 2T")
    return M.oMath(
        _P("classify") + M.paren(_P("age")),
        _OP("="),
        M.cases(rhs1, rhs2, rhs3),
    )


# ── catalogue (used by the probe renderer) ───────────────────────────────

CATALOGUE = [
    # (label, builder, brief description)
    ("USD-adjusted return identity",        usd_return,            "FX composition for foreign-currency instruments"),
    ("LSE pence correction",                pence_correction,      "Dynamic divisor for ‘.L’ tickers reporting in GBp"),
    ("Friday-spine alignment",              friday_spine,          "Weekly snapshot from arbitrary-cadence series"),
    ("Rolling z-score",                     rolling_zscore,        "Three-year window, 52-week warm-up"),
    ("Window mean (μ_W)",                   zscore_window,         "Window definition, parameter values"),
    ("Log-ratio indicator family",          log_ratio,             "Primary calculator template"),
    ("Composite log-ratio",                 sum_log_ratio,         "Multi-input log-ratio average"),
    ("Arithmetic-difference indicator",     arith_diff,            "Used for yield-curve and spread differences"),
    ("Year-on-year transform",              yoy_monthly,           "Monthly cadence YoY change"),
    ("3-bucket regime classifier",          regime_3bucket,        "Standard ±1σ regime helper"),
    ("Forward-regime slope",                fwd_slope,             "Eight-week z-score slope"),
    ("Forward-regime classification",       fwd_regime,            "Piecewise on β with ±0.15 thresholds"),
    ("Z-score trend — intensifying",        trend_intensifying,    ""),
    ("Z-score trend — fading",              trend_fading,          ""),
    ("Z-score trend — reversing",           trend_reversing,       ""),
    ("US_G1 — XLY / XLP",                   eq_us_g1,              "Equity rotation worked example"),
    ("US_G2 — (XLI+XLF) / (XLU+XLP)",       eq_us_g2,              "Composite equity rotation"),
    ("US_R1 — 10Y − 3M",                    eq_us_r1,              "Yield curve, raw"),
    ("US_R1 — regime (level override)",     eq_us_r1_regime,       "Yield-curve regime with inversion override"),
    ("US_Cr2 — 5-regime classifier",        eq_us_cr2_regime,      "HY credit spread"),
    ("US_V1 — VIX3M − VIX",                 eq_us_v1,              "Volatility term structure"),
    ("FX_CMD1 — log(copper / gold)",        eq_fx_cmd1,            "Cross-asset growth proxy"),
    ("GL_PMI1 — equal-weight PMI z-mean",   eq_gl_pmi1,            "Survey-derived composite"),
    ("Staleness age",                       staleness_age,         "Audit Section C metric"),
    ("Staleness band classification",       staleness_classification, "FRESH / STALE / EXPIRED thresholds"),
]
