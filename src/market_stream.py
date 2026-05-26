import asyncio
import logging
from binance import AsyncClient, BinanceSocketManager
import pandas as pd
import pandas_ta as ta

from config.config import BINANCE_API_KEY, BINANCE_SECRET_KEY, BINANCE_TESTNET, SYMBOL

log = logging.getLogger(__name__)

class MarketStream:
    def __init__(self):
        self.client = None
        self.bsm = None
        self.klines_1m = []
        self.klines_5m = []
        self.orderbook = {"bids": [], "asks": []}
        self.callbacks = []

    def register_callback(self, callback):
        self.callbacks.append(callback)

    async def start(self):
        self.client = await AsyncClient.create(
            BINANCE_API_KEY, BINANCE_SECRET_KEY, testnet=BINANCE_TESTNET
        )
        self.bsm = BinanceSocketManager(self.client)
        
        # Load historical klines for initial indicator calculation
        await self._load_historical()

        # Start streams
        asyncio.create_task(self._kline_stream("1m"))
        asyncio.create_task(self._kline_stream("5m"))
        asyncio.create_task(self._depth_stream())
        
    async def _load_historical(self):
        log.info("Loading historical data for initial calculations...")
        # 1m data
        res_1m = await self.client.futures_klines(symbol=SYMBOL, interval="1m", limit=100)
        self.klines_1m = self._parse_klines(res_1m)
        
        # 5m data
        res_5m = await self.client.futures_klines(symbol=SYMBOL, interval="5m", limit=100)
        self.klines_5m = self._parse_klines(res_5m)

    def _parse_klines(self, klines):
        # [timestamp, open, high, low, close, volume, ...]
        return [{
            "timestamp": k[0],
            "open": float(k[1]),
            "high": float(k[2]),
            "low": float(k[3]),
            "close": float(k[4]),
            "volume": float(k[5]),
        } for k in klines]

    async def _kline_stream(self, interval):
        log.info(f"Starting {interval} kline stream...")
        async with self.bsm.kline_socket(symbol=SYMBOL, interval=interval) as stream:
            while True:
                msg = await stream.recv()
                kline = msg['k']
                
                # Format
                formatted = {
                    "timestamp": kline['t'],
                    "open": float(kline['o']),
                    "high": float(kline['h']),
                    "low": float(kline['l']),
                    "close": float(kline['c']),
                    "volume": float(kline['v'])
                }
                
                if interval == "1m":
                    if kline['x']: # Candle closed
                        self.klines_1m.pop(0)
                        self.klines_1m.append(formatted)
                        # Trigger strategy on 1m candle close
                        await self._trigger_callbacks()
                    else:
                        # Update current unclosed candle
                        if self.klines_1m[-1]['timestamp'] == formatted['timestamp']:
                            self.klines_1m[-1] = formatted
                        else:
                            self.klines_1m.append(formatted)
                else:
                    if kline['x']:
                        self.klines_5m.pop(0)
                        self.klines_5m.append(formatted)
                    else:
                        if self.klines_5m[-1]['timestamp'] == formatted['timestamp']:
                            self.klines_5m[-1] = formatted
                        else:
                            self.klines_5m.append(formatted)

    async def _depth_stream(self):
        log.info("Starting depth stream for OFI...")
        async with self.bsm.depth_socket(symbol=SYMBOL, depth="5") as stream:
            while True:
                msg = await stream.recv()
                if 'bids' in msg and 'asks' in msg:
                    self.orderbook['bids'] = [[float(x[0]), float(x[1])] for x in msg['bids']]
                    self.orderbook['asks'] = [[float(x[0]), float(x[1])] for x in msg['asks']]

    def get_ofi(self):
        """ Calculate Order Flow Imbalance at the top 5 levels """
        if not self.orderbook['bids'] or not self.orderbook['asks']:
            return 0
        
        bid_vol = sum(vol for price, vol in self.orderbook['bids'])
        ask_vol = sum(vol for price, vol in self.orderbook['asks'])
        
        total = bid_vol + ask_vol
        if total == 0:
            return 0
        return (bid_vol - ask_vol) / total

    def get_dataframes(self):
        df_1m = pd.DataFrame(self.klines_1m)
        df_5m = pd.DataFrame(self.klines_5m)
        return df_1m, df_5m

    async def _trigger_callbacks(self):
        ofi = self.get_ofi()
        df_1m, df_5m = self.get_dataframes()
        for cb in self.callbacks:
            await cb(df_1m, df_5m, ofi)
