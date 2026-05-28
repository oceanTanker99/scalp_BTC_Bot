import asyncio
import logging
import sys
import os

from src.live_trader import LiveTrader
from binance import AsyncClient

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
log = logging.getLogger("TestTrade")

async def test_execution():
    log.info("Memulai uji coba eksekusi manual...")
    
    trader = LiveTrader()
    # Override waktu tunggu agar peluang order terjemput pasar lebih besar
    import src.live_trader
    src.live_trader.CHASE_WAIT_SECONDS = 15
    src.live_trader.CHASE_MAX_ATTEMPTS = 5
    
    await trader.initialize()
    
    # Cek posisi
    has_pos = await trader.has_open_position()
    log.info(f"Apakah ada posisi terbuka? {has_pos}")
    
    if has_pos:
        log.warning("Harap tutup posisi terlebih dahulu untuk menguji entry baru.")
        await trader.client.close_connection()
        return

    # Ambil harga BTC saat ini untuk dummy trade
    try:
        ticker = await trader.client.futures_symbol_ticker(symbol="BTCUSDT")
        current_price = float(ticker['price'])
        log.info(f"Harga BTC saat ini: {current_price}")
    except Exception as e:
        log.error(f"Gagal mengambil harga: {e}")
        await trader.client.close_connection()
        return

    # Uji Coba Entry LONG dengan jarak SL 0.5% (sl_distance = 0.005)
    signal = 'LONG'
    sl_distance = 0.005
    
    log.info(f"Mencoba mengirim {signal} Order. Harga acuan: {current_price}, SL Distance: 0.5%")
    
    # Execute Trade
    sl_price, tp_price, qty = await trader.execute_trade(signal, current_price, sl_distance)
    
    if sl_price:
        log.info(f"✅ UJI COBA BERHASIL! Qty: {qty}, SL: {sl_price}, TP: {tp_price}")
    else:
        log.error("❌ UJI COBA GAGAL! Bot gagal mengeksekusi trade.")

    await trader.client.close_connection()

if __name__ == "__main__":
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(test_execution())
