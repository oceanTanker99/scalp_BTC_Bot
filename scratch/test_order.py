import asyncio
from binance import AsyncClient
from config.config import BINANCE_API_KEY, BINANCE_SECRET_KEY

async def main():
    client = await AsyncClient.create(api_key=BINANCE_API_KEY, api_secret=BINANCE_SECRET_KEY)
    try:
        print("⚙️ Mengubah Leverage ke 5x...")
        await client.futures_change_leverage(symbol='BTCUSDT', leverage=5)
        
        print("⚙️ Mengubah Margin ke ISOLATED...")
        try:
            await client.futures_change_margin_type(symbol='BTCUSDT', marginType='ISOLATED')
        except Exception:
            pass # Ignore if already ISOLATED
            
        print("🚀 Mengeksekusi Market Order LONG BTCUSDT (0.001 BTC)...")
        order = await client.futures_create_order(
            symbol='BTCUSDT',
            side='BUY',
            type='MARKET',
            quantity=0.001
        )
        print("✅ ORDER BERHASIL DIEKSEKUSI!")
        print(f"Harga Eksekusi Rata-rata: {order.get('avgPrice', 'N/A')}")
        print(f"Status: {order.get('status', 'N/A')}")
        print("⚠️ HARAP SEGERA CEK APLIKASI BINANCE ANDA DAN TUTUP POSISINYA JIKA INI HANYA TES!")
    except Exception as e:
        print("❌ GAGAL Eksekusi:", e)
    finally:
        await client.close_connection()

if __name__ == "__main__":
    asyncio.run(main())
