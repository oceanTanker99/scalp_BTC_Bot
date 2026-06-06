import os
import pandas as pd
from openai import OpenAI
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config.config import DEEPSEEK_API_KEY

def analyze_via_deepseek():
    if not DEEPSEEK_API_KEY:
        print("Error: DEEPSEEK_API_KEY tidak ditemukan di config.")
        return

    df = pd.read_csv('logs/training_dataset.csv')
    
    # Konversi DataFrame ke format CSV string
    csv_string = df.to_csv(index=False)
    
    client = OpenAI(
        api_key=DEEPSEEK_API_KEY,
        base_url="https://api.deepseek.com"
    )
    
    prompt = f"""Anda adalah seorang Quant Data Scientist tingkat lanjut.
Berikut adalah dataset hasil backtest sinyal trading bot (6000+ baris) dari 4 kondisi pasar yang berbeda (Bullish, Bearish, Sideways).
Tiap baris mewakili momen di mana kondisi setup trading awal terpenuhi.
Kolom 'outcome' = 'WIN' berarti target profit (1:2 RRR) tercapai. 'LOSS' berarti Stop Loss tercapai. 'UNKNOWN' berarti tidak kena keduanya.

Misi Anda:
1. Analisis korelasi matematis mendalam antara indikator (RSI, ADX, bb_width, dist_ema200_pct, dist_ema800_pct, dmi_diff) terhadap outcome WIN vs LOSS.
2. Temukan "Sweet Spot" (parameter rentang angka yang ideal). Misal: "Hanya ambil TREND_FOLLOWING jika ADX > 45 dan bb_width > 3%" yang secara historis memiliki Win Rate > 50%.
3. Evaluasi aturan penolakan PSO (pada kolom rejection_reason: REJECT_PSO...). Apakah ada pola di mana PSO sering salah menolak sinyal WIN? Di parameter berapa PSO sebaiknya diabaikan?

Berikan laporan analitik teknis yang ringkas namun dipenuhi dengan temuan parameter threshold yang akurat. Tidak perlu basa-basi, langsung berikan panduan optimasi angkanya.

Dataset (CSV):
{csv_string}
"""
    
    print("Mengirim ~80.000 token (6.064 baris data) ke DeepSeek API (Model: deepseek-v4-pro)...")
    try:
        response = client.chat.completions.create(
            model="deepseek-v4-pro",
            messages=[
                {"role": "system", "content": "You are a quantitative data scientist."},
                {"role": "user", "content": prompt}
            ]
        )
        result = response.choices[0].message.content
        with open('logs/deepseek_ml_analysis.md', 'w', encoding='utf-8') as f:
            f.write(result)
        print("✅ Analisis selesai! Laporan disimpan di logs/deepseek_ml_analysis.md")
    except Exception as e:
        print(f"⚠️ Error dengan model deepseek-v4-pro: {e}")
        print("Mencoba fallback menggunakan model 'deepseek-chat' (v3)...")
        try:
             response = client.chat.completions.create(
                model="deepseek-chat",
                messages=[
                    {"role": "system", "content": "You are a quantitative data scientist."},
                    {"role": "user", "content": prompt}
                ]
             )
             result = response.choices[0].message.content
             with open('logs/deepseek_ml_analysis.md', 'w', encoding='utf-8') as f:
                f.write(result)
             print("✅ Analisis fallback selesai! Laporan disimpan di logs/deepseek_ml_analysis.md")
        except Exception as e2:
             print(f"❌ Fallback Error: {e2}")

if __name__ == "__main__":
    analyze_via_deepseek()
