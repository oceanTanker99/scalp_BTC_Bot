import os
import asyncio
import json
from dotenv import load_dotenv
from binance import AsyncClient
from openai import AsyncOpenAI

async def main():
    load_dotenv()
    deepseek_api_key = os.getenv("DEEPSEEK_API_KEY")
    binance_api_key = os.getenv("BINANCE_API_KEY")
    binance_secret_key = os.getenv("BINANCE_SECRET_KEY")
    testnet = os.getenv("BINANCE_TESTNET", "true").lower() == "true"
    
    print("[INFO] Mengambil data market 15m terakhir dari Binance...")
    client = await AsyncClient.create(api_key=binance_api_key, api_secret=binance_secret_key, testnet=testnet)
    klines = await client.futures_klines(symbol="BTCUSDT", interval="15m", limit=15)
    await client.close_connection()
    
    market_data = []
    for k in klines:
        market_data.append({
            "open": float(k[1]),
            "high": float(k[2]),
            "low": float(k[3]),
            "close": float(k[4]),
            "volume": float(k[5])
        })
        
    current_price = market_data[-1]['close']
    
    ai_client = AsyncOpenAI(api_key=deepseek_api_key, base_url="https://api.deepseek.com/v1")
    
    prompt = f"""
    Saya memiliki posisi LONG BTCUSDT di Binance Futures.
    Entry: 75,938
    Harga Terkini (Real-time): {current_price}
    SL: 74,000
    TP: 80,000
    
    Data 15 Candle terakhir (Timeframe 15 Menit) dari bursa saat ini:
    {json.dumps(market_data, indent=2)}
    
    Alasan saya mengambil posisi ini:
    1. Terjadi perubahan trend besar dengan breakout di resistance sebelumnya, dan saat ini saya melihat sedang terjadi retest ke bawah.
    2. Ada area FVG (Fair Value Gap) di sekitar 75.100 - 75.400 yang saya yakini akan menjadi Order Block untuk menahan harga turun lebih jauh.
    3. Indikator Moving Average menunjukkan Golden Cross di Timeframe 4 Jam.
    
    Sebagai AI Quant Trader elit yang ahli dalam Smart Money Concepts (SMC) dan Price Action, tolong analisis struktur market real-time ini dan bandingkan dengan argumen saya.
    Apakah pergerakan harga 15 candle terakhir ini mengkonfirmasi pantulan di area FVG 75.100-75.400, atau malah menunjukkan tekanan jual yang menembusnya?
    Berikan saran tindakan konkret (Hold/Tutup/Geser SL)!
    """
    
    print("[INFO] Mengirim pertanyaan analitis beserta data riil ke DeepSeek AI...")
    response = await ai_client.chat.completions.create(
        model="deepseek-chat",
        messages=[
            {"role": "system", "content": "Anda adalah AI Quant Trader elit dan pakar Smart Money Concepts (SMC) yang kritis, objektif, dan bertindak murni berdasarkan data OHLCV riil."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.3
    )
    
    print("\n--- JAWABAN DEEPSEEK AI ---")
    answer = response.choices[0].message.content
    with open("deepseek_answer.txt", "w", encoding="utf-8") as f:
        f.write(answer)
    print("Jawaban berhasil disimpan ke deepseek_answer.txt")
    print("-----------------------------")

if __name__ == "__main__":
    asyncio.run(main())
