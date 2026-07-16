"""calculators.common — shared helpers + constants for the Phase E
calculators (C7 split of compute_macro_market.py). Pure functions over
the comp_hist / macro_economic_hist frames; no network, no module state."""

from __future__ import annotations

import numpy as np
import pandas as pd
from datetime import datetime, timezone

ZSCORE_WINDOW = 156
ZSCORE_MIN_PERIODS = 52
_ALIGN_FFILL_LIMIT = 13

def _to_weekly_friday(series: pd.Series) -> pd.Series:
    """
    Resample an arbitrary-frequency series to weekly Friday close.
    Uses last observation in the week then forward-fills gaps (for monthly data).

    NaNs are dropped first so the returned series *ends at the last real
    value*: the unified hist leaves NaN beyond each column's bounded-fill
    window (2026-07-08 bounded-fill change), and resampling over those
    trailing NaNs then ffilling would re-fabricate the very currency the
    writer bound removed. Interior gaps (weeks between monthly prints)
    still fill as before.
    """
    if series.empty:
        return series
    series = series.dropna()
    if series.empty:
        return series
    return series.resample("W-FRI").last().ffill()


def _rolling_zscore(series: pd.Series) -> pd.Series:
    """
    Apply a rolling z-score normalisation to a weekly price/level series.

    Window and min_periods are controlled by the module-level constants:
      ZSCORE_WINDOW      — rolling window in weeks (default 260 = 5 years)
      ZSCORE_MIN_PERIODS — minimum observations before emitting a value (default 52)

    To change to a full-history expanding z-score set ZSCORE_WINDOW = None.
    See the Z-SCORE CONFIGURATION section at the top of this file.
    """
    roll = series.rolling(window=ZSCORE_WINDOW, min_periods=ZSCORE_MIN_PERIODS)
    mu   = roll.mean()
    sig  = roll.std().replace(0, np.nan)
    return (series - mu) / sig


def _get_col(df: pd.DataFrame, col: str) -> pd.Series:
    """
    Safely extract a column from a DataFrame.
    Returns an empty Series with the df index if the column is absent,
    so callers never receive a KeyError — they just get NaN-filled results.
    """
    if col in df.columns:
        return df[col].copy()
    return pd.Series(dtype=float, index=df.index, name=col)


def _p(df_comp: pd.DataFrame, ticker: str, usd: bool = False) -> pd.Series:
    """
    Extract a price series from the comp_hist DataFrame.
    Variant is 'USD' when usd=True, otherwise 'Local'.
    Falls back to the other variant if the requested one is empty/absent.
    """
    variant  = "USD" if usd else "Local"
    fallback = "Local" if usd else "USD"
    col      = f"{ticker}_{variant}"
    fb_col   = f"{ticker}_{fallback}"
    s = _get_col(df_comp, col).dropna()
    if s.empty:
        s = _get_col(df_comp, fb_col).dropna()
    return s


def _log_ratio(num: pd.Series, den: pd.Series) -> pd.Series:
    """
    Compute log(num / den) on the aligned intersection of both series.
    Returns an empty Series if either input is empty or denominator is zero.
    """
    aligned = pd.concat([num, den], axis=1).ffill(limit=_ALIGN_FFILL_LIMIT).dropna()
    if aligned.empty or aligned.shape[1] < 2:
        return pd.Series(dtype=float)
    n = aligned.iloc[:, 0]
    d = aligned.iloc[:, 1].replace(0, np.nan)
    return np.log(n / d).dropna()


def _arith_diff(a: pd.Series, b: pd.Series) -> pd.Series:
    """Arithmetic difference a - b on aligned intersection."""
    aligned = pd.concat([a, b], axis=1).ffill(limit=_ALIGN_FFILL_LIMIT).dropna()
    if aligned.empty or aligned.shape[1] < 2:
        return pd.Series(dtype=float)
    return (aligned.iloc[:, 0] - aligned.iloc[:, 1]).dropna()


def _sum_log_ratio(nums: list, dens: list) -> pd.Series:
    """
    log(sum(num_prices) / sum(den_prices)) on aligned intersection.
    nums / dens are lists of pd.Series already extracted from comp_hist.
    """
    all_s = nums + dens
    aligned = pd.concat(all_s, axis=1).ffill(limit=_ALIGN_FFILL_LIMIT).dropna()
    if aligned.empty or aligned.shape[1] < len(nums) + len(dens):
        return pd.Series(dtype=float)
    num_sum = aligned.iloc[:, :len(nums)].sum(axis=1)
    den_sum = aligned.iloc[:, len(nums):].sum(axis=1)
    den_sum = den_sum.replace(0, np.nan)
    return np.log(num_sum / den_sum).dropna()


def _yoy(series: pd.Series, freq: int = 52) -> pd.Series:
    """
    Year-over-year percentage change for a weekly series.
    freq=52 for weekly; uses shift(52) → one year back.
    Returns 100 * (x / x_1y_ago - 1).
    """
    prior = series.shift(freq)
    return (100.0 * (series / prior.replace(0, np.nan) - 1)).dropna()


def _taylor_gap(policy, pi, activity_gap_z, r_star, target):
    """Assemble the Taylor-style stance gap on the weekly-Friday spine.

    policy / pi are % levels; activity_gap_z is the ~0-centred standardized
    activity gap (empty → the gap term is 0). Requires policy and pi to
    overlap; returns policy_rate − taylor_implied."""
    policy = _to_weekly_friday(policy)
    pi = _to_weekly_friday(pi)
    if policy is None or policy.empty or pi is None or pi.empty:
        return pd.Series(dtype=float)
    frame = pd.concat({"policy": policy, "pi": pi}, axis=1)
    if activity_gap_z is not None and not activity_gap_z.empty:
        frame = frame.join(activity_gap_z.rename("gap"), how="left")
    else:
        frame["gap"] = 0.0
    frame["gap"] = frame["gap"].fillna(0.0)
    frame = frame.dropna(subset=["policy", "pi"])
    if frame.empty:
        return pd.Series(dtype=float)
    taylor_implied = r_star + frame["pi"] + 0.5 * (frame["pi"] - target) + 0.5 * frame["gap"]
    return frame["policy"] - taylor_implied


__all__ = [
    '_to_weekly_friday',
    '_rolling_zscore',
    '_get_col',
    '_p',
    '_log_ratio',
    '_arith_diff',
    '_sum_log_ratio',
    '_yoy',
    '_taylor_gap',
    'ZSCORE_WINDOW',
    'ZSCORE_MIN_PERIODS',
    '_ALIGN_FFILL_LIMIT',
]
