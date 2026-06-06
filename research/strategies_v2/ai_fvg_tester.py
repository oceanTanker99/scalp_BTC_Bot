import pandas as pd
import sys
import os
import asyncio

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))
from research.strategies_v2.smc_fvg import SMC_FVG_Engine
from src.ai_analyzer import DeepSeekValidator

async def run_ai_fvg_test():
    try:
        df_5m = pd.read_csv("data/2_MONTH_AI_BACKTEST_5m.csv")
    except Exception as e:
        print(f"Error reading data: {e}")
        return

    df_5m = df_5m.sort_values('timestamp').reset_index(drop=True)
    engine = SMC_FVG_Engine()
    ai = DeepSeekValidator()
    
    print("Mengeksekusi AI FVG Tester (Maksimal 5 sinyal pertama)...")
    
    signals_found = 0
    for i in range(10, len(df_5m)):
        window = df_5m.iloc[:i+1] # berikan seluruh history hingga saat ini
        signal, price, sl_dist, ctx = engine.analyze(window)
        
        if signal != "NEUTRAL":
            print(f"\n--- Sinyal {signals_found + 1} ---")
            print(f"[{window.iloc[-1]['timestamp']}] Mendapat sinyal {signal} di harga {price}")
            
            # Tambahkan strategy_type ke context
            ctx['strategy_type'] = 'SMC_FVG'
            # Asumsi sentimen dummy karena tidak ada mock data (bisa netral)
            sentiment_dummy = {
                'funding_rate': 0.0,
                'top_long_short_ratio': 1.0,
                'global_long_short_ratio': 1.0,
                'open_interest': 1000000
            }
            
            is_approved, reason = await ai.validate(signal, window, 0.0, ctx, sentiment_dummy)
            print(f"Keputusan AI: {'DISETUJUI' if is_approved else 'DITOLAK'}")
            print(f"Alasan: {reason}")
            
            signals_found += 1
            if signals_found >= 5:
                break

if __name__ == "__main__":
    asyncio.run(run_ai_fvg_test())
