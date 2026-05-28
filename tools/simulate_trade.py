import asyncio
import os
import sys
from dotenv import load_dotenv

from src.notifier import TelegramNotifier
from src.live_trader import LiveTrader

if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

async def run_simulation():
    print("🚀 Memulai Simulasi Trading & Notifikasi...")
    load_dotenv()
    
    notifier = TelegramNotifier()
    trader = LiveTrader()
    trader._notifier = notifier
    
    print("\n[1] Mengirim pesan startup bot...")
    await notifier.notify_startup(15.20)
    await asyncio.sleep(2)
    
    print("\n[2] Simulasi Sinyal Ditolak AI...")
    await notifier.notify_ai_rejected(
        signal="LONG", 
        price=73100.5, 
        reasoning="Tren makro 1H masih sangat bearish dan belum ada konfirmasi reversal dari volume. Terlalu berisiko."
    )
    await asyncio.sleep(2)
    
    print("\n[3] Simulasi Trade Dieksekusi...")
    await notifier.notify_trade(
        signal="SHORT",
        price=74500.0,
        qty=0.005,
        sl=75100.0,
        tp=73000.0
    )
    await asyncio.sleep(2)
    
    print("\n[4] Simulasi Trailing Stop (Memindahkan SL ke BE)...")
    await notifier.notify_info(
        "🛡️ <b>Trailing Stop Aktif!</b>\n"
        "Profit mencapai > 0.5%. SL telah dipindah ke titik impas: <code>74,500.0</code>"
    )
    await asyncio.sleep(2)
    
    print("\n[5] Uji coba Trailing Stop pada posisi riil Anda (jika profit > 0.5%)...")
    await trader.initialize()
    await trader.manage_trailing_stop()
    await trader.client.close_connection()

    print("\n✅ Simulasi selesai. Silakan periksa Telegram Anda!")

if __name__ == "__main__":
    asyncio.run(run_simulation())
