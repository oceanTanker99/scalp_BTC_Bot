import pandas as pd
import pandas_ta as ta
import asyncio
import sys
import os
from openai import AsyncOpenAI
from config.config import DEEPSEEK_API_KEY

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))
from research.strategies_v2.smc_fvg import SMC_FVG_Engine

RR_RATIO = 2.0

async def analyze_losses_with_ai(loss_samples):
    client = AsyncOpenAI(api_key=DEEPSEEK_API_KEY, base_url="https://api.deepseek.com/v1")
    
    prompt = """Anda adalah Senior Quant Researcher ahli Smart Money Concepts.
Berikut adalah 5 contoh sinyal eksekusi FVG (Fair Value Gap) yang BERUJUNG LOSS (terkena Stop Loss).
Semua sinyal ini adalah sinyal mentah FVG.

Tugas Anda:
1. Analisis mengapa FVG ini gagal. Apakah ada kesamaan pola price action sebelum sinyal?
2. Berikan 2 ATURAN TAMBAHAN (Filter) yang harus ditambahkan ke script matematika FVG agar sinyal-sinyal buruk seperti ini bisa dihindari.

Contoh Data Sinyal (8 candle terakhir sebelum entry):
"""
    for i, s in enumerate(loss_samples):
        prompt += f"\n--- LOSS {i+1} ({s['signal']} di Harga {s['price']}) ---\n"
        prompt += s['window'].to_string() + "\n"

    print("Mengirim data Loss ke DeepSeek untuk dianalisa...")
    response = await client.chat.completions.create(
        model="deepseek-chat",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3
    )
    print("\n--- HASIL ANALISIS DEEPSEEK AI ---")
    print(response.choices[0].message.content)

def run_fvg_loss_extraction():
    df_5m = pd.read_csv("data/2_MONTH_AI_BACKTEST_5m.csv").sort_values('timestamp').reset_index(drop=True)
    df_5m['ema_200'] = ta.ema(df_5m['close'], length=200)
    df_5m.dropna(inplace=True)
    
    one_month_len = len(df_5m) // 2
    df_5m = df_5m.iloc[-one_month_len:].reset_index(drop=True)
    
    engine = SMC_FVG_Engine()
    
    loss_signals = []
    
    for i in range(10, len(df_5m)):
        window = df_5m.iloc[max(0, i-30):i+1]
        signal, price, sl_dist, ctx = engine.analyze(window)
        
        if signal != "NEUTRAL":
            tp_dist = sl_dist * RR_RATIO
            if signal == 'LONG':
                sl_price = price * (1 - sl_dist)
                tp_price = price * (1 + tp_dist)
            else:
                sl_price = price * (1 + sl_dist)
                tp_price = price * (1 - tp_dist)
                
            trade_result = 'OPEN'
            for j in range(i + 1, min(i+50, len(df_5m))): # scan 50 candle ke depan
                future_cndl = df_5m.iloc[j]
                high, low = future_cndl['high'], future_cndl['low']
                
                if signal == 'LONG':
                    if low <= sl_price:
                        trade_result = 'LOSS'
                        break
                    elif high >= tp_price:
                        trade_result = 'WIN'
                        break
                else:
                    if high >= sl_price:
                        trade_result = 'LOSS'
                        break
                    elif low <= tp_price:
                        trade_result = 'WIN'
                        break
                        
            if trade_result == 'LOSS':
                loss_signals.append({
                    "signal": signal,
                    "price": price,
                    "window": window.tail(8)[['timestamp', 'open', 'high', 'low', 'close', 'volume']].round(2).copy()
                })

    print(f"Total Loss Signals Ditemukan: {len(loss_signals)}")
    return loss_signals[:5] # Ambil 5 sampel pertama

if __name__ == "__main__":
    sys.stdout.reconfigure(encoding='utf-8')
    losses = run_fvg_loss_extraction()
    if losses:
        asyncio.run(analyze_losses_with_ai(losses))
