import os
import pandas as pd
import numpy as np

from config.config import (
    RSI_PERIOD, BOLLINGER_PERIOD, BOLLINGER_STD, ATR_PERIOD, EMA_MTF_PERIOD,
    RSI_OVERSOLD, RSI_OVERBOUGHT, ADX_THRESHOLD, BB_SQUEEZE_THRESHOLD,
    MIN_SIGNAL_SCORE, COOLDOWN_CANDLES, ATR_MULTIPLIER, RRR_TP1
)
from src.backtester.engine import BacktestEngine
from research.regime_stress_test import fetch_period_data
from datetime import datetime, timedelta

def forward_simulate_trade(df_1m, entry_ts, entry_price, signal, atr, rrr):
    """Melihat ke masa depan (df_1m) untuk menentukan nasib trade."""
    sl_distance = (atr * ATR_MULTIPLIER) / entry_price
    
    if signal == 'LONG':
        sl_price = entry_price * (1 - sl_distance)
        tp_price = entry_price * (1 + (sl_distance * rrr))
    else:
        sl_price = entry_price * (1 + sl_distance)
        tp_price = entry_price * (1 - (sl_distance * rrr))
        
    # Cari index 1m terdekat setelah entry
    future_1m = df_1m[df_1m['timestamp'] > entry_ts]
    
    for _, row in future_1m.iterrows():
        high = row['high']
        low = row['low']
        
        if signal == 'LONG':
            if low <= sl_price:
                return 'LOSS'
            if high >= tp_price:
                return 'WIN'
        else:
            if high >= sl_price:
                return 'LOSS'
            if low <= tp_price:
                return 'WIN'
                
    return 'UNKNOWN' # Jika data habis sebelum SL/TP kena

def collect_data_for_period(name, start_str, end_str):
    print(f"Mengumpulkan data untuk {name}...")
    try:
        start_dt = datetime.strptime(start_str, "%d %b, %Y")
    except ValueError:
        start_dt = pd.to_datetime(start_str)
        
    pad_dt = start_dt - timedelta(days=6)
    pad_start_str = pad_dt.strftime("%d %b, %Y")
    
    files = fetch_period_data("BTCUSDT", pad_start_str, end_str, name.replace(" ", "_"))
    
    df_1m = pd.read_csv(files['1m'])
    df_5m = pd.read_csv(files['5m'])
    df_15m = pd.read_csv(files['15m'])
    
    engine = BacktestEngine()
    df_1m, df_5m = engine.prepare_data(df_1m, df_5m, df_15m)
    
    # Filter 5m ke rentang tanggal asli agar sesuai
    start_ts = int(start_dt.timestamp() * 1000)
    df_5m = df_5m[df_5m['timestamp'] >= start_ts].reset_index(drop=True)
    
    bbl_col = [col for col in df_5m.columns if col.startswith('BBL_')][0]
    bbh_col = [col for col in df_5m.columns if col.startswith('BBU_')][0]
    bbm_col = [col for col in df_5m.columns if col.startswith('BBM_')][0]
    adx_col = [col for col in df_5m.columns if col.startswith('ADX_')][0]
    dmp_col = [col for col in df_5m.columns if col.startswith('DMP_')][0]
    dmn_col = [col for col in df_5m.columns if col.startswith('DMN_')][0]
    
    dataset = []
    
    for idx, row in df_5m.iterrows():
        if idx < 10: continue # Skip awal
        
        price = row['close']
        rsi = row['rsi']
        bbl = row[bbl_col]
        bbh = row[bbh_col]
        bbm = row[bbm_col]
        adx = row[adx_col]
        dmp = row[dmp_col]
        dmn = row[dmn_col]
        atr = row['atr']
        ema_200 = row['ema_200']
        ema_800 = row['ema_800']
        volume = row['volume']
        avg_vol = row['volume_ma']
        bb_width = (bbh - bbl) / bbm
        
        # ── DUAL-ENGINE: Regime Detection ───────────────
        is_trending_bull = False
        is_trending_bear = False
        dist_ema800 = (price - ema_800) / ema_800
        
        if adx > ADX_THRESHOLD and bb_width > 0.02:
            if dist_ema800 > 0.02 and dmp > dmn + 10:
                is_trending_bull = True
            elif dist_ema800 < -0.02 and dmn > dmp + 10:
                is_trending_bear = True
                
        strategy_type = "TREND_FOLLOWING" if (is_trending_bull or is_trending_bear) else "MEAN_REVERSION"

        # Signal check
        signals_to_evaluate = []
        
        # Simulasi deteksi
        long_bb_touch = price <= bbl * 1.001
        short_bb_touch = price >= bbh * 0.999
        long_rsi_ok = rsi < RSI_OVERSOLD
        short_rsi_ok = rsi > RSI_OVERBOUGHT
        
        # Evaluasi semua potensi sinyal (sebelum difilter)
        if strategy_type == "MEAN_REVERSION" and bb_width >= BB_SQUEEZE_THRESHOLD and adx <= ADX_THRESHOLD:
            if long_bb_touch and long_rsi_ok:
                signals_to_evaluate.append('LONG')
            if short_bb_touch and short_rsi_ok:
                signals_to_evaluate.append('SHORT')
                
        elif strategy_type == "TREND_FOLLOWING":
            if is_trending_bull and (price <= bbm * 1.002 and price >= bbm * 0.998):
                signals_to_evaluate.append('LONG')
            if is_trending_bear and (price >= bbm * 0.998 and price <= bbm * 1.002):
                signals_to_evaluate.append('SHORT')

        for sig in signals_to_evaluate:
            # Cek apakah filter PSO menolaknya
            rejection_reason = "PASSED"
            
            # Helper wicks
            range_ht = row['high'] - row['low']
            upper_wick_ratio = (row['high'] - max(row['open'], row['close'])) / range_ht if range_ht > 0 else 0
            lower_wick_ratio = (min(row['open'], row['close']) - row['low']) / range_ht if range_ht > 0 else 0
            is_bullish_candle = row['close'] > row['open']
            is_bearish_candle = row['close'] < row['open']
            
            band_expanding = False
            if idx >= 1:
                prev_row = df_5m.iloc[idx - 1]
                prev_bandwidth = prev_row[bbh_col] - prev_row[bbl_col]
                band_expanding = (bbh - bbl) > (prev_bandwidth * 1.05)
                
            if strategy_type == "MEAN_REVERSION":
                if sig == 'LONG':
                    strong_bearish = (rsi < 28 and volume > avg_vol * 1.5 and is_bearish_candle and lower_wick_ratio < 0.3)
                    if strong_bearish: rejection_reason = "REJECT_PSO_STRONG_MOMENTUM"
                    elif (price < bbl) and band_expanding and (rsi < 30): rejection_reason = "REJECT_PSO_BAND_EXPAND"
                else:
                    strong_bullish = (rsi > 72 and volume > avg_vol * 1.5 and is_bullish_candle and upper_wick_ratio < 0.3)
                    if strong_bullish: rejection_reason = "REJECT_PSO_STRONG_MOMENTUM"
                    elif (price > bbh) and band_expanding and (rsi > 70): rejection_reason = "REJECT_PSO_BAND_EXPAND"
            
            # Simulasikan hasil masa depan (Forward-look)
            outcome = forward_simulate_trade(df_1m, row['timestamp'], price, sig, atr, RRR_TP1)
            
            dataset.append({
                'regime': name,
                'timestamp': pd.to_datetime(row['timestamp'], unit='ms'),
                'strategy_type': strategy_type,
                'signal': sig,
                'rsi': round(rsi, 2),
                'adx': round(adx, 2),
                'bb_width': round(bb_width * 100, 2),
                'dist_ema200_pct': round(((price - ema_200)/ema_200)*100, 2),
                'dist_ema800_pct': round(((price - ema_800)/ema_800)*100, 2),
                'dmi_diff': round(abs(dmp - dmn), 2),
                'rejection_reason': rejection_reason,
                'outcome': outcome
            })
            
    return dataset

if __name__ == "__main__":
    regimes = [
        ("BULLISH_AGRESIF_2025", "1 Apr, 2025", "30 Apr, 2025"),
        ("NEW_BULL_RALLY_2024", "1 Jan, 2024", "28 Feb, 2024"),
        ("NEW_BEAR_CRASH_2022", "1 May, 2022", "30 Jun, 2022"),
        ("NEW_SIDEWAYS_2023", "1 May, 2023", "30 Jun, 2023")
    ]
    
    all_data = []
    for name, start, end in regimes:
        data = collect_data_for_period(name, start, end)
        all_data.extend(data)
        
    df = pd.DataFrame(all_data)
    os.makedirs('logs', exist_ok=True)
    df.to_csv('logs/training_dataset.csv', index=False)
    print(f"\n✅ Selesai! {len(df)} data sinyal berhasil diekstrak dan disimpan ke logs/training_dataset.csv")
