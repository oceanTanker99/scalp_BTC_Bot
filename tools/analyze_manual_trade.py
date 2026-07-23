import asyncio
import os
import sys
from openai import AsyncOpenAI
from dotenv import load_dotenv

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
load_dotenv()

async def main():
    api_key = os.getenv("DEEPSEEK_API_KEY")
    if not api_key:
        print("API Key tidak ditemukan!")
        return
        
    client = AsyncOpenAI(
        api_key=api_key,
        base_url="https://api.deepseek.com/v1"
    )
    
    prompt = """
Seorang trader ingin membuka posisi LONG dengan parameter jaring (Limit Order) berikut:
- Entry: 62,000
- Stop Loss (SL): 60,730
- Take Profit (TP): 69,500

Tugas Anda:
1. Analisis setup ini secara matematis (hitung poin Risk, poin Reward, dan rasio Risk:Reward / RRR).
2. Berikan opini kritis sebagai Quant Trader institusional mengenai setup rasio ini (apakah 1:6 RRR terlalu ambisius untuk scalping/day-trading, apa konsekuensi win-ratenya?).
3. Jika trader menggunakan modal $1000 dan bersedia merisikokan 5% modalnya jika terkena SL, tolong hitungkan *position size* (dalam USD atau BTC) yang tepat, serta *leverage* yang aman agar terhindar dari likuidasi sebelum menyentuh SL.

Jawab dengan bahasa Indonesia yang jelas, profesional, dan berikan perhitungan angka yang konkret.
"""

    print("Meminta perhitungan rasio dan analisis dari DeepSeek-V4-Pro...")
    try:
        response = await client.chat.completions.create(
            model="deepseek-reasoner",
            messages=[
                {"role": "system", "content": "Anda adalah Quant Trader institusional dan spesialis manajemen risiko portofolio kripto."},
                {"role": "user", "content": prompt}
            ]
        )
        print("\n=== HASIL ANALISIS DEEPSEEK (REVISI ENTRY 62k) ===\n")
        print(response.choices[0].message.content)
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(main())
