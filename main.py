import asyncio
import logging
import sys
import os

from src.market_stream import MarketStream
from src.strategy import StrategyEngine
from src.live_trader import LiveTrader
from src.ai_analyzer import DeepSeekValidator
from src.notifier import TelegramNotifier
from config.config import COOLDOWN_CANDLES

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
        self.stream = MarketStream()
        self.strategy = StrategyEngine()
        self.trader = LiveTrader()
        self.ai = DeepSeekValidator()
        self.notifier = TelegramNotifier()
        self.stream.register_callback(self.on_candle_close)

        self.in_position = False
        # Perbaikan #6: Cooldown timer pasca trade
        self.candles_since_last_trade = COOLDOWN_CANDLES  # Start ready

    async def start(self):
        log.info("Starting Scalp BTC Bot...")
        await self.trader.initialize()

        # Cek posisi aktif saat startup
        self.in_position = await self.trader.has_open_position()
        if self.in_position:
            log.info("Posisi terbuka terdeteksi saat startup. Menunggu posisi tertutup...")

        balance = await self.trader.get_balance()
        await self.notifier.notify_startup(balance)

        await self.stream.start()

        # Keep alive
        while True:
            await asyncio.sleep(3600)

    async def on_candle_close(self, df_1m, df_5m, df_15m, ofi):
        # Perbaikan #6: Hitung cooldown
        self.candles_since_last_trade += 1

        # Cek posisi nyata dari Binance setiap candle
        self.in_position = await self.trader.has_open_position()

        if self.in_position:
            log.info("[SKIP] Posisi masih terbuka. Menunggu SL/TP...")
            return

        # Cooldown check
        if self.candles_since_last_trade < COOLDOWN_CANDLES:
            remaining = COOLDOWN_CANDLES - self.candles_since_last_trade
            log.info(f"[COOLDOWN] Menunggu {remaining} candle lagi sebelum boleh entry.")
            return

        # Jalankan analisis strategi
        signal, price, sl_distance, context = self.strategy.analyze(df_1m, df_5m, df_15m, ofi)

        if signal in ['LONG', 'SHORT']:
            log.info(
                f"[SIGNAL] {signal} @ {price:.1f} | "
                f"Skor: {context.get('score', '?')}/5 | "
                f"RSI: {context.get('rsi', '?')} | ADX: {context.get('adx', '?')}"
            )

            # Kirim ke DeepSeek AI untuk validasi akhir dengan konteks penuh
            is_approved, reasoning = await self.ai.validate(signal, df_5m, ofi, context)

            if is_approved:
                log.info("AI MENYETUJUI → Eksekusi order...")
                sl_price, tp_price, qty = await self.trader.execute_trade(signal, price, sl_distance)

                if sl_price:
                    self.in_position = True
                    self.candles_since_last_trade = 0  # Reset cooldown
                    await self.notifier.notify_trade(signal, price, qty, sl_price, tp_price)
            else:
                log.info(f"AI MENOLAK | Alasan: {reasoning}")
                await self.notifier.notify_ai_rejected(signal, price, reasoning)

if __name__ == "__main__":
    bot = ScalpBot()
    try:
        asyncio.run(bot.start())
    except KeyboardInterrupt:
        log.info("Bot dihentikan oleh pengguna.")
    except Exception as e:
        log.error(f"Fatal error: {e}", exc_info=True)
        asyncio.run(bot.notifier.notify_error(str(e)))
