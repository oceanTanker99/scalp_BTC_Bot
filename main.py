import asyncio
import logging
import sys

from src.market_stream import MarketStream
from src.strategy import StrategyEngine
from src.live_trader import LiveTrader

if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
log = logging.getLogger(__name__)

class ScalpBot:
    def __init__(self):
        self.stream = MarketStream()
        self.strategy = StrategyEngine()
        self.trader = LiveTrader()
        self.in_position = False

    async def start(self):
        log.info("Starting Scalp BTC Bot...")
        await self.trader.initialize()
        
        self.stream.register_callback(self.on_candle_close)
        await self.stream.start()
        
        # Keep alive
        while True:
            await asyncio.sleep(3600)

    async def on_candle_close(self, df_1m, df_5m, ofi):
        # We only look for entry if not currently in a position
        # For simplicity in this base version, we assume OCO closes the position.
        # Checking open positions is recommended for production.
        
        # In a real bot, we'd check self.client.futures_position_information()
        
        signal, price = self.strategy.analyze(df_1m, df_5m, ofi)
        
        if signal != 'NEUTRAL':
            log.info(f"Signal Generated: {signal} at {price}")
            await self.trader.execute_trade(signal, price)

if __name__ == "__main__":
    bot = ScalpBot()
    try:
        asyncio.run(bot.start())
    except KeyboardInterrupt:
        log.info("Bot stopped by user.")
    except Exception as e:
        log.error(f"Fatal error: {e}")
