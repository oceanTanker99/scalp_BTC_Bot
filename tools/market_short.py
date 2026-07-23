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
        symbol = "BTCUSDT"
        
        # 1. Bersihkan order gantung (termasuk Limit Sell 62975 yang lama)
        print("🧹 [1/4] Membatalkan semua order gantung lama...")
        await client.futures_cancel_all_open_orders(symbol=symbol)
        
        # 2. Cek Saldo & Harga Terkini
        acc = await client.futures_account()
        balance = float(acc['totalWalletBalance'])
        
        ticker = await client.futures_ticker(symbol=symbol)
        current_price = float(ticker['lastPrice'])
        
        print(f"💰 Saldo Aktual: {balance:.2f} USDT")
        print(f"📉 Harga Market: {current_price:.2f} USDT")
        
        # 3. Parameter Order (MARKET SHORT)
        sl_price = 63200.0
        tp_price = 62000.0
        risk_pct = 0.05  # 5% Risk
        
        risk_amount = balance * risk_pct
        risk_distance = sl_price - current_price
        
        if risk_distance <= 0:
            print("❌ ERROR: SL 63.200 lebih rendah dari harga market saat ini. Tidak valid untuk posisi SHORT.")
            return

        # Kalkulasi Qty
        qty = risk_amount / risk_distance
        qty = math.floor(qty * 1000) / 1000  # Pembulatan 3 desimal
        
        if qty < 0.001:
            qty = 0.001
            print("⚠️ Peringatan: Ukuran disesuaikan ke minimum lot bursa (0.001 BTC).")
        
        print(f"📊 Kalkulasi Posisi:")
        print(f"   - Risiko Target: ${risk_amount:.2f} (5%)")
        print(f"   - Ukuran (BTC): {qty}")
        
        print("\n🚀 MENYETEL LEVERAGE DAN MENGEKSEKUSI ORDER KE BINANCE...")
        
        print("   [2/4] Menyesuaikan Leverage ke 20x...")
        await client.futures_change_leverage(symbol=symbol, leverage=20)
        
        # A. Order Utama (MARKET SELL)
        print(f"   [3/4] Membuka posisi SHORT dengan MARKET ORDER...")
        await client.futures_create_order(
            symbol=symbol,
            side='SELL',
            type='MARKET',
            quantity=qty
        )
        print("   ✅ Sukses! Posisi terbeli.")
        
        # B. Stop Loss (BUY STOP)
        print(f"   [4/4] Memasang STOP LOSS di {sl_price} dan TAKE PROFIT di {tp_price}...")
        await client.futures_create_order(
            symbol=symbol, side='BUY', type='STOP_MARKET', stopPrice=sl_price,
            quantity=qty, reduceOnly='true'
        )
        await client.futures_create_order(
            symbol=symbol, side='BUY', type='TAKE_PROFIT_MARKET', stopPrice=tp_price,
            quantity=qty, reduceOnly='true'
        )
        print("   ✅ Sukses!")
        
        print("\n🎉 EKSEKUSI MARKET SHORT & SL/TP BERHASIL!")
        
    except BinanceAPIException as e:
        print(f"❌ Binance API Error: {e}")
    except Exception as e:
        print(f"❌ Error sistem: {e}")
    finally:
        await client.close_connection()

if __name__ == "__main__":
    asyncio.run(main())
