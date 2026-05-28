"""
debug_all_orders.py
Memeriksa SEMUA jenis order Binance Futures yang mungkin:
- Open Orders standar
- Conditional Orders (Algo)
- Position info lengkap
"""
import os, asyncio, json
from dotenv import load_dotenv
from binance import AsyncClient

async def main():
    load_dotenv()
    client = await AsyncClient.create(
        api_key=os.getenv("BINANCE_API_KEY"),
        api_secret=os.getenv("BINANCE_SECRET_KEY"),
        testnet=os.getenv("BINANCE_TESTNET","true").lower()=="true"
    )

    print("\n===== 1. POSISI AKTIF =====")
    positions = await client.futures_position_information(symbol="BTCUSDT")
    for p in positions:
        if float(p.get('positionAmt', 0)) != 0:
            print(json.dumps(p, indent=2))

    print("\n===== 2. OPEN ORDERS (Standar) =====")
    open_orders = await client.futures_get_open_orders(symbol="BTCUSDT")
    if open_orders:
        for o in open_orders:
            print(f"  Type: {o['type']} | Side: {o['side']} | StopPrice: {o.get('stopPrice')} | Price: {o.get('price')}")
    else:
        print("  (Kosong)")

    print("\n===== 3. ALL ORDERS (Histori lengkap 50 terakhir) =====")
    all_orders = await client.futures_get_all_orders(symbol="BTCUSDT", limit=20)
    for o in all_orders[-10:]:
        print(f"  [{o['status']}] Type: {o['type']} | Side: {o['side']} | StopPrice: {o.get('stopPrice')} | Price: {o.get('price')}")

    print("\n===== 4. CONDITIONAL ORDERS (Algo - SL/TP dari HP) =====")
    try:
        algo_orders = await client._request_futures_api('get', 'openOrders', True, data={'symbol': 'BTCUSDT'})
        print(f"  Algo Open Orders: {json.dumps(algo_orders, indent=2)}")
    except Exception as e:
        print(f"  Error: {e}")

    print("\n===== 5. RAW POSITION DETAIL (liquidation price dll) =====")
    try:
        raw = await client.futures_account()
        for pos in raw.get('positions', []):
            if pos['symbol'] == 'BTCUSDT' and float(pos.get('positionAmt',0)) != 0:
                print(json.dumps(pos, indent=2))
    except Exception as e:
        print(f"  Error: {e}")

    await client.close_connection()
    print("\nSelesai.")

asyncio.run(main())
