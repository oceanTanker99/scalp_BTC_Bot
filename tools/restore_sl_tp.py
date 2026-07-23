import asyncio
import os
import sys
from binance import AsyncClient
from binance.exceptions import BinanceAPIException
from dotenv import load_dotenv

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
load_dotenv()

import time

async def main():
    api_key = os.getenv("BINANCE_API_KEY")
    api_secret = os.getenv("BINANCE_SECRET_KEY")
    testnet = os.getenv("BINANCE_TESTNET", "true").lower() == "true"
    
    print("Menghubungkan ke Binance untuk memulihkan SL/TP...")
    client = await AsyncClient.create(api_key, api_secret, testnet=testnet)
    
    try:
        # Sync time
        res = await client.futures_time()
        client.timestamp_offset = res['serverTime'] - int(time.time() * 1000)

        symbol = "BTCUSDT"
        
        # Cari ukuran posisi terbuka saat ini
        positions = await client.futures_position_information(symbol=symbol)
        active_pos = next((p for p in positions if float(p.get('positionAmt', 0)) != 0), None)
        
        if not active_pos:
            print("❌ ERROR: Tidak ada posisi aktif.")
            return
            
        qty = abs(float(active_pos['positionAmt']))
        direction = "LONG" if float(active_pos['positionAmt']) > 0 else "SHORT"
        
        if direction != "LONG":
            print("❌ Posisi bukan LONG, script ini khusus untuk mengembalikan SL LONG.")
            return

        print(f"📊 Ditemukan posisi {direction} sebesar {qty} BTC.")
        
        # Hapus sisa order gantung jika ada
        await client.futures_cancel_all_open_orders(symbol=symbol)
        
        # Pasang ulang SL di 60730
        sl_price = 60730.0
        print(f"🛡️ Memulihkan STOP LOSS di {sl_price}...")
        await client.futures_create_order(
            symbol=symbol,
            side='SELL',
            type='STOP_MARKET',
            stopPrice=sl_price,
            quantity=qty,
            reduceOnly='true'
        )
        print("✅ SL berhasil dipasang!")
        
        # Pasang ulang TP di 69500
        tp_price = 69500.0
        print(f"🎯 Memulihkan TAKE PROFIT di {tp_price}...")
        await client.futures_create_order(
            symbol=symbol,
            side='SELL',
            type='TAKE_PROFIT_MARKET',
            stopPrice=tp_price,
            quantity=qty,
            reduceOnly='true'
        )
        print("✅ TP berhasil dipasang!")
        
    except BinanceAPIException as e:
        print(f"❌ Binance API Error: {e}")
    except Exception as e:
        print(f"❌ Error sistem: {e}")
    finally:
        await client.close_connection()

if __name__ == "__main__":
    asyncio.run(main())
