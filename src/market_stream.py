import asyncio
import logging
from binance import AsyncClient, BinanceSocketManager
from config.config import SYMBOL
from src.order_flow_engine import OrderFlowEngine

log = logging.getLogger(__name__)

RECONNECT_DELAY_SECONDS = 5
EVALUATION_INTERVAL = 3 # Evaluate strategy every 3 seconds

class MarketStream:
    def __init__(self, client: AsyncClient = None):
        self.client = client
        self.bsm = None
        self.engine = OrderFlowEngine()
        self.callbacks = []
        self._running = True

    def register_callback(self, callback):
        self.callbacks.append(callback)

    async def start(self):
        if self.client is None:
            from config.config import BINANCE_API_KEY, BINANCE_SECRET_KEY, BINANCE_TESTNET
            self.client = await AsyncClient.create(
                BINANCE_API_KEY, BINANCE_SECRET_KEY, testnet=BINANCE_TESTNET
            )

        self.bsm = BinanceSocketManager(self.client)

        self._tasks = [
            asyncio.create_task(self._run_aggtrade_with_reconnect()),
            asyncio.create_task(self._run_depth_with_reconnect()),
            asyncio.create_task(self._evaluation_loop()),
        ]

    async def _run_aggtrade_with_reconnect(self):
        while self._running:
            try:
                await self._aggtrade_stream()
            except Exception as e:
                log.error(f"AggTrade stream terputus: {e}. Reconnect dalam {RECONNECT_DELAY_SECONDS} detik...")
                await asyncio.sleep(RECONNECT_DELAY_SECONDS)

    async def _run_depth_with_reconnect(self):
        while self._running:
            try:
                await self._depth_stream()
            except Exception as e:
                log.error(f"Depth stream terputus: {e}. Reconnect dalam {RECONNECT_DELAY_SECONDS} detik...")
                await asyncio.sleep(RECONNECT_DELAY_SECONDS)

    async def _aggtrade_stream(self):
        log.info("Memulai aggTrade stream (Order Flow / CVD)...")
        async with self.bsm.aggtrade_socket(symbol=SYMBOL) as stream:
            while self._running:
                msg = await stream.recv()
                self.engine.process_agg_trade(msg)

    async def _depth_stream(self):
        log.info("Memulai depth stream (L2 Imbalance)...")
        async with self.bsm.depth_socket(symbol=SYMBOL, depth="5") as stream:
            while self._running:
                msg = await stream.recv()
                self.engine.process_depth(msg)

    async def _evaluation_loop(self):
        log.info(f"Memulai loop evaluasi strategi setiap {EVALUATION_INTERVAL} detik...")
        while self._running:
            await asyncio.sleep(EVALUATION_INTERVAL)
            # Fetch 15-minute, 1-hour, and 4-hour CVD/VWAP metrics
            metrics = {
                "15m": self.engine.get_metrics(lookback_seconds=900),
                "1h": self.engine.get_metrics(lookback_seconds=3600),
                "4h": self.engine.get_metrics(lookback_seconds=14400)
            }
            if metrics["15m"]["current_price"] > 0:
                await self._trigger_callbacks(metrics)

    async def _trigger_callbacks(self, metrics):
        for cb in self.callbacks:
            await cb(metrics)
