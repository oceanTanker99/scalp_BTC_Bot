import logging
import aiohttp
from config.config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_IDS

log = logging.getLogger(__name__)

import asyncio

class TelegramNotifier:
    def __init__(self):
        self.token = TELEGRAM_BOT_TOKEN
        self.chat_ids = TELEGRAM_CHAT_IDS
        self.enabled = bool(self.token and self.chat_ids)
        self._session = None
        if not self.enabled:
            log.warning("Notifikasi Telegram dinonaktifkan: TOKEN atau CHAT_ID tidak ditemukan.")

    async def _get_session(self):
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

    async def send(self, message: str):
        if not self.enabled:
            return
        url = f"https://api.telegram.org/bot{self.token}/sendMessage"
        try:
            session = await self._get_session()
            for chat_id in self.chat_ids:
                payload = {"chat_id": chat_id, "text": message, "parse_mode": "HTML"}
                async with session.post(url, json=payload, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    if resp.status != 200:
                        log.error(f"Gagal mengirim pesan Telegram ke {chat_id}: {resp.status}")
        except Exception as e:
            log.error(f"Error Telegram: {e}")
            self._session = None  # Reset session jika error

    async def _send_to_chat(self, chat_id: str, message: str):
        url = f"https://api.telegram.org/bot{self.token}/sendMessage"
        payload = {"chat_id": chat_id, "text": message, "parse_mode": "HTML"}
        try:
            session = await self._get_session()
            async with session.post(url, json=payload, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status != 200:
                    log.error(f"Gagal membalas Telegram ke {chat_id}: {resp.status}")
        except Exception as e:
            log.error(f"Gagal membalas Telegram ke {chat_id}: {e}")

    async def start_polling(self, trader):
        if not self.enabled:
            return
        url = f"https://api.telegram.org/bot{self.token}/getUpdates"
        offset = 0
        log.info("📡 Mulai mendengarkan perintah Telegram (/status, /balance, /kill)...")
        
        while True:
            try:
                session = await self._get_session()
                poll_payload = {"offset": offset, "timeout": 30}
                async with session.get(url, params=poll_payload, timeout=aiohttp.ClientTimeout(total=40)) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        for update in data.get("result", []):
                            offset = update["update_id"] + 1
                            msg = update.get("message", {})
                            text = msg.get("text", "").strip()
                            chat_id = str(msg.get("chat", {}).get("id", ""))
                            
                            # Verifikasi keamanan: Hanya memproses dari chat ID yang terdaftar
                            if chat_id in self.chat_ids and text.startswith("/"):
                                log.info(f"Telegram Command: {text} dari {chat_id}")
                                if text == "/status":
                                    pos_msg = await trader.get_active_position_details()
                                    await self._send_to_chat(chat_id, pos_msg)
                                elif text == "/balance":
                                    bal = await trader.get_balance()
                                    await self._send_to_chat(chat_id, f"💰 <b>Saldo Saat Ini:</b>\n<code>{bal:,.4f}</code> USDT")
                                elif text == "/kill":
                                    trader.is_killed = True
                                    await self._send_to_chat(chat_id, "🚨 <b>KILL SWITCH AKTIF!</b>\nBot berhenti beroperasi untuk hari ini secara manual.")
                                elif text == "/ping":
                                    await self._send_to_chat(chat_id, "🏓 <b>PONG!</b> Bot Scalp BTC sedang online.")
            except asyncio.TimeoutError:
                pass
            except Exception as e:
                log.error(f"Error Telegram Polling: {e}")
                self._session = None  # Reset session jika error polling
                await asyncio.sleep(5)

    async def notify_trade(self, signal: str, price: float, qty: float, sl: float, tp: float):
        emoji = "🟢" if signal == "LONG" else "🔴"
        msg = (
            f"{emoji} <b>TRADE DIEKSEKUSI: {signal}</b>\n"
            f"━━━━━━━━━━━━━━━━\n"
            f"💰 Entry  : <code>{price:,.1f}</code> USDT\n"
            f"📦 Qty    : <code>{qty}</code> BTC\n"
            f"🛑 SL     : <code>{sl:,.1f}</code> USDT\n"
            f"🎯 TP     : <code>{tp:,.1f}</code> USDT\n"
            f"━━━━━━━━━━━━━━━━\n"
            f"🤖 Divalidasi oleh DeepSeek AI"
        )
        await self.send(msg)

    async def notify_ai_rejected(self, signal: str, price: float, reasoning: str):
        msg = (
            f"🚫 <b>SINYAL DITOLAK AI: {signal}</b>\n"
            f"━━━━━━━━━━━━━━━━\n"
            f"💰 Harga  : <code>{price:,.1f}</code> USDT\n"
            f"🧠 Alasan : {reasoning}\n"
        )
        await self.send(msg)

    async def notify_ghost_signal(self, signal: str, price: float, reasoning: str):
        reason_text = reasoning[:200] + "..." if len(reasoning) > 200 else reasoning
        msg = (
            f"👻 <b>[GHOST SIGNAL] AI MENYETUJUI: {signal}</b>\n"
            f"━━━━━━━━━━━━━━━━\n"
            f"⚠️ <i>Tidak dieksekusi karena ada posisi aktif</i>\n"
            f"💰 Harga  : <code>{price:,.1f}</code> USDT\n"
            f"🧠 Alasan : {reason_text}\n"
        )
        await self.send(msg)

    async def notify_kill_switch(self, drawdown_pct: float, balance: float):
        msg = (
            f"🚨 <b>KILL SWITCH AKTIF!</b>\n"
            f"━━━━━━━━━━━━━━━━\n"
            f"📉 Drawdown  : <code>{drawdown_pct:.2%}</code>\n"
            f"💰 Saldo saat ini: <code>{balance:.4f}</code> USDT\n"
            f"🛑 Bot berhenti trading hari ini."
        )
        await self.send(msg)

    async def notify_error(self, error_msg: str):
        msg = f"💥 <b>FATAL ERROR</b> 💥\n\n<code>{error_msg}</code>\n\nBot mungkin terhenti!"
        await self.send(msg)

    async def notify_news_pause(self, event_title: str, country: str, event_time_str: str):
        msg = (
            f"📰 <b>NEWS FILTER AKTIF!</b> 📰\n\n"
            f"Mengamankan bot karena ada rilis data High Impact:\n"
            f"📌 <b>Event:</b> {event_title} ({country})\n"
            f"⏰ <b>Waktu:</b> {event_time_str} UTC\n\n"
            f"<i>Bot masuk mode siaga. Tidak akan mencari sinyal baru selama 30 menit sebelum/sesudah berita.</i>"
        )
        await self.send(msg)

    async def notify_news_resume(self):
        msg = "✅ <b>NEWS FILTER SELESAI</b>\n\nBadai volatilitas berita telah berlalu. Bot kembali berburu sinyal di pasar! 🏹"
        await self.send(msg)

    async def notify_info(self, info_msg: str):
        msg = f"ℹ️ <b>INFO BOT</b>\n{info_msg}"
        await self.send(msg)

    async def notify_startup(self, balance: float):
        msg = (
            f"🚀 <b>Bot Scalp BTC Aktif!</b>\n"
            f"━━━━━━━━━━━━━━━━\n"
            f"💰 Saldo Awal : <code>{balance:.4f}</code> USDT\n"
            f"📊 Strategi  : 5M BB + RSI + ADX + OFI + AI\n"
            f"🤖 AI Validator: DeepSeek V4 Pro ✅"
        )
        await self.send(msg)
