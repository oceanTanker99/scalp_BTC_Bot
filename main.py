import asyncio
import logging
import sys
import os
from datetime import datetime, timezone

from binance import AsyncClient

from src.market_stream import MarketStream
from src.strategy import StrategyEngine
from src.live_trader import LiveTrader
from src.ai_analyzer import DeepSeekValidator
from src.notifier import TelegramNotifier
from src.calendar import EconomicCalendar
from src.sentiment import MarketSentiment
from config.config import (
    BINANCE_API_KEY, BINANCE_SECRET_KEY, BINANCE_TESTNET,
    COOLDOWN_CANDLES
)

if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

# --- Setup Logging (Terminal + File Permanen) ---
os.makedirs("logs", exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("logs/bot.log", encoding="utf-8")
    ]
)
log = logging.getLogger(__name__)


class ScalpBot:
    def __init__(self):
        self.client = None  # Shared Binance client — dibuat di start()
        self.stream = None
        self.strategy = StrategyEngine()
        self.trader = None
        self.ai = DeepSeekValidator()
        self.notifier = TelegramNotifier()
        self.calendar = EconomicCalendar()
        self.sentiment = None  # Dibuat di start()

        self.in_position = False
        self._was_in_position = False  # Untuk deteksi transisi posisi
        self.candles_since_last_trade = COOLDOWN_CANDLES  # Mulai siap trading
        self._last_kill_switch_date = None  # Tanggal terakhir kill switch aktif

    async def start(self):
        log.info("🚀 Memulai Scalp BTC Bot...")

        # Buat SATU AsyncClient yang di-share ke semua modul
        self.client = await AsyncClient.create(
            BINANCE_API_KEY, BINANCE_SECRET_KEY, testnet=BINANCE_TESTNET
        )

        # Injeksikan client ke modul-modul
        self.stream = MarketStream(client=self.client)
        self.trader = LiveTrader(client=self.client)
        self.sentiment = MarketSentiment(client=self.client)

        await self.trader.initialize()
        self.trader._notifier = self.notifier
        self.stream.register_callback(self.on_candle_close)

        # Cek posisi aktif saat startup
        self.in_position = await self.trader.has_open_position()
        self._was_in_position = self.in_position
        if self.in_position:
            log.info("📊 Posisi terbuka terdeteksi saat startup. Menunggu posisi tertutup...")

        balance = await self.trader.get_balance()
        await self.notifier.notify_startup(balance)

        # Mulai stream dan calendar di background
        await self.calendar.start()
        # Beri waktu kalender mengambil data awal
        await asyncio.sleep(2)
        
        await self.stream.start()

        # Keep alive
        while True:
            await asyncio.sleep(3600)

    async def on_candle_close(self, df_1m, df_5m, df_15m, ofi):
        # --- Reset kill switch harian (00:00 UTC hari baru) ---
        today_utc = datetime.now(timezone.utc).date()
        if self.trader.is_killed and self._last_kill_switch_date != today_utc:
            log.info("🔄 Hari baru terdeteksi. Mereset kill switch...")
            self.trader.is_killed = False
            self.trader.start_balance = await self.trader.get_balance()

        # --- Cek kill switch ---
        if self.trader.is_killed:
            log.info("🚨 Kill switch aktif. Menunggu hari baru...")
            return

        # --- Cek posisi nyata dari Binance setiap candle ---
        self.in_position = await self.trader.has_open_position()

        # --- FIX BUG-04: Cooldown hanya reset saat transisi posisi (close → open → close) ---
        if self._was_in_position and not self.in_position:
            # Posisi baru saja ditutup — reset cooldown
            self.candles_since_last_trade = 0
            log.info("📉 Posisi tertutup. Cooldown dimulai...")
        self._was_in_position = self.in_position

        # --- Jika masih ada posisi aktif ---
        if self.in_position:
            # Periksa Trailing Stop (Break Even)
            await self.trader.manage_trailing_stop()
        
        # --- Cek News Filter (Kalender Ekonomi) ---
        blocking_news = self.calendar.get_current_blocking_event()
        if blocking_news:
            if not self.calendar.is_paused:
                self.calendar.is_paused = True
                event_time_str = blocking_news['dt'].strftime("%Y-%m-%d %H:%M")
                log.warning(f"📰 NEWS FILTER AKTIF: Menghindari rilis {blocking_news['title']} ({blocking_news['country']})")
                await self.notifier.notify_news_pause(blocking_news['title'], blocking_news['country'], event_time_str)
            
            # Jika ada posisi terbuka, biarkan (karena trailing stop sudah di-manage di atas), tapi tolak sinyal baru
            return
        else:
            if self.calendar.is_paused:
                self.calendar.is_paused = False
                log.info("✅ Badai berita berlalu. Bot kembali beroperasi normal.")
                await self.notifier.notify_news_resume()
                self.candles_since_last_trade = 0  # Opsional: reset cooldown agar langsung siap

        # --- Jika masih ada posisi aktif (lanjutan Ghost Signal) ---
        if self.in_position:

            # Hitung cooldown meskipun sedang hold (agar siap saat posisi tutup)
            self.candles_since_last_trade += 1
            log.info("📊 Posisi masih terbuka. Menjalankan trailing stop management.")

            # Ghost Signal: analisis strategi tanpa eksekusi (tetap kirim ke AI jika ada sinyal)
            signal, price, sl_distance, context = self.strategy.analyze(df_1m, df_5m, df_15m, ofi)
            if signal in ['LONG', 'SHORT']:
                log.info(
                    f"👻 [GHOST SIGNAL] {signal} @ {price:.1f} | "
                    f"Skor: {context.get('score', '?')}/5"
                )
                sentiment_data = await self.sentiment.get_sentiment()
                is_approved, reasoning = await self.ai.validate(signal, df_5m, ofi, context, sentiment_data)
                if is_approved:
                    log.info(f"👻 AI menyetujui ghost signal — tidak dieksekusi (posisi aktif).")
                    await self.notifier.notify_ghost_signal(signal, price, reasoning)
                else:
                    log.info(f"👻 AI menolak ghost signal: {reasoning}")
            return

        # --- Cooldown check ---
        self.candles_since_last_trade += 1
        if self.candles_since_last_trade < COOLDOWN_CANDLES:
            remaining = COOLDOWN_CANDLES - self.candles_since_last_trade
            log.info(f"⏳ [COOLDOWN] Menunggu {remaining} candle lagi sebelum boleh entry.")
            return

        # --- Jalankan analisis strategi ---
        signal, price, sl_distance, context = self.strategy.analyze(df_1m, df_5m, df_15m, ofi)

        if signal in ['LONG', 'SHORT']:
            log.info(
                f"📡 [SINYAL] {signal} @ {price:.1f} | "
                f"Skor: {context.get('score', '?')}/5 | "
                f"RSI: {context.get('rsi', '?')} | ADX: {context.get('adx', '?')}"
            )

            # Kirim ke DeepSeek AI untuk validasi akhir
            sentiment_data = await self.sentiment.get_sentiment()
            is_approved, reasoning = await self.ai.validate(signal, df_5m, ofi, context, sentiment_data)

            if is_approved:
                log.info("✅ AI menyetujui sinyal → Eksekusi order...")
                sl_price, tp_price, qty = await self.trader.execute_trade(signal, price, sl_distance)

                if sl_price:
                    self.in_position = True
                    self._was_in_position = True
                    self.candles_since_last_trade = 0
                    await self.notifier.notify_trade(signal, price, qty, sl_price, tp_price)
            else:
                log.info(f"❌ AI menolak sinyal | Alasan: {reasoning}")
                await self.notifier.notify_ai_rejected(signal, price, reasoning)


if __name__ == "__main__":
    bot = ScalpBot()
    try:
        asyncio.run(bot.start())
    except KeyboardInterrupt:
        log.info("🛑 Bot dihentikan oleh pengguna.")
    except Exception as e:
        log.error(f"💥 Fatal error: {e}", exc_info=True)
        asyncio.run(bot.notifier.notify_error(str(e)))
