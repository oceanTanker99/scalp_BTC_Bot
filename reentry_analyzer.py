import pandas as pd
import numpy as np
from src.backtester.engine import BacktestEngine

class ReentryAnalyzer(BacktestEngine):
    def run_analysis(self, df_1m: pd.DataFrame, df_5m: pd.DataFrame, df_15m: pd.DataFrame):
        df_1m, df_5m = self.prepare_data(df_1m, df_5m, df_15m)
        from config.config import RRR_TP1, COOLDOWN_CANDLES, TRADE_START_HOUR_UTC, TRADE_END_HOUR_UTC, BB_SQUEEZE_THRESHOLD, ADX_THRESHOLD, MIN_SIGNAL_SCORE, ATR_MULTIPLIER, RSI_OVERSOLD, RSI_OVERBOUGHT
        
        rrr_to_use = RRR_TP1
        bbl_col = [col for col in df_5m.columns if col.startswith('BBL_')][0]
        bbh_col = [col for col in df_5m.columns if col.startswith('BBU_')][0]
        adx_col = [col for col in df_5m.columns if col.startswith('ADX_')][0]

        in_position = False
        cooldown_counter = COOLDOWN_CANDLES
        
        reentry_active = False
        reentry_dir = None
        reentry_timer = 0
        reentries_done = 0
        MAX_REENTRIES = 1

        trades = []
        
        df_1m_sorted = df_1m.sort_values('timestamp').reset_index(drop=True)
        timestamps_1m = df_1m_sorted['timestamp'].values
        highs_1m = df_1m_sorted['high'].values
        lows_1m = df_1m_sorted['low'].values
        closes_1m = df_1m_sorted['close'].values

        for idx, row in df_5m.iterrows():
            if in_position: continue
            
            ts = row['timestamp']
            price = row['close']
            rsi = row['rsi']
            bbl = row[bbl_col]
            bbh = row[bbh_col]
            adx = row[adx_col]
            atr = row['atr']
            ema_200 = row['ema_200']
            
            signal = None
            is_reentry_trade = False

            # Cek Re-entry mode
            if reentry_active:
                reentry_timer -= 1
                if reentry_timer <= 0:
                    reentry_active = False
                else:
                    # Validasi ulang posisi oversold/overbought untuk Re-entry
                    bb_touch = (price <= bbl * 1.001) if reentry_dir == 'LONG' else (price >= bbh * 0.999)
                    rsi_ok = (rsi < RSI_OVERSOLD) if reentry_dir == 'LONG' else (rsi > RSI_OVERBOUGHT)
                    if bb_touch and rsi_ok:
                        signal = reentry_dir
                        is_reentry_trade = True
                        reentries_done += 1
                        reentry_active = False
            
            # Cari sinyal reguler jika tidak ada re-entry
            if not signal:
                cooldown_counter += 1
                if cooldown_counter < COOLDOWN_CANDLES: continue
                if row['hour_utc'] < TRADE_START_HOUR_UTC or row['hour_utc'] >= TRADE_END_HOUR_UTC: continue
                
                bb_width = (bbh - bbl) / price
                if bb_width < BB_SQUEEZE_THRESHOLD or adx > ADX_THRESHOLD: continue

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
                        is_reentry_trade = False
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

                for i in range(idx_1m + 1, len(timestamps_1m)):
                    h1 = highs_1m[i]
                    l1 = lows_1m[i]

                    if signal == 'LONG':
                        if l1 <= sl_price:
                            trade_result = 'LOSS'
                            break
                        if h1 >= tp_price:
                            trade_result = 'WIN'
                            break
                    else:
                        if h1 >= sl_price:
                            trade_result = 'LOSS'
                            break
                        if l1 <= tp_price:
                            trade_result = 'WIN'
                            break

                trades.append({
                    'signal': signal,
                    'result': trade_result,
                    'is_reentry': is_reentry_trade
                })

                in_position = False
                
                if trade_result == 'LOSS':
                    if is_reentry_trade:
                        reentry_active = False
                        cooldown_counter = 0
                    else:
                        reentry_active = True
                        reentry_dir = signal
                        reentry_timer = 12 # 60 menit / 1 Jam
                        reentries_done = 0
                else:
                    reentry_active = False
                    cooldown_counter = 0

        return trades

def main():
    df_1m = pd.read_csv("data/BTCUSDT_1m.csv").tail(90 * 24 * 60).copy()
    df_5m = pd.read_csv("data/BTCUSDT_5m.csv").tail(90 * 24 * 12).copy()
    df_15m = pd.read_csv("data/BTCUSDT_15m.csv").tail(90 * 24 * 4).copy()

    analyzer = ReentryAnalyzer()
    trades = analyzer.run_analysis(df_1m, df_5m, df_15m)

    total = len(trades)
    wins = len([t for t in trades if t['result'] == 'WIN'])
    losses = len([t for t in trades if t['result'] == 'LOSS'])
    
    reentry_trades = [t for t in trades if t['is_reentry']]
    re_wins = len([t for t in reentry_trades if t['result'] == 'WIN'])
    re_losses = len([t for t in reentry_trades if t['result'] == 'LOSS'])

    print("-" * 50)
    print(f"Total Trade Keseluruhan (Termasuk Re-entry): {total}")
    print(f"Total Menang: {wins}")
    print(f"Total Kalah: {losses}")
    print(f"Win Rate Keseluruhan: {(wins/total)*100:.2f}%")
    print("-" * 50)
    print(f"Khusus Trade RE-ENTRY (Tembakan Kedua):")
    print(f"Jumlah Tembakan Kedua: {len(reentry_trades)}")
    print(f"Menang: {re_wins}")
    print(f"Kalah (Mati 2x berturut-turut): {re_losses}")
    if len(reentry_trades) > 0:
        print(f"Win Rate Re-Entry: {(re_wins/len(reentry_trades))*100:.2f}%")
    print("-" * 50)
    
    start_balance = 1000.0
    bal = start_balance
    for t in trades:
        risk = bal * 0.02
        fee = (risk / 0.005) * 0.00015 * 2 
        if t['result'] == 'WIN':
            bal += (risk * 2.0) - fee
        else:
            bal -= (risk + fee)
            
    print(f"Modal Akhir (Estimasi Hyperliquid 0.015%): ${bal:,.2f}")
    print(f"Total PNL: {((bal-start_balance)/start_balance)*100:.2f}%")

if __name__ == "__main__":
    main()
