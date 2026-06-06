import asyncio
from src.notifier import TelegramNotifier
import logging

logging.basicConfig(level=logging.INFO)

async def main():
    notifier = TelegramNotifier()
    print("Mencoba kirim ke:", notifier.chat_ids)
    await notifier.notify_info("Pesan tes dari script manual!")
    print("Selesai.")

if __name__ == "__main__":
    asyncio.run(main())
