import pandas as pd
import pandas_ta as ta
import asyncio
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))
from research.strategies_v2.smc_fvg import SMC_FVG_Engine
from src.ai_analyzer import DeepSeekValidator

# Konfigurasi Backtest
RR_RATIO = 2.0  # Risk:Reward = 1:2
BATCH_SIZE = 10 # Request parallel ke DeepSeek

async def validate_signal(ai, s, sentiment_dummy):
    is_approved, reason = await ai.validate(s['signal'], s['window'], 0.0, s['ctx'], sentiment_dummy)
    s['ai_approved'] = is_approved
    s['ai_reason'] = reason
    return s

async def run_1mo_backtest():
    try:
        print("Memuat data 2 bulan...")
        df_5m = pd.read_csv("data/2_MONTH_AI_BACKTEST_5m.csv")
    except Exception as e:
        print(f"Error reading data: {e}")
        return

    df_5m = df_5m.sort_values('timestamp').reset_index(drop=True)
    
    # Hitung Indikator untuk Konteks AI
    print("Menghitung EMA 200 dan RSI...")
    df_5m['ema_200'] = ta.ema(df_5m['close'], length=200)
    df_5m['rsi'] = ta.rsi(df_5m['close'], length=14)
    df_5m.dropna(inplace=True)
    df_5m.reset_index(drop=True, inplace=True)
    
    # Ambil hanya 1 bulan terakhir (setengah dataset terakhir)
    one_month_len = len(df_5m) // 2
    df_5m = df_5m.iloc[-one_month_len:].reset_index(drop=True)
    
    engine = SMC_FVG_Engine()
    ai = DeepSeekValidator()
    
    print("Mencari Sinyal FVG di 1 Bulan Terakhir...")
    raw_signals = []
    
    for i in range(10, len(df_5m)):
        window = df_5m.iloc[max(0, i-30):i+1] # 30 candle ke belakang + 1 sekarang
        signal, price, sl_dist, ctx = engine.analyze(window)
        
        if signal != "NEUTRAL":
            # Siapkan context untuk AI
            ema200 = window.iloc[-1].get('ema_200', price)
            ctx['price_vs_ema200_pct'] = round(((price - ema200) / ema200) * 100, 3)
            ctx['strategy_type'] = 'SMC_FVG'
            
            raw_signals.append({
                "idx": i,
                "time": window.iloc[-1]['timestamp'],
                "signal": signal,
                "price": price,
                "sl_dist": sl_dist,
                "ctx": ctx,
                "window": window.tail(8).copy() # Cukup simpan 8 candle terakhir untuk AI
            })

    print(f"Ditemukan {len(raw_signals)} sinyal mentah. Memulai Validasi AI secara paralel...")
    
    sentiment_dummy = {
        'funding_rate': 0.0,
        'top_long_short_ratio': 1.0,
        'global_long_short_ratio': 1.0,
        'open_interest': 1000000
    }
    
    validated_signals = []
    
    # Proses dengan batching agar tidak rate-limit
    for i in range(0, len(raw_signals), BATCH_SIZE):
        batch = raw_signals[i:i+BATCH_SIZE]
        print(f"Memproses batch {i//BATCH_SIZE + 1} ({len(batch)} sinyal)...")
        tasks = [validate_signal(ai, s, sentiment_dummy) for s in batch]
        results = await asyncio.gather(*tasks)
        validated_signals.extend(results)
        await asyncio.sleep(1) # jeda untuk aman dari rate-limit
        
    # Filter yang disetujui
    approved_signals = [s for s in validated_signals if s['ai_approved']]
    print(f"\nAI menyetujui {len(approved_signals)} dari {len(raw_signals)} sinyal.")
    
    # Simulasi Trade
    print("Menjalankan Simulasi Trade (P/L)...")
    win = 0
    loss = 0
    
    for s in approved_signals:
        entry_idx = s['idx']
        entry_price = s['price']
        sl_dist = s['sl_dist']
        tp_dist = sl_dist * RR_RATIO
        
        if s['signal'] == 'LONG':
            sl_price = entry_price * (1 - sl_dist)
            tp_price = entry_price * (1 + tp_dist)
        else:
            sl_price = entry_price * (1 + sl_dist)
            tp_price = entry_price * (1 - tp_dist)
            
        # Scan harga masa depan untuk melihat SL atau TP kena duluan
        trade_result = 'OPEN'
        for j in range(entry_idx + 1, len(df_5m)):
            future_cndl = df_5m.iloc[j]
            high, low = future_cndl['high'], future_cndl['low']
            
            if s['signal'] == 'LONG':
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
                    
        if trade_result == 'WIN':
            win += 1
        elif trade_result == 'LOSS':
            loss += 1

    total_closed = win + loss
    winrate = (win / total_closed * 100) if total_closed > 0 else 0
    
    print("\n" + "="*40)
    print("HASIL BACKTEST SMC/FVG + AI (1 BULAN)")
    print("="*40)
    print(f"Total Sinyal Mentah: {len(raw_signals)}")
    print(f"Disetujui AI       : {len(approved_signals)}")
    print(f"Ditolak AI         : {len(raw_signals) - len(approved_signals)}")
    print(f"Trade Ditutup      : {total_closed} (Win: {win}, Loss: {loss})")
    print(f"Win Rate           : {winrate:.2f}%")
    print(f"Risk/Reward Ratio  : 1:{RR_RATIO}")
    print("="*40)
    
    # Save log
    pd.DataFrame([{
        "time": s['time'], "signal": s['signal'], "price": s['price'],
        "ai_reason": s['ai_reason']
    } for s in approved_signals]).to_csv("research/strategies_v2/fvg_ai_approved_1mo.csv", index=False)

if __name__ == "__main__":
    # Fix unicode printing in Windows
    sys.stdout.reconfigure(encoding='utf-8')
    asyncio.run(run_1mo_backtest())
