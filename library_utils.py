"""
library_utils.py
================
Shared constants and helpers for fetch_data.py and fetch_hist.py.

Contains:
  - Sort order dicts (asset class, region, subclass, sector, etc.)
  - lib_sort_key() — sort key function for index_library.csv rows
  - COMP_FX_TICKERS — single authoritative currency → yfinance ticker map
  - COMP_FCY_PER_USD — set of indirect-quote currencies (1 USD = X FCY)

Both fetch_data.py and fetch_hist.py import from here.
Do NOT duplicate these definitions in those files.
"""

# ---------------------------------------------------------------------------
# ASSET CLASS GROUP ORDER
# ---------------------------------------------------------------------------

ASSET_CLASS_GROUP = {
    "Equity":       1,
    "Fixed Income": 2,
    "Spread":       3,   # OAS / credit spread series (bps)
    "Rates":        3,   # yield series (bps) — same visual group as Spread
    "FX":           4,
    "Commodity":    5,
    "Crypto":       6,
    "Volatility":   7,
}

# ---------------------------------------------------------------------------
# REGION ORDER
# ---------------------------------------------------------------------------

REGION_ORDER = {
    "Global":               1,
    "Global ex-US/Canada":  1,
    "North America":        2,
    "UK":                   3,   # UK sits between NA and EU
    "Europe":               4,
    "Japan":                5,   # Japan sits between EU and EM
    "Emerging Markets":     6,
    "Asia Pacific":         7,
    "Asia ex Japan":        7,
    "Middle East & Africa": 8,
    "Latin America":        9,
}

# ---------------------------------------------------------------------------
# SUBCLASS ORDER MAPS
# ---------------------------------------------------------------------------

EQUITY_SUBCLASS_ORDER = {
    "Equity Broad":              1,
    "Equity Large Cap":          2,
    "Equity Large Cap (Value)":  2,
    "Equity Large Cap (Growth)": 2,
    "Equity Mid Cap":            3,
    "Equity Mid Cap (Growth)":   3,
    "Equity Mid Cap (Value)":    3,
    "Equity Small Cap":          4,
    "Equity Small Cap (Growth)": 4,
    "Equity Small Cap (Value)":  4,
    "Equity Sector":             5,
    "Equity Industry Group":     6,
    "Factor":                    7,
    "Equity Factor":             7,
}

SECTOR_ORDER = {
    "Blend": 0, "Value": 1, "Growth": 2,
    "Energy": 10, "Materials": 11, "Industrials": 12,
    "Consumer Discretionary": 13, "Consumer Staples": 14,
    "Health Care": 15, "Financials": 16,
    "Information Technology": 17, "Communication Services": 18,
    "Utilities": 19, "Real Estate": 20,
    "Mega-Cap Tech / Growth": 30, "Equal Weight": 31,
    "Momentum": 32, "Dividend Growth": 33, "Quality": 34,
    "Dividend/Quality": 35, "Low Volatility": 36,
    "Dividend/Income": 37, "Broad Market": 38,
}

FI_SUBCLASS_ORDER = {
    "Bond Aggregate":              1,
    "Global Aggregate":            1,
    "Govt Bond":                   2,
    "Government":                  2,
    "Government Short":            2,
    "Government Inflation-Linked": 3,
    "Inflation-Linked":            3,
    "EM Bond":                     4,
    "Emerging Market Debt":        4,
    "Corp IG":                     5,
    "Corp HY":                     6,
    "Credit Spread":               7,
}

MATURITY_ORDER = {
    "Broad": 1, "Short (1-3yr)": 2, "Long (10yr+)": 3,
}

COMMODITY_GROUP_ORDER = {
    "Energy": 1, "Precious Metals": 2, "Industrial Metals": 3,
    "Agriculture": 4, "Livestock": 5, "Broad": 6,
    "Commodity": 7,
}

VOL_SUBCLASS_ORDER = {
    "Equity Volatility": 1, "Tail Risk": 2,
    "Fixed Income Volatility": 3, "Commodity Volatility": 4,
}

RATES_SUBCLASS_ORDER = {
    "Government Yield": 1, "Breakeven Inflation": 2,
    "Credit Spread": 3, "Policy Rate": 4, "Yield Curve": 5,
}

SPREAD_SUBCLASS_ORDER = {
    "Corp IG": 1, "Credit Spread": 2, "Corp HY": 3,
}

# ---------------------------------------------------------------------------
# SORT KEY FUNCTION
# ---------------------------------------------------------------------------

def lib_sort_key(row) -> tuple:
    """Sort key for a raw index_library.csv row (works with both dict and Series)."""
    ac      = str(row.get("asset_class", ""))
    asc     = str(row.get("asset_subclass", ""))
    region  = str(row.get("region", ""))
    sector  = str(row.get("sector_style", ""))
    mat     = str(row.get("maturity_focus", ""))
    cg      = str(row.get("commodity_group", ""))
    name    = str(row.get("name", ""))

    g = ASSET_CLASS_GROUP.get(ac, 99)
    r = REGION_ORDER.get(region, 50)

    if ac == "Equity":
        s   = EQUITY_SUBCLASS_ORDER.get(asc, 50)
        sec = SECTOR_ORDER.get(sector, 50)
        return (g, r, s, sec, name)

    if ac == "Fixed Income":
        s = FI_SUBCLASS_ORDER.get(asc, 50)
        m = MATURITY_ORDER.get(mat, 50)
        return (g, r, s, m, name)

    if ac in ("Spread", "Rates"):
        s = SPREAD_SUBCLASS_ORDER.get(asc, RATES_SUBCLASS_ORDER.get(asc, 50))
        return (g, r, s, name)

    if ac == "FX":
        s = 1 if "Index" in asc else 2
        return (g, 0, s, name)

    if ac == "Commodity":
        cgn = COMMODITY_GROUP_ORDER.get(cg, 50)
        return (g, 0, cgn, name)

    if ac == "Crypto":
        return (g, 0, 0, name)

    if ac == "Volatility":
        s = VOL_SUBCLASS_ORDER.get(asc, 50)
        return (g, 0, s, name)

    return (g, r, 0, name)


# ---------------------------------------------------------------------------
# FX TICKER MAP  (single authoritative definition)
#
# Convention:
#   Direct quotes  (1 FCY = X USD) → NOT in COMP_FCY_PER_USD → multiply to get USD
#   Indirect quotes (1 USD = X FCY) → IN COMP_FCY_PER_USD → divide to get USD
#
# USX (US cents, e.g. agricultural futures) is handled separately in the
# fetch functions: divide by 100 then treat as USD — no FX entry needed.
# ---------------------------------------------------------------------------

COMP_FX_TICKERS = {
    # Direct quotes
    "GBP": "GBPUSD=X",
    "EUR": "EURUSD=X",
    "AUD": "AUDUSD=X",
    # Indirect quotes
    "JPY": "USDJPY=X",
    "CNY": "CNY=X",
    "INR": "INR=X",
    "KRW": "KRW=X",
    "TWD": "TWD=X",
    "CAD": "USDCAD=X",
    "BRL": "USDBRL=X",
    "HKD": "USDHKD=X",
    "MXN": "USDMXN=X",
    "IDR": "USDIDR=X",
    "RUB": "USDRUB=X",
    "SAR": "USDSAR=X",
    "ZAR": "USDZAR=X",
    "TRY": "USDTRY=X",
    "ARS": "USDARS=X",
}

# Indirect-quote currencies: 1 USD = X FCY → divide price by FX rate to get USD
COMP_FCY_PER_USD = {
    "JPY", "CNY", "INR", "KRW", "TWD",
    "CAD", "BRL", "HKD", "MXN", "IDR",
    "RUB", "SAR", "ZAR", "TRY", "ARS",
}
