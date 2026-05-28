import logging
import asyncio
import aiohttp
from config.config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID

log = logging.getLogger(__name__)

class TelegramNotifier:
    def __init__(self):
        self.token = TELEGRAM_BOT_TOKEN
        self.chat_id = TELEGRAM_CHAT_ID
        self.enabled = bool(self.token and self.chat_id)
        if not self.enabled:
            log.warning("Telegram notifier disabled: TOKEN or CHAT_ID missing.")

    async def send(self, message: str):
        if not self.enabled:
            return
        url = f"https://api.telegram.org/bot{self.token}/sendMessage"
        payload = {"chat_id": self.chat_id, "text": message, "parse_mode": "HTML"}
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    if resp.status != 200:
                        log.error(f"Telegram send failed: {resp.status}")
        except Exception as e:
            log.error(f"Telegram error: {e}")

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
        msg = f"⚠️ <b>ERROR BOT</b>\n<code>{error_msg[:500]}</code>"
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
