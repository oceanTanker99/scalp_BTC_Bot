import os, asyncio
from dotenv import load_dotenv
from binance import AsyncClient
from binance.exceptions import BinanceAPIException

async def main():
    load_dotenv()
    client = await AsyncClient.create(
        api_key=os.getenv("BINANCE_API_KEY"),
        api_secret=os.getenv("BINANCE_SECRET_KEY"),
        testnet=os.getenv("BINANCE_TESTNET", "true").lower() == "true"
    )
    
    symbol = "BTCUSDT"
    
    print(f"🔄 Memeriksa posisi aktif untuk {symbol}...")
    positions = await client.futures_position_information(symbol=symbol)
    active = [p for p in positions if float(p.get('positionAmt', 0)) != 0]
    
    if not active:
        print("⚠️ Tidak ada posisi aktif.")
        await client.close_connection()
        return
        
    pos = active[0]
    qty = abs(float(pos['positionAmt']))
    direction = "LONG" if float(pos['positionAmt']) > 0 else "SHORT"
    side = "SELL" if direction == "LONG" else "BUY"
    
    print(f"✅ Ditemukan posisi {direction} sebesar {qty} BTC.")
    print("🧹 Membatalkan order SL/TP lama (jika ada)...")
    await client.futures_cancel_all_open_orders(symbol=symbol)
    
    sl_price = "72800"
    tp_price = "85000"
    
    try:
        # Memasang Stop Loss
        print(f"⏳ Memasang Stop Loss di {sl_price}...")
        sl_order = await client.futures_create_order(
            symbol=symbol,
            side=side,
            type="STOP_MARKET",
            stopPrice=sl_price,
            closePosition="true",
            timeInForce="GTC"
        )
        print("✅ Stop Loss berhasil dipasang!")
        
        # Memasang Take Profit
        print(f"⏳ Memasang Take Profit di {tp_price}...")
        tp_order = await client.futures_create_order(
            symbol=symbol,
            side=side,
            type="TAKE_PROFIT_MARKET",
            stopPrice=tp_price,
            closePosition="true",
            timeInForce="GTC"
        )
        print("✅ Take Profit berhasil dipasang!")
        
    except BinanceAPIException as e:
        print(f"❌ Error dari Binance: {e.message}")
    except Exception as e:
        print(f"❌ Error sistem: {e}")
        
    finally:
        await client.close_connection()

if __name__ == "__main__":
    asyncio.run(main())
