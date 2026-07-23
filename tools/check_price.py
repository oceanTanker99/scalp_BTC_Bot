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
    
    client = await AsyncClient.create(api_key, api_secret, testnet=testnet)
    try:
        ticker = await client.futures_ticker(symbol="BTCUSDT")
        acc = await client.futures_account()
        balance = float(acc['totalWalletBalance'])
        print(f"CURRENT_PRICE: {ticker['lastPrice']}")
        print(f"BALANCE: {balance}")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        await client.close_connection()

if __name__ == "__main__":
    asyncio.run(main())
