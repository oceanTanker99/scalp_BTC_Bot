import sys
import os
import asyncio
import aiohttp
from dotenv import load_dotenv

async def main():
    load_dotenv()
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_ids = [c.strip() for c in os.getenv("TELEGRAM_CHAT_ID", "").split(",") if c.strip()]
    if not token or not chat_ids:
        print("Token atau Chat ID tidak diset")
        return

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    balance = 100.5
    msg = (
        f"🚀 <b>Bot Scalp BTC Aktif!</b>\n"
        f"━━━━━━━━━━━━━━━━\n"
        f"💰 Saldo Awal : <code>{balance:.4f}</code> USDT\n"
        f"📊 Strategi  : 5M BB + RSI + ADX + OFI + AI\n"
        f"🤖 AI Validator: DeepSeek V4 Pro ✅"
    )
    
    async with aiohttp.ClientSession() as session:
        for chat_id in chat_ids:
            payload = {"chat_id": chat_id, "text": msg, "parse_mode": "HTML"}
            async with session.post(url, json=payload) as resp:
                status = resp.status
                text = await resp.text()
                print(f"Chat ID: {chat_id}, Status: {status}, Response: {text}")

asyncio.run(main())
