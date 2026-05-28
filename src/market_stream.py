import asyncio
import logging
from binance import AsyncClient, BinanceSocketManager
import pandas as pd

from config.config import BINANCE_API_KEY, BINANCE_SECRET_KEY, BINANCE_TESTNET, SYMBOL

log = logging.getLogger(__name__)

RECONNECT_DELAY_SECONDS = 5
MAX_KLINES = 300  # Batas maksimum candle yang disimpan (bug #9 pencegahan memory leak)

class MarketStream:
    def __init__(self):
        self.client = None
        self.bsm = None
        self.klines_1m = []
        self.klines_5m = []
        self.klines_15m = []
        self.orderbook = {"bids": [], "asks": []}
        self.callbacks = []
        self._running = True

    def register_callback(self, callback):
        self.callbacks.append(callback)

    async def start(self):
        self.client = await AsyncClient.create(
            BINANCE_API_KEY, BINANCE_SECRET_KEY, testnet=BINANCE_TESTNET
        )
        self.bsm = BinanceSocketManager(self.client)
        
        await self._load_historical()

        # Perbaikan Bug #4: Setiap stream dibungkus dengan loop reconnect
        asyncio.create_task(self._run_with_reconnect("1m", self._kline_stream))
        asyncio.create_task(self._run_with_reconnect("5m", self._kline_stream))
        asyncio.create_task(self._run_with_reconnect("15m", self._kline_stream))
        asyncio.create_task(self._run_depth_with_reconnect())

    # --- Perbaikan Bug #4: Reconnect Wrapper ---
    async def _run_with_reconnect(self, interval: str, stream_fn):
        while self._running:
            try:
                await stream_fn(interval)
            except Exception as e:
                log.error(f"Stream {interval} terputus: {e}. Reconnect dalam {RECONNECT_DELAY_SECONDS} detik...")
                await asyncio.sleep(RECONNECT_DELAY_SECONDS)
                # Muat ulang data historis setelah reconnect
                try:
                    await self._load_historical()
                except Exception as reload_err:
                    log.error(f"Gagal reload historical data: {reload_err}")

    async def _run_depth_with_reconnect(self):
        while self._running:
            try:
                await self._depth_stream()
            except Exception as e:
                log.error(f"Depth stream terputus: {e}. Reconnect dalam {RECONNECT_DELAY_SECONDS} detik...")
                await asyncio.sleep(RECONNECT_DELAY_SECONDS)

    async def _load_historical(self):
        log.info("Loading historical data for initial calculations...")
        res_1m = await self.client.futures_klines(symbol=SYMBOL, interval="1m", limit=100)
        self.klines_1m = self._parse_klines(res_1m)
        
        res_5m = await self.client.futures_klines(symbol=SYMBOL, interval="5m", limit=100)
        self.klines_5m = self._parse_klines(res_5m)

        res_15m = await self.client.futures_klines(symbol=SYMBOL, interval="15m", limit=250)
        self.klines_15m = self._parse_klines(res_15m)

    def _parse_klines(self, klines):
        return [{
            "timestamp": k[0],
            "open": float(k[1]),
            "high": float(k[2]),
            "low": float(k[3]),
            "close": float(k[4]),
            "volume": float(k[5]),
        } for k in klines]

    def _update_klines(self, kline_list: list, formatted: dict, max_size: int = MAX_KLINES):
        """Update daftar klines dengan candle baru, jaga batas maksimum (anti memory leak)."""
        if len(kline_list) >= max_size:
            kline_list.pop(0)
        kline_list.append(formatted)

    async def _kline_stream(self, interval):
        log.info(f"Starting {interval} kline stream...")
        async with self.bsm.kline_socket(symbol=SYMBOL, interval=interval) as stream:
            while True:
                msg = await stream.recv()
                kline = msg['k']
                
                formatted = {
                    "timestamp": kline['t'],
                    "open": float(kline['o']),
                    "high": float(kline['h']),
                    "low": float(kline['l']),
                    "close": float(kline['c']),
                    "volume": float(kline['v'])
                }
                
                if interval == "1m":
                    if kline['x']:
                        self._update_klines(self.klines_1m, formatted)
                    else:
                        if self.klines_1m and self.klines_1m[-1]['timestamp'] == formatted['timestamp']:
                            self.klines_1m[-1] = formatted
                        else:
                            self.klines_1m.append(formatted)

                elif interval == "5m":
                    if kline['x']:
                        self._update_klines(self.klines_5m, formatted)
                        await self._trigger_callbacks()
                    else:
                        if self.klines_5m and self.klines_5m[-1]['timestamp'] == formatted['timestamp']:
                            self.klines_5m[-1] = formatted
                        else:
                            self.klines_5m.append(formatted)

                elif interval == "15m":
                    if kline['x']:
                        self._update_klines(self.klines_15m, formatted)
                    else:
                        if self.klines_15m and self.klines_15m[-1]['timestamp'] == formatted['timestamp']:
                            self.klines_15m[-1] = formatted
                        else:
                            self.klines_15m.append(formatted)

    async def _depth_stream(self):
        log.info("Starting depth stream for OFI...")
        async with self.bsm.depth_socket(symbol=SYMBOL, depth="5") as stream:
            while True:
                msg = await stream.recv()
                if 'bids' in msg and 'asks' in msg:
                    self.orderbook['bids'] = [[float(x[0]), float(x[1])] for x in msg['bids']]
                    self.orderbook['asks'] = [[float(x[0]), float(x[1])] for x in msg['asks']]

    def get_ofi(self) -> float:
        if not self.orderbook['bids'] or not self.orderbook['asks']:
            return 0
        bid_vol = sum(vol for _, vol in self.orderbook['bids'])
        ask_vol = sum(vol for _, vol in self.orderbook['asks'])
        total = bid_vol + ask_vol
        if total == 0:
            return 0
        return (bid_vol - ask_vol) / total

    def get_dataframes(self):
        df_1m = pd.DataFrame(self.klines_1m)
        df_5m = pd.DataFrame(self.klines_5m)
        df_15m = pd.DataFrame(self.klines_15m)
        return df_1m, df_5m, df_15m

    async def _trigger_callbacks(self):
        ofi = self.get_ofi()
        df_1m, df_5m, df_15m = self.get_dataframes()
        for cb in self.callbacks:
            await cb(df_1m, df_5m, df_15m, ofi)
