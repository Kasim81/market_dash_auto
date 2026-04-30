#!/usr/bin/env python3
"""Stage F probe — verify yfinance candidate tickers for §1 gaps and §3.6
Market Index Expansion buckets. Outputs a CSV result that we can review
to decide which tickers to add to data/index_library.csv.

Run from CI via .github/workflows/stage_f_probe.yml — sandbox blocks yfinance.
"""
import os
import sys
import pandas as pd
import yfinance as yf
import warnings
warnings.filterwarnings("ignore")

REPO_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, REPO_ROOT)

existing_lib = pd.read_csv(os.path.join(REPO_ROOT, "data", "index_library.csv"))
# Find the ticker column robustly
ticker_col = None
for c in ["ticker", "Ticker ID", "Ticker", "ticker_id"]:
    if c in existing_lib.columns:
        ticker_col = c
        break
existing_tickers = set()
if ticker_col:
    existing_tickers = set(existing_lib[ticker_col].astype(str).str.strip().str.upper())

# Probe candidates by goal
CANDIDATES = {
    # Goal: Euro IG corp bond yield proxy for EU_Cr1 (currently n/a)
    # iShares EUR Corporate Bond UCITS family — most liquid Euro IG corp ETFs
    "Euro_IG_corp": [
        "IBCX.DE",  # iShares Core € Corp Bond UCITS ETF (XETRA)
        "IEAC.L",   # iShares Core € Corp Bond UCITS ETF (LSE EUR)
        "EUNA.DE",  # iShares Euro Corp Bond Large Cap UCITS
        "VECP.L",   # Vanguard EUR Corporate Bond UCITS
        "ZPRC.DE",  # SPDR Bloomberg Euro Aggregate Corp Bond UCITS
    ],
    # Goal: CN 10Y govt bond proxy for AS_CN_R1 (currently n/a)
    "CN_govt_bond": [
        "CGB.AX",   # VanEck China Govt Bond ETF (ASX)
        "CHNB.L",   # KraneShares Bloomberg China Bond Aggregate
        "CGOV.L",   # iShares China CNY Bond UCITS
        "CBON",     # VanEck China Bond ETF (US)
    ],
    # Goal: Europe sector ETFs (.DE EUR-denominated) — §3.6 bucket
    "EU_sector_ETFs": [
        "EXSA.DE",  # STOXX Europe 600
        "EXV1.DE",  # STOXX Europe 600 Banks
        "EXV3.DE",  # STOXX Europe 600 Telecoms
        "EXV4.DE",  # STOXX Europe 600 Financial Services
        "EXV5.DE",  # STOXX Europe 600 Personal & Household Goods
        "EXV6.DE",  # STOXX Europe 600 Real Estate
        "EXV7.DE",  # STOXX Europe 600 Tech
        "EXV8.DE",  # STOXX Europe 600 Construction & Materials
        "EXV9.DE",  # STOXX Europe 600 Insurance
        "EXH1.DE",  # STOXX Europe 600 Automobiles
        "EXH2.DE",  # STOXX Europe 600 Basic Resources
        "EXH3.DE",  # STOXX Europe 600 Chemicals
        "EXH4.DE",  # STOXX Europe 600 Health Care
        "EXH5.DE",  # STOXX Europe 600 Industrial Goods
        "EXH6.DE",  # STOXX Europe 600 Media
        "EXH7.DE",  # STOXX Europe 600 Oil & Gas
        "EXH8.DE",  # STOXX Europe 600 Retail
        "EXH9.DE",  # STOXX Europe 600 Travel & Leisure
        "EXSI.DE",  # STOXX Europe 600 Utilities
        "EXSJ.DE",  # STOXX Europe 600 Food & Beverage
    ],
    # Goal: UK style ETFs — §3.6 bucket
    "UK_style": [
        "VMID.L",   # Vanguard FTSE 250
        "ISF.L",    # iShares Core FTSE 100
        "IUKD.L",   # iShares UK Dividend
        "MIDD.L",   # iShares FTSE 250
        "VUKE.L",   # Vanguard FTSE 100
    ],
    # Goal: EM regional ETFs — §3.6 bucket
    "EM_regional": [
        "EWZ",      # iShares Brazil
        "ILF",      # iShares Latin America 40
        "EWW",      # iShares Mexico
        "INDA",     # iShares MSCI India
        "EZA",      # iShares MSCI South Africa
        "EWY",      # iShares MSCI South Korea
        "TUR",      # iShares MSCI Turkey
        "EIS",      # iShares MSCI Israel
        "ASHR",     # Xtrackers Harvest CSI 300 China A
        "MCHI",     # iShares MSCI China
        "FXI",      # iShares China Large-Cap
    ],
    # Goal: Japan additional — §3.6 bucket
    "Japan_extra": [
        "EWJ",      # iShares MSCI Japan
        "DXJ",      # WisdomTree Japan Hedged Equity
        "1306.T",   # NEXT FUNDS TOPIX ETF
        "1321.T",   # Nikkei 225 ETF
        "EWV",      # ProShares Ultra MSCI Japan
        "DBJP",     # Xtrackers MSCI Japan Hedged
    ],
    # Bonus: rates / yields ETFs not currently in our library
    "Rates_and_yields": [
        "GBR.L",    # iShares UK Gilts 0-5Y (not sure exactly — needs check)
        "VGOV.L",   # Vanguard UK Gilt UCITS
        "IGLT.L",   # iShares Core UK Gilts UCITS
        "IBGS.L",   # iShares Eur Govt Bond 1-3yr
        "IBGM.L",   # iShares Eur Govt Bond 7-10yr
    ],
}


def probe_ticker(t):
    """Probe a single yfinance ticker; return (status, last_date, last_price, n_days)."""
    try:
        tk = yf.Ticker(t)
        hist = tk.history(period="1mo", auto_adjust=False)
        if hist.empty:
            return ("no data", None, None, 0)
        return (
            "live",
            hist.index[-1].strftime("%Y-%m-%d"),
            round(float(hist["Close"].iloc[-1]), 4),
            len(hist),
        )
    except Exception as e:
        return (f"ERR:{type(e).__name__}", None, None, 0)


def main():
    print(f"Stage F probe — running {sum(len(v) for v in CANDIDATES.values())} candidates")
    print(f"index_library.csv has {len(existing_tickers)} existing instruments\n")

    results = []
    for goal, tickers in CANDIDATES.items():
        print(f"=== {goal} ===")
        for t in tickers:
            in_lib = t.upper() in existing_tickers
            status, last_date, last_price, n = probe_ticker(t)
            mark = " [in lib]" if in_lib else ""
            print(f"  {t:<10s}  {status:<10s}  last={last_date or '—':10s}  "
                  f"price={last_price if last_price else '—':<8}  bars={n}{mark}")
            results.append({
                "goal": goal,
                "ticker": t,
                "status": status,
                "last_date": last_date,
                "last_price": last_price,
                "n_bars_1mo": n,
                "in_index_library": in_lib,
            })
        print()

    df = pd.DataFrame(results)
    out_path = "/tmp/stage_f_probe_results.csv"
    df.to_csv(out_path, index=False)
    print(f"\n=== SUMMARY ===")
    by_status = df["status"].value_counts().to_dict()
    print(f"  status counts: {by_status}")
    by_goal = df.groupby("goal").apply(
        lambda g: f"{(g['status'] == 'live').sum()}/{len(g)} live"
    ).to_dict()
    print(f"  by goal: {by_goal}")
    print(f"\nWrote {out_path}")


if __name__ == "__main__":
    main()
