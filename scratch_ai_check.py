import os
import json
import asyncio
from dotenv import load_dotenv
from binance import AsyncClient
from openai import AsyncOpenAI

async def main():
    load_dotenv()
    
    binance_api_key = os.getenv("BINANCE_API_KEY")
    binance_secret_key = os.getenv("BINANCE_SECRET_KEY")
    deepseek_api_key = os.getenv("DEEPSEEK_API_KEY")
    testnet = os.getenv("BINANCE_TESTNET", "true").lower() == "true"
    
    # Initialize Binance
    client = await AsyncClient.create(api_key=binance_api_key, api_secret=binance_secret_key, testnet=testnet)
    
    print("[INFO] Fetching position data...")
    positions = await client.futures_position_information(symbol="BTCUSDT")
    position = positions[0]
    position_amt = float(position['positionAmt'])
    entry_price = float(position['entryPrice'])
    mark_price = float(position['markPrice'])
    unrealized_profit = float(position['unRealizedProfit'])
    
    if position_amt == 0:
        print("[INFO] Anda tidak memiliki posisi aktif di BTCUSDT saat ini.")
        await client.close_connection()
        return
        
    print(f"[INFO] Posisi Aktif: {'LONG' if position_amt > 0 else 'SHORT'} {abs(position_amt)} BTC | Entry: {entry_price} | Mark: {mark_price} | PnL: {unrealized_profit}")
    
    print("[INFO] Fetching Open Orders (SL/TP)...")
    open_orders = await client.futures_get_open_orders(symbol="BTCUSDT")
    sl_orders = []
    tp_orders = []
    for order in open_orders:
        if order['type'] == 'STOP_MARKET':
            sl_orders.append(order['stopPrice'])
        elif order['type'] in ['TAKE_PROFIT_MARKET', 'LIMIT']:
            tp_orders.append(order['price'] if order['type'] == 'LIMIT' else order['stopPrice'])
            
    print(f"[INFO] SL: {sl_orders}, TP: {tp_orders}")
    
    print("[INFO] Fetching recent market data (15m candles)...")
    klines = await client.futures_klines(symbol="BTCUSDT", interval="15m", limit=10)
    # Format: [open_time, open, high, low, close, volume, close_time, quote_asset_volume, number_of_trades, taker_buy_base_asset_volume, taker_buy_quote_asset_volume, ignore]
    market_data = []
    for k in klines:
        market_data.append({
            "open": float(k[1]),
            "high": float(k[2]),
            "low": float(k[3]),
            "close": float(k[4]),
            "volume": float(k[5])
        })
        
    await client.close_connection()
    
    print("[INFO] Asking DeepSeek for recommendation...")
    ai_client = AsyncOpenAI(api_key=deepseek_api_key, base_url="https://api.deepseek.com/v1")
    
    prompt = f"""
    Saya memiliki posisi trading aktif di Binance Futures untuk BTCUSDT.
    Tipe Posisi: {'LONG' if position_amt > 0 else 'SHORT'}
    Ukuran Posisi: {abs(position_amt)} BTC
    Harga Masuk (Entry): {entry_price}
    Harga Saat Ini (Mark Price): {mark_price}
    Keuntungan/Kerugian Belum Direalisasi (PnL): {unrealized_profit} USDT
    Stop Loss yang Dipasang: {sl_orders}
    Take Profit yang Dipasang: {tp_orders}
    
    Data 10 Candle terakhir (Timeframe 15 Menit):
    {json.dumps(market_data, indent=2)}
    
    Berdasarkan pergerakan harga historis tersebut dan level entry/SL/TP saya saat ini, berikan analisa teknikal komprehensif Anda.
    Berikan satu rekomendasi utama: Apakah saya harus HOLD posisi ini, MENGGESER SL/TP, atau CLOSE SEKARANG?
    Jelaskan alasannya secara singkat dan padat (maksimal 3 paragraf).
    """
    
    response = await ai_client.chat.completions.create(
        model="deepseek-chat",
        messages=[
            {"role": "system", "content": "Anda adalah Quant Trader elit yang memberikan saran trading yang objektif."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.3
    )
    
    print("\n--- REKOMENDASI DEEPSEEK AI ---")
    print(response.choices[0].message.content)
    print("-------------------------------")

if __name__ == "__main__":
    asyncio.run(main())
