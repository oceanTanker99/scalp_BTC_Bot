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
    
    print(f"🔗 Menghubungkan ke Binance (Testnet: {testnet})...")
    client = await AsyncClient.create(api_key, api_secret, testnet=testnet)
    
    try:
        symbol = "BTCUSDT"
        tp_price = 69500.0
        
        # Cari ukuran posisi terbuka saat ini
        positions = await client.futures_position_information(symbol=symbol)
        active_pos = next((p for p in positions if float(p.get('positionAmt', 0)) != 0), None)
        
        if not active_pos:
            print("❌ ERROR: Tidak ada posisi aktif untuk dipasangi TP.")
            return
            
        qty = abs(float(active_pos['positionAmt']))
        direction = "LONG" if float(active_pos['positionAmt']) > 0 else "SHORT"
        
        print(f"📊 Menemukan posisi aktif {direction} dengan ukuran {qty} BTC.")
        
        # Tentukan side untuk close position
        close_side = 'SELL' if direction == 'LONG' else 'BUY'
        
        print(f"🎯 Memasang TAKE PROFIT di {tp_price}...")
        await client.futures_create_order(
            symbol=symbol,
            side=close_side,
            type='TAKE_PROFIT_MARKET',
            stopPrice=tp_price,
            quantity=qty,
            reduceOnly='true'
        )
        print("✅ Sukses! Take Profit berhasil dipasang.")
        
    except BinanceAPIException as e:
        print(f"❌ Binance API Error: {e}")
    except Exception as e:
        print(f"❌ Error sistem: {e}")
    finally:
        await client.close_connection()

if __name__ == "__main__":
    asyncio.run(main())
