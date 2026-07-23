import asyncio
import os
import sys
import math
from binance import AsyncClient
from binance.exceptions import BinanceAPIException
from dotenv import load_dotenv

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
load_dotenv()

async def main():
    api_key = os.getenv("BINANCE_API_KEY")
    api_secret = os.getenv("BINANCE_SECRET_KEY")
    testnet = os.getenv("BINANCE_TESTNET", "true").lower() == "true"
    
    print(f"🔗 Menghubungkan ke Binance (Testnet: {testnet})...")
    client = await AsyncClient.create(api_key, api_secret, testnet=testnet)
    
    try:
        # 1. Cek Saldo & Harga Terkini
        acc = await client.futures_account()
        balance = float(acc['totalWalletBalance'])
        
        ticker = await client.futures_ticker(symbol="BTCUSDT")
        current_price = float(ticker['lastPrice'])
        
        print(f"💰 Saldo Aktual: {balance:.2f} USDT")
        print(f"📈 Harga Market: {current_price:.2f} USDT")
        
        # 2. Parameter Order (MARKET LONG)
        symbol = "BTCUSDT"
        sl_price = 60730.0
        risk_pct = 0.05  # 5% Risk
        
        risk_amount = balance * risk_pct
        risk_distance = current_price - sl_price
        
        if risk_distance <= 0:
            print("❌ ERROR: SL 60.730 lebih tinggi dari harga market saat ini. Tidak valid untuk posisi LONG.")
            return

        # Kalkulasi Qty
        qty = risk_amount / risk_distance
        qty = math.floor(qty * 1000) / 1000  # Pembulatan 3 desimal
        
        # Penyesuaian Binance Minimum Lot
        if qty < 0.001:
            qty = 0.001
            print("⚠️ Peringatan: Ukuran disesuaikan ke minimum lot bursa (0.001 BTC).")
        
        position_value = qty * current_price
        print(f"📊 Kalkulasi Posisi:")
        print(f"   - Risiko Target: ${risk_amount:.2f} (5%)")
        print(f"   - Ukuran (BTC): {qty}")
        print(f"   - Nilai Posisi: ${position_value:.2f}")
        
        print("\n🚀 MENYETEL LEVERAGE DAN MENGEKSEKUSI ORDER KE BINANCE...")
        
        print("   [0/3] Menyesuaikan Leverage ke 20x...")
        await client.futures_change_leverage(symbol=symbol, leverage=20)
        
        # A. Order Utama (MARKET BUY)
        print(f"   [1/3] Membuka posisi LONG dengan MARKET ORDER...")
        main_order = await client.futures_create_order(
            symbol=symbol,
            side='BUY',
            type='MARKET',
            quantity=qty
        )
        print("   ✅ Sukses! Posisi terbeli.")
        
        # B. Stop Loss (SELL STOP)
        print(f"   [2/3] Memasang STOP LOSS di {sl_price}...")
        await client.futures_create_order(
            symbol=symbol,
            side='SELL',
            type='STOP_MARKET',
            stopPrice=sl_price,
            quantity=qty,
            reduceOnly='true'
        )
        print("   ✅ Sukses!")
        
        print("\n🎉 EKSEKUSI MARKET BUY & STOP LOSS BERHASIL!")
        
    except BinanceAPIException as e:
        print(f"❌ Binance API Error: {e}")
    except Exception as e:
        print(f"❌ Error sistem: {e}")
    finally:
        await client.close_connection()

if __name__ == "__main__":
    asyncio.run(main())
