import asyncio
import os
import sys
from binance import AsyncClient
from dotenv import load_dotenv

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
load_dotenv()

async def main():
    api_key = os.getenv("BINANCE_API_KEY")
    api_secret = os.getenv("BINANCE_SECRET_KEY")
    testnet = os.getenv("BINANCE_TESTNET", "true").lower() == "true"
    
    print("Menghubungkan ke Binance untuk membatalkan semua order...")
    client = await AsyncClient.create(api_key, api_secret, testnet=testnet)
    
    try:
        symbol = "BTCUSDT"
        res = await client.futures_cancel_all_open_orders(symbol=symbol)
        print(f"✅ Semua order untuk {symbol} berhasil dibatalkan!")
        print(res)
    except Exception as e:
        print(f"❌ Error saat membatalkan order: {e}")
    finally:
        await client.close_connection()

if __name__ == "__main__":
    asyncio.run(main())
