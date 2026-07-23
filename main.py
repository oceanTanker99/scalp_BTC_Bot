import asyncio
import logging
import sys
import os
from datetime import datetime, timezone

from binance import AsyncClient

from src.market_stream import MarketStream
from src.strategy import StrategyEngine
from src.live_trader import LiveTrader
from src.ai_analyzer import AITuner
from src.notifier import TelegramNotifier
from config.config import (
    BINANCE_API_KEY, BINANCE_SECRET_KEY, BINANCE_TESTNET
)

if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding='utf-8')

# --- Setup Logging (Terminal + File Permanen) ---
os.makedirs("logs", exist_ok=True)
handlers = [logging.StreamHandler(sys.stdout)]
try:
    handlers.append(logging.FileHandler("logs/bot.log", encoding="utf-8"))
except PermissionError:
    pass

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=handlers
)
log = logging.getLogger(__name__)


class ScalpBot:
    def __init__(self):
        self.client = None
        self.stream = None
        self.strategy = StrategyEngine()
        self.trader = None
        self.ai_tuner = None
        self.notifier = TelegramNotifier()

        self.in_position = False
        self._last_kill_switch_date = None

    async def start(self):
        log.info("🚀 Memulai Scalp BTC Bot (HFT Order Flow Edition)...")

        self.client = await AsyncClient.create(
            BINANCE_API_KEY, BINANCE_SECRET_KEY, testnet=BINANCE_TESTNET
        )

        self.stream = MarketStream(client=self.client)
        self.trader = LiveTrader(client=self.client)
        
        # Pass OrderFlowEngine to AI Tuner
        self.ai_tuner = AITuner(engine=self.stream.engine)

        await self.trader.initialize()
        self.trader._notifier = self.notifier
        self.stream.register_callback(self.on_metrics_update)

        self.in_position = await self.trader.has_open_position()
        if self.in_position:
            log.info("📊 Posisi terbuka terdeteksi saat startup. Menunggu posisi tertutup...")

        balance = await self.trader.get_balance()
        await self.notifier.notify_startup(balance)

        # Mulai tasks background
        self._polling_task = asyncio.create_task(self.notifier.start_polling(self.trader, self.stream.engine, self.strategy))
        self._ai_tuning_task = asyncio.create_task(self.ai_tuner.start_tuning_loop())
        
        await self.stream.start()

        # Keep alive
        while True:
            await asyncio.sleep(3600)

    async def on_metrics_update(self, metrics):
        # Callback ini dipanggil setiap beberapa detik oleh MarketStream
        today_utc = datetime.now(timezone.utc).date()
        if self.trader.is_killed and self._last_kill_switch_date != today_utc:
            log.info("🔄 Hari baru terdeteksi. Mereset kill switch...")
            self.trader.is_killed = False
            self._last_kill_switch_date = today_utc
            self.trader.start_balance = await self.trader.get_balance()

        if self.trader.is_killed:
            return

        # Sinkronisasi API secara berkala agar tidak kena Timestamp error
        await self.trader.sync_time()

        # Cek posisi
        current_in_position = await self.trader.has_open_position()

        # Deteksi penutupan posisi untuk mencatat jurnal
        if self.in_position and not current_in_position:
            log.info("📊 Posisi telah tertutup. Merekam ke Live Trade Journal...")
            await self.trader.log_closed_trade()

        self.in_position = current_in_position

        if self.in_position:
            await self.trader.manage_trailing_stop()
            # Jangan eksekusi sinyal baru jika masih ada posisi aktif
            return

        # Evaluasi Order Flow Metrics via StrategyEngine
        signal, price, sl_distance = self.strategy.analyze_order_flow(metrics)

        if signal in ['LONG', 'SHORT']:
            valid_signal = True
            
            # Filter 1: NY Session Kill Zone (13:00 - 15:59 UTC)
            dt_utc = datetime.now(timezone.utc)
            if 13 <= dt_utc.hour <= 15:
                valid_signal = False
                log.info(f"🛡️ Sinyal {signal} diabaikan (NY Kill Zone: {dt_utc.hour:02d}:00 UTC).")
            
            # Filter 2: VWAP Distance (> 0.45%)
            if valid_signal and '15m' in metrics and 'vwap' in metrics['15m']:
                vwap = metrics['15m']['vwap']
                if vwap > 0:
                    dist_to_vwap = abs(price - vwap) / vwap * 100
                    if dist_to_vwap < 0.45:
                        valid_signal = False
                        log.info(f"🛡️ Sinyal {signal} diabaikan (Jarak VWAP {dist_to_vwap:.2f}% < 0.45%).")
                        
            if valid_signal:
                log.info(f"⚡ [EKSEKUSI HFT] Sinyal {signal} @ {price:.1f} terdeteksi! Mengeksekusi...")
                
                # Eksekusi langsung tanpa LLM Validator (karena parameter sudah dituning background)
                sl_price, tp_price, qty = await self.trader.execute_trade(signal, price, sl_distance)

                if sl_price:
                    self.in_position = True
                    await self.notifier.notify_trade(signal, price, qty, sl_price, tp_price)

if __name__ == "__main__":
    bot = ScalpBot()
    try:
        asyncio.run(bot.start())
    except KeyboardInterrupt:
        log.info("🛑 Bot dihentikan oleh pengguna.")
    except Exception as e:
        log.error(f"💥 Fatal error: {e}", exc_info=True)
        try:
            loop = asyncio.new_event_loop()
            loop.run_until_complete(bot.notifier.notify_error(str(e)))
            loop.close()
        except Exception:
            log.error("Gagal mengirim notifikasi fatal error ke Telegram.")
