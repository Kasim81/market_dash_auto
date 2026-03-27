# Multi-Frequency Data Pipeline Plan (Phase 2)

## Context

After reverting main to weekly Friday spine (Phase 1), this branch implements native-frequency storage with ragged columns — each series gets its own date + value columns, only as long as data exists. This eliminates wasted cells from forward-filling monthly/quarterly data to daily/weekly, and gives us genuine daily granularity for market prices.

**Branch:** `data_pipeline_multifreq` (created from main after Phase 1)

---

## Design: Ragged Column Format

Each series gets its own date column + value column(s):
```
Date_SPY  | SPY_Local | SPY_USD | Date_UNRATE | UNRATE  | ...
1990-01-02| 35.2      | 35.2    | 1990-01-01  | 5.4     |
1990-01-03| 35.5      | 35.5    | 1990-02-01  | 5.3     |
1990-01-04| 35.1      | 35.1    | 1990-03-01  | 5.2     |
...       | ...       | ...     | (ends here) |         |
```

- No common date spine — each series has only its actual observation dates
- Shorter series padded with empty strings at the bottom for Sheets/CSV
- Market data: daily from 1990. Macro data: native frequency (monthly, quarterly, annual)
- yfinance: bulk download + per-ticker dropna() to trim leading NaNs

### Cell budget (1990 start)

| Tab | Columns | Max rows | Cells |
|-----|---------|----------|-------|
| `market_data_comp_hist` | 302 x 3 = 906 | ~9,000 | ~8.15M |
| `macro_us_hist` | 25 x 2 = 50 | ~430 (monthly) | ~22K |
| `macro_intl_hist` | 56 x 2 = 112 | ~430 | ~48K |
| `macro_market_hist` | 150 (keep weekly) | ~1,300 | ~195K |
| Snapshots | small | small | ~10K |
| **Total** | | | **~8.4M** |

Headroom is limited. Future optimization: drop `_Local` for USD-base tickers (saves ~150 cols).

---

## Implementation Steps

### Step 1: Create branch + add alignment utilities to `library_utils.py`

New functions:
- **`load_ragged_series(df, col_name)`** — reads `Date_{col}` + `{col}` pair from a ragged DataFrame, drops empty rows, returns `pd.Series` with DatetimeIndex
- **`align_series(*series_list, method='ffill')`** — aligns multiple Series with different frequencies to a common index (union of all dates, forward-fill, drop leading NaNs)
- **`detect_frequency(series)`** — infers 'D', 'W', 'M', 'Q' from a DatetimeIndex
- **`freq_aware_shift(series, years=1)`** — shifts by 1 year using date offset (not hardcoded period count)

### Step 2: Convert `fetch_hist.py` to ragged output

Replace `build_market_hist_df(spine)` -> **`build_market_hist_df_ragged()`**:
- Bulk `yf.download(tickers, start="1990-01-01")`
- Per-ticker: `dropna()` to trim leading NaNs -> actual trading dates only
- Build ragged DataFrame: `Date_{TICKER}`, `{TICKER}_Local`, `{TICKER}_USD` per ticker
- Pad shorter columns with empty strings

Replace `build_macro_hist_df(spine)` -> **`build_macro_hist_df_ragged()`**:
- Fetch each FRED series via `fred_fetch_series_full()`
- Store at native frequency — no resampling, no forward-fill
- Each series: `Date_{SERIES_ID}`, `{SERIES_ID}`

Update **`push_df_to_sheets()`** and **`save_csv()`** for ragged format.
Update **metadata prefix rows**: frequency labels become native ("Daily", "Monthly", "Quarterly").

### Step 3: Convert `fetch_macro_international.py` to native frequency

Modify `build_history()`:
- OECD monthly -> store monthly observation dates (no Friday spine resampling)
- World Bank annual -> store annual dates
- IMF annual -> store annual dates
- Each country-indicator: `Date_{COUNTRY}_{INDICATOR}`, `{COUNTRY}_{INDICATOR}`
- Update `push_hist_to_sheets()` for ragged format

### Step 4: Update `compute_macro_market.py` to consume ragged data

This is the largest step. Key changes:

**Loaders** — replace `load_comp_hist()`, `load_macro_us_hist()`, `load_macro_intl_hist()`:
- Parse ragged CSV format using `load_ragged_series()` from library_utils
- Return dict of `{ticker: pd.Series}` instead of a single aligned DataFrame

**Helper functions:**
- `_yoy()`: replace `shift(52)` with `freq_aware_shift(series, years=1)`
- `_rolling_zscore()`: replace hardcoded `window=260` with frequency-appropriate window (e.g., ~1300 for daily, ~60 for monthly, 260 for weekly)
- `_log_ratio()`, `_arith_diff()`, `_sum_log_ratio()`: use `align_series()` before computing

**Indicator calculators** (`_calc_US_G1` through `_calc_REG_CLI5`):
- Each function extracts needed series from the dict, aligns them via `align_series()`, then computes
- Pattern: `s1 = series_dict['TICKER1']; s2 = series_dict['TICKER2']; aligned = align_series(s1, s2); result = _log_ratio(aligned['TICKER1'], aligned['TICKER2'])`

**Output**: `macro_market_hist` stays weekly — resample final indicators to W-FRI for output

### Step 5: Validate

- Run both branches end-to-end via `python fetch_data.py`
- Compare `macro_market_hist` indicator values between branches for overlapping Friday dates
- Verify all 50 indicators produce equivalent results (within floating-point tolerance)
- Confirm Sheets tab sizes are within 10M cell budget
- Spot-check ragged columns: per-ticker dates should match yfinance/FRED source data

---

## Key Files

| File | Change |
|------|--------|
| `fetch_hist.py` | Rewrite build functions to ragged |
| `library_utils.py` | Add alignment utilities |
| `compute_macro_market.py` | Update loaders + all 50 calculators |
| `fetch_macro_international.py` | Remove Friday spine, native freq |
| `fetch_data.py` | No change (snapshots unchanged) |
| `fetch_macro_us_fred.py` | No change (snapshot only) |

## Risks

1. **Sheets cell budget tight (8.4M/10M)**: If more tickers added, drop `_Local` for USD-base or split tabs
2. **50 indicator functions to update**: Test each individually against weekly branch output
3. **Z-score window equivalence**: 260 weekly != 1300 daily (trading vs calendar days) — verify regime classifications match
4. **Cherry-pick conflicts**: Hist/compute changes won't merge cleanly between branches — manual adaptation needed
