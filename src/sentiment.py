import logging
import time
from binance import AsyncClient

log = logging.getLogger(__name__)

SENTIMENT_CACHE_TTL = 300  # Cache selama 5 menit (300 detik)

class MarketSentiment:
    def __init__(self, client: AsyncClient, symbol: str = "BTCUSDT"):
        self.client = client
        self.symbol = symbol
        self._cache = None
        self._cache_time = 0

    async def get_sentiment(self) -> dict:
        """Mengambil data sentimen dari Binance Futures API dengan caching."""
        # Gunakan cache jika masih valid
        now = time.time()
        if self._cache and (now - self._cache_time) < SENTIMENT_CACHE_TTL:
            return self._cache
        
        sentiment_data = {
            "funding_rate": 0.0,
            "open_interest": 0.0,
            "top_long_short_ratio": 1.0,
            "global_long_short_ratio": 1.0
        }
        
        # 1. Funding Rate
        try:
            pi = await self.client.futures_mark_price(symbol=self.symbol)
            if isinstance(pi, dict):
                sentiment_data["funding_rate"] = float(pi.get("lastFundingRate", 0))
            elif isinstance(pi, list) and len(pi) > 0:
                sentiment_data["funding_rate"] = float(pi[0].get("lastFundingRate", 0))
        except Exception as e:
            log.warning(f"Gagal mengambil funding rate: {e}")

        # 2. Open Interest
        try:
            oi = await self.client.futures_open_interest(symbol=self.symbol)
            sentiment_data["open_interest"] = float(oi.get("openInterest", 0))
        except Exception as e:
            log.warning(f"Gagal mengambil open interest: {e}")

        # 3. Top Trader Long/Short Account Ratio (Paus/Whales)
        try:
            top_ls = await self.client.futures_top_longshort_account_ratio(symbol=self.symbol, period="5m")
            if top_ls and len(top_ls) > 0:
                sentiment_data["top_long_short_ratio"] = float(top_ls[0].get("longShortRatio", 1.0))
        except Exception as e:
            log.warning(f"Gagal mengambil top L/S ratio: {e}")

        # 4. Global Long/Short Ratio (Massa/Retail)
        try:
            global_ls = await self.client.futures_global_longshort_ratio(symbol=self.symbol, period="5m")
            if global_ls and len(global_ls) > 0:
                sentiment_data["global_long_short_ratio"] = float(global_ls[0].get("longShortRatio", 1.0))
        except Exception as e:
            log.warning(f"Gagal mengambil global L/S ratio: {e}")

        # Update cache
        self._cache = sentiment_data
        self._cache_time = now
        
        return sentiment_data
