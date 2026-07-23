import asyncio
import os
import sys
from binance import AsyncClient
from binance.exceptions import BinanceAPIException
from dotenv import load_dotenv

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
load_dotenv()

async def main():
    api_key = os.getenv("BINANCE_API_KEY")
    api_secret = os.getenv("BINANCE_SECRET_KEY")
    testnet = os.getenv("BINANCE_TESTNET", "true").lower() == "true"
    
    print("Menghubungkan ke Binance untuk cek posisi...")
    client = await AsyncClient.create(api_key, api_secret, testnet=testnet)
    
    try:
        symbol = "BTCUSDT"
        
        # 1. Cek Posisi Terbuka
        positions = await client.futures_position_information(symbol=symbol)
        active_pos = next((p for p in positions if float(p.get('positionAmt', 0)) != 0), None)
        
        if not active_pos:
            print("Tidak ada posisi aktif saat ini.")
        else:
            qty = float(active_pos['positionAmt'])
            direction = "LONG" if qty > 0 else "SHORT"
            entry_price = float(active_pos['entryPrice'])
            mark_price = float(active_pos['markPrice'])
            pnl = float(active_pos['unRealizedProfit'])
            
            print(f"📊 POSISI AKTIF: {direction}")
            print(f"   Ukuran : {abs(qty)} BTC")
            print(f"   Entry  : {entry_price:.2f}")
            print(f"   Market : {mark_price:.2f}")
            print(f"   PnL    : ${pnl:.2f}")
        
        print("\n--- ORDER GANTUNG (SL/TP) ---")
        orders = await client.futures_get_open_orders(symbol=symbol)
        if not orders:
            print("Tidak ada order terbuka (SL/TP kosong!).")
        else:
            for o in orders:
                tipe = o['type']
                side = o['side']
                harga = float(o['price']) if float(o['price']) > 0 else float(o['stopPrice'])
                print(f"🔹 {tipe} ({side}) di harga {harga:.2f}")

    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        await client.close_connection()

if __name__ == "__main__":
    asyncio.run(main())
