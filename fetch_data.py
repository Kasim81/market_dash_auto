import pandas as pd
import yfinance as yf
import numpy as np
from datetime import datetime, timedelta, timezone
import os

# Asset configuration
INDEX_TICKERS = [
    ('^GSPC', 'S&P 500 (Large Cap)', 'North America', 'Equity Index'),
    ('^RUT', 'Russell 2000 (Small Cap)', 'North America', 'Equity Small Cap Index'),
    ('^FTSE', 'FTSE 100 (Large Cap)', 'UK', 'Equity Index'),
    ('^FTMC', 'FTSE 250 (Mid Cap)', 'UK', 'Equity Mid Cap Index'),
    ('^GDAXI', 'DAX 40 (Large Cap Germany)', 'Europe', 'Equity Index'),
    ('^N225', 'Nikkei 225 (Large Cap Japan)', 'Asia', 'Equity Index'),
]

BOND_TICKERS = [
    ('^FVX', 'US 5Y Treasury Yield', 'North America', 'Fixed Income Sovereign'),
    ('^TNX', 'US 10Y Treasury Yield', 'North America', 'Fixed Income Sovereign'),
]

COMMODITY_TICKERS = [
    ('GC=F', 'Gold', 'Global', 'Commodity Metal'),
    ('SI=F', 'Silver', 'Global', 'Commodity Metal'),
    ('CL=F', 'WTI Crude Oil', 'Global', 'Commodity Energy'),
    ('BZ=F', 'Brent Crude', 'Global', 'Commodity Energy'),
]

CRYPTO_TICKERS = [
    ('BTC-USD', 'Bitcoin', 'Global', 'Crypto'),
    ('ETH-USD', 'Ethereum', 'Global', 'Crypto'),
]

ALL_TICKERS = INDEX_TICKERS + BOND_TICKERS + COMMODITY_TICKERS + CRYPTO_TICKERS
BOND_TICKER_SYMBOLS = {t[0] for t in BOND_TICKERS}

def fetch_asset_history(symbol, periods):
    end = datetime.now(timezone.utc)
    
    try:
        ticker = yf.Ticker(symbol)
        hist = ticker.history(period="max")
        
        if hist is None or hist.empty:
            return None, {k: np.nan for k in periods.keys()}, None
        
        hist = hist[~hist.index.duplicated(keep='first')]
        last_price = hist['Close'].iloc[-1]
        end_date = hist.index[-1].date()
        
        def perf_at(period_days):
            if period_days == 0:
                prev = hist['Close'].iloc[-2] if len(hist) > 1 else None
            else:
                period_start_date = end - timedelta(days=period_days)
                prev_idx = hist.index.searchsorted(period_start_date, side='left')
                if prev_idx >= len(hist):
                    return np.nan
                prev = hist['Close'].iloc[prev_idx]
            
            if prev is None or last_price is None:
                return np.nan
            
            if symbol in BOND_TICKER_SYMBOLS:
                return last_price - prev
            else:
                if prev > 0:
                    return 100 * (last_price - prev) / prev
                else:
                    return np.nan
        
        perf_dict = {}
        for key, ndays in periods.items():
            try:
                perf_dict[key] = perf_at(ndays) if last_price is not None else np.nan
            except Exception:
                perf_dict[key] = np.nan
        
        return last_price, perf_dict, end_date
    
    except Exception as e:
        print(f"{symbol}: {str(e)}")
        return None, {k: np.nan for k in periods.keys()}, None

def collect_dashboard_data():
    periods = {
        'Perf 1D': 1,
        'Perf 1W': 7,
        'Perf 1M': 30,
        'Perf 3M': 90,
        'Perf 6M': 182,
        'Perf 1Y': 365,
        'Perf 2Y': 365*2,
        'Perf 3Y': 365*3
    }
    
    rows = []
    
    for asset in ALL_TICKERS:
        symbol, name, region, asset_class = asset
        
        last_price, perf, end_date = fetch_asset_history(symbol, periods)
        
        row = {
            'Symbol': symbol,
            'Name': name,
            'Region': region,
            'Asset Class': asset_class,
            'End Date': end_date,
            'Current Price': np.nan if last_price is None else last_price,
            **{k: (perf.get(k, np.nan)) for k in periods.keys()}
        }
        rows.append(row)
    
    df = pd.DataFrame(rows)
    return df

if __name__ == "__main__":
    print("Fetching market data...")
    df = collect_dashboard_data()
    
    # Create data directory if it doesn't exist
    os.makedirs('data', exist_ok=True)
    
    # Save to CSV
    output_file = 'data/market_data.csv'
    df.to_csv(output_file, index=False)
    print(f"Data saved to {output_file}")
    print(f"Total assets: {len(df)}")
    print(f"Timestamp: {datetime.now()}")

