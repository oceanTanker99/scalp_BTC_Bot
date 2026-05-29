import pandas as pd
import numpy as np
import json
import os
from src.backtester.engine import BacktestEngine

class LossExtractor(BacktestEngine):
    def run_analysis(self, df_1m: pd.DataFrame, df_5m: pd.DataFrame, df_15m: pd.DataFrame):
        df_1m, df_5m = self.prepare_data(df_1m, df_5m, df_15m)
        print("Menganalisis 90 hari data untuk mengekstraksi kerugian murni (Pure Losses)...")

        from config.config import RRR_TP1, COOLDOWN_CANDLES, TRADE_START_HOUR_UTC, TRADE_END_HOUR_UTC, BB_SQUEEZE_THRESHOLD, ADX_THRESHOLD, MIN_SIGNAL_SCORE, ATR_MULTIPLIER, RSI_OVERSOLD, RSI_OVERBOUGHT
        rrr_to_use = RRR_TP1
        
        bbl_col = [col for col in df_5m.columns if col.startswith('BBL_')][0]
        bbh_col = [col for col in df_5m.columns if col.startswith('BBU_')][0]
        adx_col = [col for col in df_5m.columns if col.startswith('ADX_')][0]

        in_position = False
        cooldown_counter = COOLDOWN_CANDLES
        
        pure_loss_cases = []
        
        df_1m_sorted = df_1m.sort_values('timestamp').reset_index(drop=True)
        timestamps_1m = df_1m_sorted['timestamp'].values
        highs_1m = df_1m_sorted['high'].values
        lows_1m = df_1m_sorted['low'].values

        # Gunakan logik dasar murni tanpa R1 filter, karena kita ingin melihat error logika dasar.
        # Atau bisa juga dengan R1 filter (karena R1 filter sudah ditanam di BacktestEngine.prepare_data? 
        # Tidak, R1 filter kita tanam di loop engine.py. Kita akan pakai loop yang bersih tanpa filter R1 untuk melihat kelemahan).
        for idx, row in df_5m.iterrows():
            if in_position: continue
            cooldown_counter += 1
            if cooldown_counter < COOLDOWN_CANDLES: continue
            if row['hour_utc'] < TRADE_START_HOUR_UTC or row['hour_utc'] >= TRADE_END_HOUR_UTC: continue

            price = row['close']
            rsi = row['rsi']
            bbl = row[bbl_col]
            bbh = row[bbh_col]
            adx = row[adx_col]
            atr = row['atr']
            ema_200 = row['ema_200']
            ts = row['timestamp']

            bb_width = (bbh - bbl) / price
            if bb_width < BB_SQUEEZE_THRESHOLD or adx > ADX_THRESHOLD: continue

            signal = None
            for direction in ['LONG', 'SHORT']:
                score = 0
                bb_touch = (price <= bbl * 1.001) if direction == 'LONG' else (price >= bbh * 0.999)
                rsi_ok = (rsi < RSI_OVERSOLD) if direction == 'LONG' else (rsi > RSI_OVERBOUGHT)
                macro_ok = (price > ema_200) if direction == 'LONG' else (price < ema_200)

                if not (bb_touch and rsi_ok): continue
                score += 2
                if macro_ok: score += 1
                else: continue
                
                if score >= 3: 
                    signal = direction
                    break
            
            if signal:
                entry_price = price
                sl_distance = (atr * ATR_MULTIPLIER) / entry_price

                if signal == 'LONG':
                    sl_price = entry_price * (1 - sl_distance)
                    tp_price = entry_price * (1 + (sl_distance * rrr_to_use))
                else:
                    sl_price = entry_price * (1 + sl_distance)
                    tp_price = entry_price * (1 - (sl_distance * rrr_to_use))

                in_position = True
                idx_1m = np.searchsorted(timestamps_1m, ts)

                trade_result = None
                exit_ts = 0

                for i in range(idx_1m + 1, len(timestamps_1m)):
                    h1 = highs_1m[i]
                    l1 = lows_1m[i]
                    t1 = timestamps_1m[i]

                    if signal == 'LONG':
                        if l1 <= sl_price:
                            trade_result = 'LOSS'
                            exit_ts = t1
                            break
                        if h1 >= tp_price:
                            trade_result = 'WIN'
                            exit_ts = t1
                            break
                    else:
                        if h1 >= sl_price:
                            trade_result = 'LOSS'
                            exit_ts = t1
                            break
                        if l1 <= tp_price:
                            trade_result = 'WIN'
                            exit_ts = t1
                            break

                is_pure_loss = False
                
                if trade_result == 'LOSS':
                    # Cek 2 jam ke depan, apakah dia nge-hit TP (Stop Hunt) atau benar-benar tren salah
                    end_scan = min(len(timestamps_1m), i + 120) 
                    pso = False
                    for j in range(i + 1, end_scan):
                        h2 = highs_1m[j]
                        l2 = lows_1m[j]
                        if signal == 'LONG' and h2 >= tp_price:
                            pso = True; break
                        if signal == 'SHORT' and l2 <= tp_price:
                            pso = True; break
                    
                    if not pso:
                        is_pure_loss = True
                                
                if is_pure_loss:
                    loc = df_5m.index.get_loc(idx)
                    # Ambil 10 candle sebelumnya
                    context_klines = df_5m.iloc[max(0, loc-10):loc+1][['timestamp', 'open', 'high', 'low', 'close', 'volume', 'rsi', bbl_col, bbh_col]].copy()
                    context_klines.columns = ['timestamp', 'open', 'high', 'low', 'close', 'volume', 'rsi', 'bbl', 'bbh']
                    context_klines['time_str'] = pd.to_datetime(context_klines['timestamp'], unit='ms').dt.strftime('%Y-%m-%d %H:%M:%S')
                    
                    pure_loss_cases.append({
                        'signal_time_str': pd.to_datetime(ts, unit='ms').strftime('%Y-%m-%d %H:%M:%S'),
                        'signal_direction': signal,
                        'entry_price': round(entry_price, 2),
                        'sl_price': round(sl_price, 2),
                        'tp_price': round(tp_price, 2),
                        'context_5m_candles': context_klines.to_dict(orient='records')
                    })

                in_position = False
                cooldown_counter = 0

        # Ambil 20 sampel paling baru (terbaru)
        sample_cases = pure_loss_cases[-20:]

        if not os.path.exists('logs'):
            os.makedirs('logs')
        with open('logs/pure_loss_cases.json', 'w') as f:
            json.dump(sample_cases, f, indent=4)
            
        print(f"✅ Berhasil mengekstrak total {len(pure_loss_cases)} Pure Losses.")
        print(f"✅ Menyimpan 20 kasus terbaru ke logs/pure_loss_cases.json untuk dianalisis DeepSeek.")
        return sample_cases

def main():
    data_dir = "data"
    # Memuat data 3 BULAN (90 Hari)
    df_1m = pd.read_csv(f"{data_dir}/BTCUSDT_1m.csv").tail(90 * 24 * 60).copy()
    df_5m = pd.read_csv(f"{data_dir}/BTCUSDT_5m.csv").tail(90 * 24 * 12).copy()
    df_15m = pd.read_csv(f"{data_dir}/BTCUSDT_15m.csv").tail(90 * 24 * 4).copy()

    extractor = LossExtractor()
    extractor.run_analysis(df_1m, df_5m, df_15m)

if __name__ == "__main__":
    main()
