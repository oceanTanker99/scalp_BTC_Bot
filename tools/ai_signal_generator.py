import asyncio
import os
import sys
import pandas as pd
from binance import AsyncClient
from openai import AsyncOpenAI
from dotenv import load_dotenv

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
load_dotenv()

async def fetch_market_data(client):
    symbol = "BTCUSDT"
    print("Mendapatkan data pasar terkini dari Binance...")
    
    # Get 24h ticker
    ticker = await client.futures_ticker(symbol=symbol)
    
    # Get 15m klines (last 20)
    klines_15m = await client.futures_klines(symbol=symbol, interval='15m', limit=20)
    df_15m = pd.DataFrame(klines_15m, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume', 'close_time', 'quote_av', 'trades', 'tb_base_av', 'tb_quote_av', 'ignore'])
    df_15m = df_15m[['open', 'high', 'low', 'close', 'volume']].astype(float)
    
    # Get 1h klines (last 20)
    klines_1h = await client.futures_klines(symbol=symbol, interval='1h', limit=20)
    df_1h = pd.DataFrame(klines_1h, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume', 'close_time', 'quote_av', 'trades', 'tb_base_av', 'tb_quote_av', 'ignore'])
    df_1h = df_1h[['open', 'high', 'low', 'close', 'volume']].astype(float)

    return ticker, df_15m, df_1h

async def main():
    api_key = os.getenv("BINANCE_API_KEY")
    api_secret = os.getenv("BINANCE_SECRET_KEY")
    ds_api_key = os.getenv("DEEPSEEK_API_KEY")
    testnet = os.getenv("BINANCE_TESTNET", "true").lower() == "true"
    
    binance_client = await AsyncClient.create(api_key, api_secret, testnet=testnet)
    ds_client = AsyncOpenAI(api_key=ds_api_key, base_url="https://api.deepseek.com/v1")
    
    try:
        ticker, df_15m, df_1h = await fetch_market_data(binance_client)
        
        current_price = float(ticker['lastPrice'])
        high_24 = float(ticker['highPrice'])
        low_24 = float(ticker['lowPrice'])
        vol_24 = float(ticker['volume'])
        
        market_context = f"""
Simbol: BTCUSDT
Harga Saat Ini: {current_price}
24H High: {high_24}
24H Low: {low_24}
24H Volume (BTC): {vol_24}

Data Harga 15-Menit Terakhir (20 Candle terakhir):
{df_15m.tail(5).to_string(index=False)}

Data Harga 1-Jam Terakhir (5 Candle terakhir):
{df_1h.tail(5).to_string(index=False)}
"""
        prompt = f"""
Anda adalah AI Quant Trader tingkat institusional.
Pengguna Anda (seorang trader) saat ini melihat potensi Sell Order (SHORT) pada BTCUSDT berdasarkan insting dan pengamatannya.
Tugas Anda adalah membedah dan memvalidasi tesis SHORT ini secara objektif menggunakan data pasar terbaru berikut:

{market_context}

Tugas Anda:
1. Analisis tren jangka pendek (15m) dan makro (1h) menggunakan data harga OHLCV di atas. Cari area Resistance, Supply Zone, atau Fair Value Gap (FVG) yang ideal untuk menempatkan jaring Limit Sell Order.
2. Validasi Tesis: Apakah secara statistik menguntungkan untuk melakukan SHORT sekarang? (Jika kondisi malah mendukung LONG, peringatkan pengguna!).
3. Jika kondisi mendukung SHORT, berikan rekomendasi angka eksak untuk:
   - Titik Entry (Limit Order)
   - Titik Stop Loss (SL)
   - Titik Take Profit (TP)
4. Hitung Risk:Reward Ratio (RRR) dari setup ini. (RRR minimal 1:2).
5. Berikan rasionalisasi/alasan teknikal (Trading Thesis) yang solid dan profesional.

Jangan memberikan instruksi kode, langsung berikan Laporan Analisis Market dan Sinyal Trading.
"""

        print("Meminta otak DeepSeek-V4-Pro meracik setup...")
        response = await ds_client.chat.completions.create(
            model="deepseek-reasoner",
            messages=[
                {"role": "system", "content": "Anda adalah Quant Trader Ahli."},
                {"role": "user", "content": prompt}
            ]
        )
        print("\n=== REKOMENDASI DEEPSEEK ===\n")
        print(response.choices[0].message.content)
        
    except Exception as e:
        print(f"Error: {e}")
    finally:
        await binance_client.close_connection()

if __name__ == "__main__":
    asyncio.run(main())
