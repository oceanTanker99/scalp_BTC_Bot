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
        
        print("\n🧹 [FASE 1] MEMBERSIHKAN POSISI LAMA...")
        # 1. Batalkan semua order lama (SL/TP dari posisi LONG)
        await client.futures_cancel_all_open_orders(symbol=symbol)
        print("   ✅ Semua order gantung (SL/TP) lama dibatalkan.")
        
        # 2. Tutup posisi LONG jika ada
        positions = await client.futures_position_information(symbol=symbol)
        active_pos = next((p for p in positions if float(p.get('positionAmt', 0)) != 0), None)
        
        if active_pos and float(active_pos['positionAmt']) > 0:
            qty_to_close = abs(float(active_pos['positionAmt']))
            print(f"   ⚠️ Menutup posisi LONG lama sebesar {qty_to_close} BTC pada harga Market...")
            await client.futures_create_order(
                symbol=symbol,
                side='SELL',
                type='MARKET',
                quantity=qty_to_close,
                reduceOnly='true'
            )
            print("   ✅ Posisi LONG lama berhasil ditutup (Flip ke Netral).")
        else:
            print("   ℹ️ Tidak ada posisi aktif yang perlu ditutup.")
            
        print("\n🚀 [FASE 2] MEMASANG JARING SHORT BARU...")
        
        # Cek saldo terbaru setelah penutupan
        acc = await client.futures_account()
        balance = float(acc['totalWalletBalance'])
        print(f"💰 Saldo Aktual: {balance:.2f} USDT")
        
        # Parameter SHORT Setup dari DeepSeek
        entry_price = 62975.0  # Tengah-tengah 62950-63000
        sl_price = 63150.0
        tp_price = 62500.0
        risk_pct = 0.05  # 5% Risk
        
        risk_amount = balance * risk_pct
        risk_distance = sl_price - entry_price
        
        # Kalkulasi Qty
        qty = risk_amount / risk_distance
        qty = math.floor(qty * 1000) / 1000
        
        if qty < 0.001:
            qty = 0.001
            print("   ⚠️ Peringatan: Ukuran disesuaikan ke minimum lot bursa (0.001 BTC).")
            
        print(f"   - Entry Limit : {entry_price}")
        print(f"   - Stop Loss   : {sl_price}")
        print(f"   - Take Profit : {tp_price}")
        print(f"   - Ukuran (BTC): {qty}")
        
        await client.futures_change_leverage(symbol=symbol, leverage=20)
        
        # A. Limit Sell Order
        print(f"   [1/3] Memasang LIMIT SELL di {entry_price}...")
        await client.futures_create_order(
            symbol=symbol, side='SELL', type='LIMIT', timeInForce='GTC',
            price=entry_price, quantity=qty
        )
        print("   ✅ Sukses!")
        
        # B. Stop Loss (BUY STOP)
        print(f"   [2/3] Memasang STOP LOSS (BUY) di {sl_price}...")
        await client.futures_create_order(
            symbol=symbol, side='BUY', type='STOP_MARKET', stopPrice=sl_price,
            quantity=qty, reduceOnly='true'
        )
        print("   ✅ Sukses!")
        
        # C. Take Profit (BUY TAKE PROFIT)
        print(f"   [3/3] Memasang TAKE PROFIT (BUY) di {tp_price}...")
        await client.futures_create_order(
            symbol=symbol, side='BUY', type='TAKE_PROFIT_MARKET', stopPrice=tp_price,
            quantity=qty, reduceOnly='true'
        )
        print("   ✅ Sukses!")
        
        print("\n🎉 FLIP KE SHORT SELESAI! Jaring telah terpasang dengan rapi.")
        
    except BinanceAPIException as e:
        print(f"❌ Binance API Error: {e}")
    except Exception as e:
        print(f"❌ Error sistem: {e}")
    finally:
        await client.close_connection()

if __name__ == "__main__":
    asyncio.run(main())
