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
        self.funding_rate = 0.0

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
            asyncio.create_task(self._poll_macro_data()),
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
        tick_count = 0
        async with self.bsm.aggtrade_socket(symbol=SYMBOL) as stream:
            while self._running:
                try:
                    # Timeout 30 detik untuk mencegah hanging connection
                    msg = await asyncio.wait_for(stream.recv(), timeout=30.0)
                except asyncio.TimeoutError:
                    raise ConnectionError("AggTrade stream timeout. Tidak ada data selama 30 detik.")
                
                if isinstance(msg, dict) and msg.get('e') == 'error':
                    raise ConnectionError(f"Binance Server Error: {msg.get('m')}")
                
                self.engine.process_agg_trade(msg)
                tick_count += 1
                if tick_count % 100 == 0:
                    log.info(f"Received {tick_count} ticks... VWAP: {self.engine.get_metrics()['vwap']:.2f}")

    async def _depth_stream(self):
        log.info("Memulai depth stream (L2 Imbalance)...")
        async with self.bsm.depth_socket(symbol=SYMBOL, depth="5") as stream:
            while self._running:
                try:
                    msg = await asyncio.wait_for(stream.recv(), timeout=30.0)
                except asyncio.TimeoutError:
                    raise ConnectionError("Depth stream timeout. Tidak ada data selama 30 detik.")
                
                if isinstance(msg, dict) and msg.get('e') == 'error':
                    raise ConnectionError(f"Binance Server Error: {msg.get('m')}")
                self.engine.process_depth(msg)

    async def _evaluation_loop(self):
        log.info(f"Memulai loop evaluasi strategi setiap {EVALUATION_INTERVAL} detik...")
        while self._running:
            await asyncio.sleep(EVALUATION_INTERVAL)
            # Metrik sekarang berisi data 15m, 1h, dan 4h secara native dari Rust
            metrics = self.engine.get_metrics()
            
            # Inject macro data
            metrics['funding_rate'] = self.funding_rate
            
            if metrics["15m"]["current_price"] > 0:
                await self._trigger_callbacks(metrics)

    async def _poll_macro_data(self):
        log.info("Memulai polling macro data (Funding Rate)...")
        while self._running:
            try:
                # Fetch mark price and funding rate
                res = await self.client.futures_mark_price(symbol=SYMBOL)
                self.funding_rate = float(res.get('lastFundingRate', 0.0))
            except Exception as e:
                log.error(f"Gagal mengambil macro data: {e}")
            await asyncio.sleep(60)

    async def _trigger_callbacks(self, metrics):
        for cb in self.callbacks:
            await cb(metrics)
