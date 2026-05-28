import pandas as pd
import pandas_ta as ta
import numpy as np
import sys
import os
import asyncio
from src.ai_analyzer import DeepSeekValidator

from config.config import (
    BOLLINGER_PERIOD, BOLLINGER_STD, RSI_PERIOD, RSI_OVERSOLD, RSI_OVERBOUGHT,
    TRADE_START_HOUR_UTC, TRADE_END_HOUR_UTC, ATR_PERIOD, ATR_MULTIPLIER,
    EMA_MTF_PERIOD, ADX_PERIOD, ADX_THRESHOLD, OFI_BOOST_THRESHOLD,
    VOLUME_SPIKE_MULTIPLIER, BB_SQUEEZE_THRESHOLD, MIN_SIGNAL_SCORE,
    BREAK_EVEN_TRIGGER_PCT, COOLDOWN_CANDLES, RRR_TP1
)

class BacktestEngine:
    def __init__(self):
        self.trades = []
        self.ai_validator = DeepSeekValidator()
        
    def prepare_data(self, df_1m: pd.DataFrame, df_5m: pd.DataFrame, df_15m: pd.DataFrame):
        print("⚙️ Pra-kalkulasi indikator secara vectorized (Mohon tunggu)...")
        
        # --- 15M Indicators ---
        df_15m['ema_200'] = ta.ema(df_15m['close'], length=EMA_MTF_PERIOD)
        # Bawa EMA 200 ke 5M
        df_15m_aligned = df_15m[['timestamp', 'ema_200']].copy()
        df_5m = pd.merge_asof(df_5m.sort_values('timestamp'), df_15m_aligned.sort_values('timestamp'), on='timestamp', direction='backward')
        
        # --- 5M Indicators ---
        df_5m['rsi'] = ta.rsi(df_5m['close'], length=RSI_PERIOD)
        bbands = ta.bbands(df_5m['close'], length=BOLLINGER_PERIOD, std=BOLLINGER_STD)
        df_5m = pd.concat([df_5m, bbands], axis=1)
        
        adx_df = ta.adx(df_5m['high'], df_5m['low'], df_5m['close'], length=ADX_PERIOD)
        df_5m = pd.concat([df_5m, adx_df], axis=1)
        
        df_5m['atr'] = ta.atr(df_5m['high'], df_5m['low'], df_5m['close'], length=ATR_PERIOD)
        df_5m['volume_ma'] = df_5m['volume'].rolling(window=20).mean()
        
        # VWAP Reset Harian
        df_5m['date_utc'] = pd.to_datetime(df_5m['timestamp'], unit='ms', utc=True).dt.date
        df_5m['typical_price'] = (df_5m['high'] + df_5m['low'] + df_5m['close']) / 3
        df_5m['vp'] = df_5m['typical_price'] * df_5m['volume']
        
        # Hitung VWAP
        df_5m['cum_vp'] = df_5m.groupby('date_utc')['vp'].cumsum()
        df_5m['cum_vol'] = df_5m.groupby('date_utc')['volume'].cumsum()
        df_5m['vwap'] = df_5m['cum_vp'] / df_5m['cum_vol']
        
        df_5m['hour_utc'] = pd.to_datetime(df_5m['timestamp'], unit='ms', utc=True).dt.hour
        
        # Bersihkan missing data karena periode indicator
        df_5m = df_5m.dropna(subset=['rsi', 'atr', 'ema_200']).copy()
        
        return df_1m, df_5m

    def run(self, df_1m: pd.DataFrame, df_5m: pd.DataFrame, df_15m: pd.DataFrame, simulated_rrr=None, use_ai=False):
        df_1m, df_5m = self.prepare_data(df_1m, df_5m, df_15m)
        print(f"📊 Menjalankan simulasi pada {len(df_5m)} candle 5M... (AI Filter: {'Aktif' if use_ai else 'Mati'})")
        
        rrr_to_use = simulated_rrr if simulated_rrr else RRR_TP1
        
        bbl_col = [col for col in df_5m.columns if col.startswith('BBL_')][0]
        bbh_col = [col for col in df_5m.columns if col.startswith('BBU_')][0]
        adx_col = [col for col in df_5m.columns if col.startswith('ADX_')][0]
        
        in_position = False
        cooldown_counter = COOLDOWN_CANDLES
        
        trades = []
        
        # Index dataframe 1m agar pencarian loop mikro lebih cepat
        df_1m_sorted = df_1m.sort_values('timestamp').reset_index(drop=True)
        timestamps_1m = df_1m_sorted['timestamp'].values
        highs_1m = df_1m_sorted['high'].values
        lows_1m = df_1m_sorted['low'].values
        closes_1m = df_1m_sorted['close'].values
        
        # Loop pada candle 5M
        for idx, row in df_5m.iterrows():
            if in_position:
                continue # Skip jika ada posisi
                
            cooldown_counter += 1
            if cooldown_counter < COOLDOWN_CANDLES:
                continue
                
            # Filter Jam Trading
            if row['hour_utc'] < TRADE_START_HOUR_UTC or row['hour_utc'] >= TRADE_END_HOUR_UTC:
                continue
                
            # Identifikasi Nilai
            price = row['close']
            rsi = row['rsi']
            bbl = row[bbl_col]
            bbh = row[bbh_col]
            adx = row[adx_col]
            atr = row['atr']
            ema_200 = row['ema_200']
            volume = row['volume']
            volume_ma = row['volume_ma']
            ts = row['timestamp']
            
            bb_width = (bbh - bbl) / price
            is_volume_spike = volume > (volume_ma * VOLUME_SPIKE_MULTIPLIER)
            
            # Simulasi OFI acak (karena OFI butuh tick data orderbook)
            # Kita asumsi netral (skor 0 dari OFI) untuk konservatif
            ofi_ok = False
            
            if bb_width < BB_SQUEEZE_THRESHOLD or adx > ADX_THRESHOLD:
                continue
                
            is_bullish_macro = price > ema_200
            is_bearish_macro = price < ema_200
            
            long_bb_touch = price <= bbl * 1.001
            short_bb_touch = price >= bbh * 0.999
            
            long_rsi_ok = rsi < RSI_OVERSOLD
            short_rsi_ok = rsi > RSI_OVERBOUGHT
            
            signal = None
            
            for direction in ['LONG', 'SHORT']:
                score = 0
                bb_touch = long_bb_touch if direction == 'LONG' else short_bb_touch
                rsi_ok = long_rsi_ok if direction == 'LONG' else short_rsi_ok
                macro_ok = is_bullish_macro if direction == 'LONG' else is_bearish_macro
                
                if not (bb_touch and rsi_ok):
                    continue
                score += 2
                
                if macro_ok:
                    score += 1
                else:
                    continue
                    
                if is_volume_spike:
                    score += 1
                    
                if score >= MIN_SIGNAL_SCORE:
                    signal = direction
                    break
                    
            if signal:
                if use_ai:
                    ctx = {
                        'price': price,
                        'rsi': rsi,
                        'bbl': bbl,
                        'bbh': bbh,
                        'bb_width_pct': round(bb_width * 100, 2),
                        'vwap': row['vwap'],
                        'price_vs_vwap_pct': round(((price - row['vwap']) / row['vwap']) * 100, 2),
                        'ema_200_15m': ema_200,
                        'price_vs_ema200_pct': round(((price - ema_200) / ema_200) * 100, 2),
                        'adx': adx,
                        'atr': atr,
                        'atr_pct': round((atr / price) * 100, 2),
                        'ofi': 0,
                        'volume_spike': is_volume_spike,
                        'score': score
                    }
                    print(f"⏳ [{pd.to_datetime(ts, unit='ms')}] Meminta AI memeriksa sinyal {signal}...")
                    is_approved, reasoning = asyncio.run(self.ai_validator.validate(signal, df_5m.loc[:idx], 0, ctx))
                    if not is_approved:
                        print(f"❌ DITOLAK: {reasoning}")
                        continue
                    else:
                        print(f"✅ DISETUJUI: {reasoning}")
                        ai_reasoning = reasoning
                else:
                    ai_reasoning = "AI Disabled"
                
                # Memicu Trade!
                entry_price = price
                sl_distance = (atr * ATR_MULTIPLIER) / entry_price
                
                if signal == 'LONG':
                    sl_price = entry_price * (1 - sl_distance)
                    tp_price = entry_price * (1 + (sl_distance * rrr_to_use))
                else:
                    sl_price = entry_price * (1 + sl_distance)
                    tp_price = entry_price * (1 - (sl_distance * rrr_to_use))
                    
                # Masuk ke Loop Mikro 1m untuk cek hit SL/TP
                idx_1m = np.searchsorted(timestamps_1m, ts)
                
                trade_result = None
                exit_price = 0
                exit_ts = 0
                sl_moved_to_be = False
                current_sl = sl_price
                
                for i in range(idx_1m + 1, len(timestamps_1m)):
                    h1 = highs_1m[i]
                    l1 = lows_1m[i]
                    c1 = closes_1m[i]
                    t1 = timestamps_1m[i]
                    
                    # Trailing Stop Check (End of 1m candle)
                    if signal == 'LONG':
                        pnl_pct = (c1 - entry_price) / entry_price
                    else:
                        pnl_pct = (entry_price - c1) / entry_price
                        
                    if not sl_moved_to_be and pnl_pct >= BREAK_EVEN_TRIGGER_PCT:
                        sl_moved_to_be = True
                        current_sl = entry_price
                    
                    # SL / TP Hit Check (Intra-candle via High/Low)
                    if signal == 'LONG':
                        if l1 <= current_sl:
                            trade_result = 'BE' if sl_moved_to_be and current_sl == entry_price else 'LOSS'
                            exit_price = current_sl
                            exit_ts = t1
                            break
                        if h1 >= tp_price:
                            trade_result = 'WIN'
                            exit_price = tp_price
                            exit_ts = t1
                            break
                    else:
                        if h1 >= current_sl:
                            trade_result = 'BE' if sl_moved_to_be and current_sl == entry_price else 'LOSS'
                            exit_price = current_sl
                            exit_ts = t1
                            break
                        if l1 <= tp_price:
                            trade_result = 'WIN'
                            exit_price = tp_price
                            exit_ts = t1
                            break
                            
                if trade_result:
                    trades.append({
                        'entry_ts': ts,
                        'exit_ts': exit_ts,
                        'signal': signal,
                        'entry_price': entry_price,
                        'exit_price': exit_price,
                        'sl_distance': sl_distance,
                        'result': trade_result,
                        'sl_moved_to_be': sl_moved_to_be,
                        'ai_reasoning': ai_reasoning
                    })
                
                cooldown_counter = 0 # Reset cooldown
                
        self.trades = trades
        return trades
