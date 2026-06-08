import asyncio
from src.live_trader import LiveTrader

async def main():
    trader = LiveTrader()
    await trader.initialize()
    msg = await trader.get_active_position_details()
    print(msg)
    await trader.client.close_connection()

if __name__ == '__main__':
    asyncio.run(main())
