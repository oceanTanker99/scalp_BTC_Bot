import asyncio
import os
import sys
from binance.client import AsyncClient
from dotenv import load_dotenv

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
load_dotenv()

async def main():
    api_key = os.getenv("BINANCE_API_KEY")
    api_secret = os.getenv("BINANCE_SECRET_KEY")
    testnet = os.getenv("BINANCE_TESTNET", "true").lower() == "true"
    
    print(f"Connecting to Binance (Testnet: {testnet})...")
    client = await AsyncClient.create(api_key, api_secret, testnet=testnet)
    
    try:
        acc = await client.futures_account()
        balance = float(acc['totalWalletBalance'])
        print(f"Actual Balance: {balance} USDT")
    except Exception as e:
        print(f"Error fetching balance: {e}")
    finally:
        await client.close_connection()

if __name__ == "__main__":
    asyncio.run(main())
