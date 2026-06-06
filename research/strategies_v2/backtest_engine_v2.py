import pandas as pd
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))
from research.strategies_v2.smc_fvg import SMC_FVG_Engine

def run_fvg_backtest():
    # Load data
    try:
        df_5m = pd.read_csv("data/2_MONTH_AI_BACKTEST_5m.csv")
    except Exception as e:
        print(f"Error reading data: {e}")
        return

    # Sort if needed
    df_5m = df_5m.sort_values('timestamp').reset_index(drop=True)
    
    engine = SMC_FVG_Engine()
    
    trades = []
    
    print("Mengeksekusi FVG Backtest...")
    
    # Simulasi live feed per candle (Mulai dari candle ke 10)
    for i in range(10, len(df_5m)):
        window = df_5m.iloc[i-10:i+1] # 10 candle ke belakang + 1 sekarang
        
        signal, price, sl_dist, context = engine.analyze(window)
        
        if signal != "NEUTRAL":
            trades.append({
                "time": window.iloc[-1]['timestamp'],
                "signal": signal,
                "price": price,
                "sl_dist": sl_dist
            })

    print(f"Selesai! Ditemukan {len(trades)} sinyal FVG mitigation dalam 2 bulan.")
    
    longs = sum(1 for t in trades if t['signal'] == 'LONG')
    shorts = sum(1 for t in trades if t['signal'] == 'SHORT')
    print(f"LONG: {longs} | SHORT: {shorts}")

if __name__ == "__main__":
    run_fvg_backtest()
