import pandas as pd
import pandas_ta as ta
import numpy as np
import os

def calculate_vwap(df):
    df['date'] = pd.to_datetime(df['timestamp'], unit='ms', utc=True).dt.date
    df['typical_price'] = (df['high'] + df['low'] + df['close']) / 3
    df['tp_vol'] = df['typical_price'] * df['volume']
    
    df['cum_tp_vol'] = df.groupby('date')['tp_vol'].cumsum()
    df['cum_vol'] = df.groupby('date')['volume'].cumsum()
    
    df['vwap'] = df['cum_tp_vol'] / df['cum_vol']
    return df

def run_backtest():
    print("Memuat data 2 bulan...")
    data_path = "../../data/2_MONTH_AI_BACKTEST_5m.csv"
    if not os.path.exists(data_path):
        # Fallback to local if running from project root
        data_path = "data/2_MONTH_AI_BACKTEST_5m.csv"
        
    df = pd.read_csv(data_path).sort_values('timestamp').reset_index(drop=True)
    
    print("Mengkalkulasi Indikator...")
    df = calculate_vwap(df)
    df['ema_9'] = ta.ema(df['close'], length=9)
    df['ema_21'] = ta.ema(df['close'], length=21)
    df['rsi'] = ta.rsi(df['close'], length=14)
    df['atr'] = ta.atr(df['high'], df['low'], df['close'], length=14)
    df['vol_ma'] = ta.sma(df['volume'], length=20)
    
    # Drop NAs
    df.dropna(inplace=True)
    df.reset_index(drop=True, inplace=True)
    
    in_position = False
    trade_type = None
    entry_price = 0.0
    sl_price = 0.0
    tp_price = 0.0
    
    trades = []
    
    print(f"Memindai {len(df)} candle untuk setup Pullback to VWAP...")
    
    for i in range(1, len(df)):
        current = df.iloc[i]
        prev = df.iloc[i-1]
        
        if in_position:
            # Check for SL or TP hit
            if trade_type == 'LONG':
                if current['low'] <= sl_price:
                    trades.append({'type': 'LONG', 'entry': entry_price, 'exit': sl_price, 'pnl_pct': -1.0, 'status': 'LOSS', 'time': current['timestamp']})
                    in_position = False
                elif current['high'] >= tp_price:
                    trades.append({'type': 'LONG', 'entry': entry_price, 'exit': tp_price, 'pnl_pct': 2.0, 'status': 'WIN', 'time': current['timestamp']})
                    in_position = False
            else: # SHORT
                if current['high'] >= sl_price:
                    trades.append({'type': 'SHORT', 'entry': entry_price, 'exit': sl_price, 'pnl_pct': -1.0, 'status': 'LOSS', 'time': current['timestamp']})
                    in_position = False
                elif current['low'] <= tp_price:
                    trades.append({'type': 'SHORT', 'entry': entry_price, 'exit': tp_price, 'pnl_pct': 2.0, 'status': 'WIN', 'time': current['timestamp']})
                    in_position = False
            continue
            
        # Strategy Logic (Entry Trigger)
        is_bullish_trend = current['ema_9'] > current['ema_21']
        is_bearish_trend = current['ema_9'] < current['ema_21']
        
        vol_spike = current['volume'] > current['vol_ma']
        
        # LONG: Trend bullish, pull back hits VWAP (low < vwap), but rejected and closed above VWAP
        long_setup = (
            is_bullish_trend and 
            current['low'] <= current['vwap'] and 
            current['close'] > current['vwap'] and 
            current['rsi'] < 70 and # Not overbought
            vol_spike
        )
        
        # SHORT: Trend bearish, pull back hits VWAP (high > vwap), but rejected and closed below VWAP
        short_setup = (
            is_bearish_trend and 
            current['high'] >= current['vwap'] and 
            current['close'] < current['vwap'] and 
            current['rsi'] > 30 and # Not oversold
            vol_spike
        )
        
        if long_setup:
            in_position = True
            trade_type = 'LONG'
            entry_price = current['close']
            sl_dist = current['atr'] * 1.5
            sl_price = entry_price - sl_dist
            tp_price = entry_price + (sl_dist * 2) # RR 1:2
            
        elif short_setup:
            in_position = True
            trade_type = 'SHORT'
            entry_price = current['close']
            sl_dist = current['atr'] * 1.5
            sl_price = entry_price + sl_dist
            tp_price = entry_price - (sl_dist * 2) # RR 1:2

    # Analisa Hasil
    total_trades = len(trades)
    if total_trades > 0:
        wins = len([t for t in trades if t['status'] == 'WIN'])
        losses = len([t for t in trades if t['status'] == 'LOSS'])
        win_rate = (wins / total_trades) * 100
        
        # Asumsikan risk 2% per trade, win = +4%, loss = -2%
        total_pnl_pct = (wins * 4.0) + (losses * -2.0)
        
        print("="*40)
        print("HASIL BACKTEST PULLBACK VWAP + EMA")
        print("="*40)
        print(f"Total Trade : {total_trades}")
        print(f"Wins        : {wins}")
        print(f"Losses      : {losses}")
        print(f"Win Rate    : {win_rate:.2f}%")
        print(f"Net PnL     : {total_pnl_pct:+.2f}%")
        print("="*40)
    else:
        print("Tidak ada trade yang tereksekusi.")

if __name__ == "__main__":
    run_backtest()
