import os
import json
import asyncio
from openai import AsyncOpenAI
from dotenv import load_dotenv

async def main():
    load_dotenv()
    api_key = os.getenv("DEEPSEEK_API_KEY")
    if not api_key:
        print("Error: DEEPSEEK_API_KEY not found in environment.")
        return

    client = AsyncOpenAI(api_key=api_key, base_url="https://api.deepseek.com")

    try:
        with open('logs/pso_cases.json', 'r') as f:
            pso_cases = json.load(f)
    except FileNotFoundError:
        print("Error: logs/pso_cases.json not found.")
        return

    # Membatasi payload agar tidak terkena token limit (kirim 15 kasus paling representatif)
    cases_to_send = pso_cases[:15]

    print(f"Menganalisis {len(cases_to_send)} kasus PSO menggunakan DeepSeek AI Engine...")

    prompt = f"""Kamu adalah Quant Trader ahli Machine Learning dan Analisis Teknikal tingkat lanjut.
Di bawah ini adalah {len(cases_to_send)} sampel data berformat JSON berisi kasus 'Premature Stop Out' (PSO / Stop Hunt) dari strategi Scalping Bitcoin (BTCUSDT) di Timeframe 5 Menit.
Kasus-kasus ini adalah situasi di mana sebuah indikator Reversal (Bollinger Band + RSI) memicu sinyal, tetapi harga langsung menabrak Stop Loss terlebih dahulu sebelum akhirnya berbalik arah dan menyentuh Take Profit. Arah prediksi awalnya BENAR, tetapi timing masuknya TERLALU CEPAT.

Tugasmu:
1. Lakukan Pattern Recognition pada array 'context_5m_candles' (10 candle 5-menit sebelum sinyal eksekusi).
2. Temukan 3 kesamaan teknikal utama dari kasus-kasus ini. Perhatikan apakah ada anomali volume, volatilitas (lebar Bollinger Band), rentetan warna candle, atau bentuk wick (ekor) tertentu.
3. Rumuskan temuanmu menjadi satu atau dua aturan if-else logika matematis (pseudocode) yang jelas untuk menyaring sinyal di masa depan agar kita tidak masuk terlalu cepat saat badai Stop Hunt sedang terjadi.

Data Kasus (JSON):
{json.dumps(cases_to_send, indent=2)}
"""

    try:
        # Mencoba deepseek-v4-pro sesuai permintaan, dengan fallback ke deepseek-reasoner (R1)
        target_model = "deepseek-v4-pro"
        print(f"Mencoba memanggil model: {target_model} dengan reasoning medium...")
        
        try:
            response = await client.chat.completions.create(
                model=target_model,
                messages=[
                    {"role": "system", "content": "You are an elite quantitative trading AI expert."},
                    {"role": "user", "content": prompt}
                ],
                extra_body={"reasoning_effort": "medium"}
            )
        except Exception as e:
            print(f"Model {target_model} gagal (kemungkinan belum tersedia di API publik): {e}")
            print("Fallback ke model DeepSeek-Reasoner (R1)...")
            response = await client.chat.completions.create(
                model="deepseek-reasoner",
                messages=[
                    {"role": "system", "content": "You are an elite quantitative trading AI expert."},
                    {"role": "user", "content": prompt}
                ]
            )
            
        # Untuk model reasoner, kita bisa mendapatkan reasoning_content (proses berpikir)
        message = response.choices[0].message
        reasoning_thought = getattr(message, 'reasoning_content', '')
        result = message.content
        
        if not os.path.exists('logs'):
            os.makedirs('logs')
            
        with open('logs/pso_deepseek_analysis.md', 'w', encoding='utf-8') as f:
            if reasoning_thought:
                f.write("### Proses Berpikir (Reasoning):\n" + reasoning_thought + "\n\n")
            f.write("### Jawaban Akhir:\n" + result)
            
        print("\n=== HASIL ANALISIS DEEPSEEK (V4 Pro / Reasoner) ===")
        if reasoning_thought:
            print("[Reasoning Process]...")
            print(reasoning_thought[:500] + "... (dipotong)")
        print("\n[Final Result]")
        print(result)
        print("===============================\n")
        print("Analisis telah disimpan di logs/pso_deepseek_analysis.md")
        
    except Exception as e:
        print(f"Error calling API: {e}")

if __name__ == "__main__":
    asyncio.run(main())
