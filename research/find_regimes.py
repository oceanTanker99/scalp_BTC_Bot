import requests
import pandas as pd
from datetime import datetime

def find_regimes():
    print("Mencari data histori BTCUSDT 1D dari Binance...")
    url = "https://fapi.binance.com/fapi/v1/klines"
    
    # Ambil 500 hari terakhir
    params = {
        "symbol": "BTCUSDT",
        "interval": "1d",
        "limit": 500
    }
    
    res = requests.get(url, params=params)
    data = res.json()
    
    df = pd.DataFrame(data, columns=[
        'timestamp', 'open', 'high', 'low', 'close', 'volume',
        'close_time', 'quote_asset_volume', 'trades', 'taker_buy_base',
        'taker_buy_quote', 'ignore'
    ])
    
    df['date'] = pd.to_datetime(df['timestamp'], unit='ms')
    df['close'] = df['close'].astype(float)
    df['open'] = df['open'].astype(float)
    df['high'] = df['high'].astype(float)
    df['low'] = df['low'].astype(float)
    
    # Resample ke bulanan untuk mencari bulan paling bullish dan bearish
    df.set_index('date', inplace=True)
    monthly = df.resample('M').agg({
        'open': 'first',
        'high': 'max',
        'low': 'min',
        'close': 'last'
    })
    
    monthly['return_pct'] = ((monthly['close'] - monthly['open']) / monthly['open']) * 100
    
    print("\n--- 3 Bulan Paling Bullish (Aggressive Bullish) ---")
    bullish = monthly.sort_values('return_pct', ascending=False).head(3)
    for idx, row in bullish.iterrows():
        print(f"{idx.strftime('%Y-%m')}: +{row['return_pct']:.2f}% (Open: {row['open']:.0f}, Close: {row['close']:.0f})")
        
    print("\n--- 3 Bulan Paling Bearish (Bloody Bearish) ---")
    bearish = monthly.sort_values('return_pct', ascending=True).head(3)
    for idx, row in bearish.iterrows():
        print(f"{idx.strftime('%Y-%m')}: {row['return_pct']:.2f}% (Open: {row['open']:.0f}, Close: {row['close']:.0f})")
        
    # Cari juga periode 14-hari (2 minggu) paling ekstrem
    # Rolling 14-day return
    df['return_14d'] = df['close'].pct_change(periods=14) * 100
    
    max_bull_idx = df['return_14d'].idxmax()
    max_bull_val = df.loc[max_bull_idx, 'return_14d']
    max_bull_start = max_bull_idx - pd.Timedelta(days=14)
    
    max_bear_idx = df['return_14d'].idxmin()
    max_bear_val = df.loc[max_bear_idx, 'return_14d']
    max_bear_start = max_bear_idx - pd.Timedelta(days=14)

    print("\n--- Periode 2-Minggu Paling Ekstrem ---")
    print(f"Bullish Terganas : {max_bull_start.strftime('%Y-%m-%d')} s/d {max_bull_idx.strftime('%Y-%m-%d')} (+{max_bull_val:.2f}%)")
    print(f"Bearish Berdarah : {max_bear_start.strftime('%Y-%m-%d')} s/d {max_bear_idx.strftime('%Y-%m-%d')} ({max_bear_val:.2f}%)")

if __name__ == "__main__":
    find_regimes()
