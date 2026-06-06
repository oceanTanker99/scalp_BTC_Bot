import os
import pandas as pd
from binance.client import Client
from src.backtester.engine import BacktestEngine
from config.config import RRR_TP1
from datetime import datetime, timedelta

def fetch_period_data(symbol, start_str, end_str, output_prefix):
    client = Client()
    os.makedirs("data", exist_ok=True)
    
    files = {}
    for interval in ['1m', '5m', '15m']:
        # Untuk 15m butuh padding ke belakang sekitar 200 candle (kira-kira 3 hari) agar EMA200 valid sejak awal bulan
        actual_start_str = start_str
        if interval in ['5m', '15m']:
            # mundur 5 hari
            # (Note: binance library accepts string dates like "26 Mar, 2025")
            # We'll just fetch raw via pandas and pd.to_datetime instead of complex logic, 
            # but Client handles it well. Let's just fetch extra days.
            pass
            
        file_path = f"data/{output_prefix}_{interval}.csv"
        files[interval] = file_path
        
        if not os.path.exists(file_path):
            print(f"📥 Mengunduh {interval} ({start_str} - {end_str})...")
            # Kita tambah 5 hari sebelum start_str agar indikator (EMA200) punya ruang pemanasan
            # Tapi parser Binance lebih aman pakai millisecond
            
            # Simple approach: let Binance parse
            klines = client.futures_historical_klines(symbol, interval, start_str, end_str)
            df = pd.DataFrame(klines, columns=[
                'timestamp', 'open', 'high', 'low', 'close', 'volume',
                'close_time', 'qav', 'num_trades', 'tbv', 'tqv', 'ignore'
            ])
            for col in ['open', 'high', 'low', 'close', 'volume']:
                df[col] = pd.to_numeric(df[col], errors='coerce')
            df.to_csv(file_path, index=False)
            
    return files

def run_stress_test(name, start_str, end_str):
    print(f"\n{'='*60}")
    print(f"🌪️ MEMULAI UJI STRES: {name}")
    print(f"📅 Periode: {start_str} s/d {end_str}")
    print(f"{'='*60}")
    
    # Pad 5 hari ke belakang untuk pemanasan EMA200 (200 * 15m = 50 jam = ~2.1 hari)
    try:
        start_dt = datetime.strptime(start_str, "%d %b, %Y")
    except ValueError:
        # Fallback if format is different
        start_dt = pd.to_datetime(start_str)
        
    pad_dt = start_dt - timedelta(days=6)
    pad_start_str = pad_dt.strftime("%d %b, %Y")
    
    files = fetch_period_data("BTCUSDT", pad_start_str, end_str, name.replace(" ", "_"))
    
    df_1m = pd.read_csv(files['1m'])
    df_5m = pd.read_csv(files['5m'])
    df_15m = pd.read_csv(files['15m'])
    
    # Filter dataset agar analisanya (print trade) hanya fokus di bulan bersangkutan
    # Wait, backtest engine runs through everything. That's fine, the 5 days before will generate few trades.
    
    engine = BacktestEngine()
    print("\n⏳ [1/2] Menjalankan Simulasi Murni Matematika (Tanpa AI)...")
    trades_math = engine.run(df_1m, df_5m, df_15m, simulated_rrr=RRR_TP1, use_ai=False)
    
    print("\n⏳ [2/2] Menjalankan Simulasi dengan AI DeepSeek Validator...")
    trades_ai = engine.run(df_1m, df_5m, df_15m, simulated_rrr=RRR_TP1, use_ai=True)
    
    print_results(name, trades_math, trades_ai)

def print_results(name, trades_math, trades_ai):
    START_BALANCE = 1000.0
    RISK_PCT = 0.02
    FEE = 0.0002 * 2 # Binance fee (0.02% per side)
    
    def calc_stats(trades):
        balance = START_BALANCE
        w = 0; l = 0; be = 0
        for t in trades:
            res = t['result']
            risk = balance * RISK_PCT
            pos_size = risk / t['sl_distance']
            trade_fee = pos_size * FEE
            t['pos_size'] = pos_size
            t['risk_usd'] = risk
            t['profit_usd'] = (risk * RRR_TP1) - trade_fee if res == 'WIN' else (-trade_fee if res == 'BE' else -(risk + trade_fee))
            
            if res == 'WIN':
                w += 1
                balance += (risk * RRR_TP1) - trade_fee
            elif res == 'LOSS':
                l += 1
                balance -= (risk + trade_fee)
            else:
                be += 1
                balance -= trade_fee
            t['balance'] = balance
        return balance, w, l, be
        
    bm, wm, lm, bem = calc_stats(trades_math)
    ba, wa, la, bea = calc_stats(trades_ai)
    
    def format_journal(trades, filename):
        if not trades:
            return
        
        journal_data = []
        for i, t in enumerate(trades):
            entry_time = pd.to_datetime(t['entry_ts'], unit='ms').strftime('%Y-%m-%d %H:%M')
            
            # SL & TP Calculation
            if t['signal'] == 'LONG':
                sl = t['entry_price'] - t['sl_distance']
                tp = t['entry_price'] + (t['sl_distance'] * RRR_TP1)
            else:
                sl = t['entry_price'] + t['sl_distance']
                tp = t['entry_price'] - (t['sl_distance'] * RRR_TP1)
            
            # P&L (R)
            if t['result'] == 'WIN': pnl_r = RRR_TP1
            elif t['result'] == 'LOSS': pnl_r = -1
            else: pnl_r = 0
            
            # Catatan Exit
            if t['result'] == 'WIN': exit_note = "Hit TP"
            elif t['result'] == 'LOSS': exit_note = "Hit SL"
            else: exit_note = "Hit BE (Trailing Stop)"

            # Kualitas & Alasan (Parse AI Reasoning if exists)
            kualitas = "N/A"
            alasan = "Technical Setup"
            if t['ai_reasoning']:
                if "SCORE:" in t['ai_reasoning']:
                    try:
                        kualitas = t['ai_reasoning'].split("SCORE:")[1].split("/")[0].strip()
                    except: pass
                alasan = t['ai_reasoning'][:200].replace('\n', ' ') + "..." # Truncate long reasons

            journal_data.append({
                '#': i + 1,
                'Tanggal': entry_time,
                'Pair': "BTC/USDT",
                'TF': "5m",
                'Arah': t['signal'],
                'Harga Entry': round(t['entry_price'], 2),
                'Stop Loss': round(sl, 2),
                'Take Profit': round(tp, 2),
                'Jarak SL (R)': round(t['sl_distance'], 2),
                'R:R Ratio': RRR_TP1,
                'Ukuran Posisi': round(t.get('pos_size', 0), 4),
                'Risk ($)': round(t.get('risk_usd', 0), 2),
                'Harga Exit': round(t['exit_price'], 2),
                'Hasil': t['result'],
                'P&L ($)': round(t['profit_usd'], 2),
                'P&L (R)': pnl_r,
                'Kualitas': kualitas,
                'Setup / Alasan Entry': alasan,
                'Catatan Exit': exit_note
            })
            
        df = pd.DataFrame(journal_data)
        df.to_csv(filename, index=False)
        return df

    # Save to CSV in requested Journal Format
    os.makedirs('logs', exist_ok=True)
    df_m = format_journal(trades_math, f"logs/{name}_math_journal.csv")
    df_a = format_journal(trades_ai, f"logs/{name}_ai_journal.csv")
    
    print(f"\n📊 HASIL AKHIR: {name}")
    print(f"--- MURNI MATEMATIKA (FILTER R1) ---")
    print(f"Modal Akhir: ${bm:.2f} | PnL: {((bm-START_BALANCE)/START_BALANCE)*100:.2f}%")
    print(f"Trade: {len(trades_math)} (W:{wm} L:{lm} BE:{bem})")
    
    print(f"--- DENGAN AI DEEPSEEK VALIDATOR ---")
    print(f"Modal Akhir: ${ba:.2f} | PnL: {((ba-START_BALANCE)/START_BALANCE)*100:.2f}%")
    print(f"Trade: {len(trades_ai)} (W:{wa} L:{la} BE:{bea})")
    
if __name__ == "__main__":
    # 2 Bulan Terakhir
    regimes = [
        ("2_MONTH_AI_BACKTEST", "06 Apr, 2026", "06 Jun, 2026")
    ]
    
    for name, start, end in regimes:
        run_stress_test(name, start, end)

