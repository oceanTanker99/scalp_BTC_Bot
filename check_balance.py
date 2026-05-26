import asyncio
import sys
import logging

logging.basicConfig(level=logging.INFO)

if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from src.live_trader import LiveTrader

async def main():
    trader = LiveTrader()
    print("Connecting to Binance...")
    await trader.initialize()
    print(f"Your Balance is: {trader.start_balance} USDT")

if __name__ == '__main__':
    asyncio.run(main())
