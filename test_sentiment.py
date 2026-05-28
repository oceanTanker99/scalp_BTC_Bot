import asyncio
from binance import AsyncClient

async def test_api():
    client = await AsyncClient.create()
    try:
        pi = await client.futures_mark_price(symbol="BTCUSDT")
        print(f"Premium Index: {pi}")

        oi = await client.futures_open_interest(symbol="BTCUSDT")
        print(f"Open Interest: {oi}")

        ls = await client.futures_global_long_short_account_ratio(symbol="BTCUSDT", period="5m")
        print(f"Global LS Ratio: {ls[0] if ls else 'None'}")
        
    except Exception as e:
        print(f"Error: {e}")
    finally:
        await client.close_connection()

asyncio.run(test_api())
