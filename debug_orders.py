import os
import asyncio
from dotenv import load_dotenv
from binance import AsyncClient
import json

async def main():
    load_dotenv()
    binance_api_key = os.getenv("BINANCE_API_KEY")
    binance_secret_key = os.getenv("BINANCE_SECRET_KEY")
    testnet = os.getenv("BINANCE_TESTNET", "true").lower() == "true"
    
    client = await AsyncClient.create(api_key=binance_api_key, api_secret=binance_secret_key, testnet=testnet)
    
    print("[INFO] Fetching raw open orders...")
    open_orders = await client.futures_get_open_orders(symbol="BTCUSDT")
    print(json.dumps(open_orders, indent=2))
    
    await client.close_connection()

if __name__ == "__main__":
    asyncio.run(main())
