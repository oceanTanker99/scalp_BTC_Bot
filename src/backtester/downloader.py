import os
import time
import pandas as pd
from binance.client import Client

def download_klines(symbol="BTCUSDT", interval="1m", days=30, output_dir="data"):
    client = Client()
    os.makedirs(output_dir, exist_ok=True)
    
    end_str = "now UTC"
    start_str = f"{days} days ago UTC"
    
    print(f"📥 Mengunduh data historis {interval} untuk {symbol} ({days} hari)...")
    
    try:
        klines = client.futures_historical_klines(symbol, interval, start_str, end_str)
        
        df = pd.DataFrame(klines, columns=[
            'timestamp', 'open', 'high', 'low', 'close', 'volume',
            'close_time', 'qav', 'num_trades', 'taker_base_vol', 'taker_quote_vol', 'ignore'
        ])
        
        # Konversi ke numerik
        for col in ['open', 'high', 'low', 'close', 'volume']:
            df[col] = pd.to_numeric(df[col], errors='coerce')
            
        file_path = os.path.join(output_dir, f"{symbol}_{interval}.csv")
        df.to_csv(file_path, index=False)
        print(f"✅ Berhasil menyimpan {len(df)} baris data ke {file_path}")
        
    except Exception as e:
        print(f"❌ Gagal mengunduh data {interval}: {e}")

if __name__ == "__main__":
    download_klines(interval="1m", days=30)
    download_klines(interval="5m", days=30)
    download_klines(interval="15m", days=30)
