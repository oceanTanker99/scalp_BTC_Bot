import asyncio
import os
import sys
import logging
from binance import AsyncClient
from dotenv import load_dotenv

logging.basicConfig(level=logging.INFO)
load_dotenv()

API_KEY = os.getenv("BINANCE_API_KEY")
API_SECRET = os.getenv("BINANCE_SECRET_KEY")

async def main():
    client = await AsyncClient.create(API_KEY, API_SECRET, testnet=False)
    
    try:
        # Set leverage to 10x
        print("Setting leverage to 10x...")
        await client.futures_change_leverage(symbol='BTCUSDT', leverage=10)
        
        # Set margin type to ISOLATED
        try:
            await client.futures_change_margin_type(symbol='BTCUSDT', marginType='ISOLATED')
            print("Margin type set to ISOLATED.")
        except Exception:
            pass
            
        # Place Market Buy order for 0.001 BTC
        print("Placing MARKET BUY order for 0.001 BTCUSDT...")
        order = await client.futures_create_order(
            symbol='BTCUSDT',
            side='BUY',
            type='MARKET',
            quantity=0.001
        )
        print("\n[SUCCESS] Order executed!")
        print(f"Order ID: {order.get('orderId')}")
        print("SILAKAN BUKA APLIKASI BINANCE ANDA SEKARANG UNTUK MEMANTAU DAN MENUTUP POSISI SECARA MANUAL.")
        
    except Exception as e:
        print(f"\n[ERROR] {e}")
    finally:
        await client.close_connection()

if __name__ == '__main__':
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())
