import sys
import os
import pandas as pd
from dotenv import load_dotenv

# Tambahkan path root proyek agar import src bisa berjalan
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.backtester.engine import BacktestEngine
from src.backtester.downloader import download_klines
from config.config import RRR_TP1

def calculate_metrics(trades, start_balance=1000.0, risk_pct=0.02, rrr=RRR_TP1):
    current_balance = start_balance
    taker_fee_rate = 0.00015
    
    total_trades = len(trades)
    wins = 0
    losses = 0
    bes = 0
    total_fees = 0.0
    
    for t in trades:
        res = t['result']
        sl_distance = t['sl_distance']
        risk_amount = current_balance * risk_pct
        position_size = risk_amount / sl_distance
        trade_fee = position_size * taker_fee_rate * 2
        total_fees += trade_fee
        
        if res == 'WIN':
            wins += 1
            current_balance += (risk_amount * rrr) - trade_fee
        elif res == 'LOSS':
            losses += 1
            current_balance -= (risk_amount + trade_fee)
        elif res == 'BE':
            bes += 1
            current_balance -= trade_fee
            
    pnl_usd = current_balance - start_balance
    pnl_pct = (pnl_usd / start_balance) * 100
    win_rate = (wins / total_trades * 100) if total_trades > 0 else 0
    
    return {
        'total_trades': total_trades,
        'wins': wins,
        'losses': losses,
        'bes': bes,
        'win_rate': win_rate,
        'final_balance': current_balance,
        'pnl_usd': pnl_usd,
        'pnl_pct': pnl_pct,
        'total_fees': total_fees
    }

def main():
    load_dotenv()
    print("🚀 Memulai Advanced Backtester (Laporan 1 Bulan Terakhir)...")
    
    symbol = "BTCUSDT"
    data_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
    if not os.path.exists(data_dir):
        os.makedirs(data_dir)
        
    files = {
        '1m': os.path.join(data_dir, f"{symbol}_1m.csv"),
        '5m': os.path.join(data_dir, f"{symbol}_5m.csv"),
        '15m': os.path.join(data_dir, f"{symbol}_15m.csv")
    }
    
    for interval, path in files.items():
        if not os.path.exists(path):
            print(f"⚠️ Data {interval} tidak ditemukan. Mengunduh data 90 hari terakhir...")
            download_klines(symbol, interval, days=90, output_dir=data_dir)
            
    print("📂 Memuat data ke memory...")
    df_1m = pd.read_csv(files['1m'])
    df_5m = pd.read_csv(files['5m'])
    df_15m = pd.read_csv(files['15m'])
    
    # Ambil 30 hari terakhir
    print("✂️ Memotong data menjadi 30 hari terakhir...")
    df_1m = df_1m.tail(30 * 24 * 60).copy()
    df_5m = df_5m.tail(30 * 24 * 12).copy()
    df_15m = df_15m.tail(30 * 24 * 4).copy()

    # --- RUN 1: AI OFF, PSO ON ---
    print("\n" + "="*50)
    print("⏳ SESI 1: Menjalankan Backtest (AI OFF, PSO ON)...")
    engine_no_ai = BacktestEngine()
    trades_no_ai = engine_no_ai.run(df_1m, df_5m, df_15m, simulated_rrr=RRR_TP1, use_ai=False, use_pso=True)
    metrics_no_ai = calculate_metrics(trades_no_ai)

    # --- RUN 2: AI ON, PSO ON ---
    print("\n" + "="*50)
    print("⏳ SESI 2: Menjalankan Backtest (AI ON, PSO ON)...")
    engine_ai = BacktestEngine()
    trades_ai = engine_ai.run(df_1m, df_5m, df_15m, simulated_rrr=RRR_TP1, use_ai=True, use_pso=True)
    metrics_ai = calculate_metrics(trades_ai)
    
    # --- RUN 3: AI ON, PSO OFF ---
    print("\n" + "="*50)
    print("⏳ SESI 3: Menjalankan Backtest (AI ON, PSO OFF)...")
    engine_ai_no_pso = BacktestEngine()
    trades_ai_no_pso = engine_ai_no_pso.run(df_1m, df_5m, df_15m, simulated_rrr=RRR_TP1, use_ai=True, use_pso=False)
    metrics_ai_no_pso = calculate_metrics(trades_ai_no_pso)
    
    # --- REPORT GENERATION ---
    print("\n" + "="*50)
    print("📈 LAPORAN AKHIR BACKTEST (30 HARI TERAKHIR)")
    print("="*50)
    
    print("\n📊 PERBANDINGAN PERFORMA")
    print(f"{'Metrik':<20} | {'Mentah (No AI, +PSO)':<22} | {'Dengan AI (+PSO)':<22} | {'Dengan AI (Tanpa PSO)':<22}")
    print("-" * 92)
    print(f"{'Total Trade':<20} | {metrics_no_ai['total_trades']:<22} | {metrics_ai['total_trades']:<22} | {metrics_ai_no_pso['total_trades']:<22}")
    print(f"{'Menang (WIN)':<20} | {metrics_no_ai['wins']:<22} | {metrics_ai['wins']:<22} | {metrics_ai_no_pso['wins']:<22}")
    print(f"{'Kalah (LOSS)':<20} | {metrics_no_ai['losses']:<22} | {metrics_ai['losses']:<22} | {metrics_ai_no_pso['losses']:<22}")
    print(f"{'Impas (BE)':<20} | {metrics_no_ai['bes']:<22} | {metrics_ai['bes']:<22} | {metrics_ai_no_pso['bes']:<22}")
    print(f"{'Win Rate':<20} | {metrics_no_ai['win_rate']:.2f}%{'':<16} | {metrics_ai['win_rate']:.2f}%{'':<16} | {metrics_ai_no_pso['win_rate']:.2f}%")
    print(f"{'Total Profit (USD)':<20} | ${metrics_no_ai['pnl_usd']:.2f}{'':<14} | ${metrics_ai['pnl_usd']:.2f}{'':<14} | ${metrics_ai_no_pso['pnl_usd']:.2f}")
    print(f"{'Profit Rate (%)':<20} | {metrics_no_ai['pnl_pct']:.2f}%{'':<16} | {metrics_ai['pnl_pct']:.2f}%{'':<16} | {metrics_ai_no_pso['pnl_pct']:.2f}%")
    
    print("\n==================================================")
    print("Laporan selesai. Anda dapat menyimpan atau menganalisis hasilnya lebih lanjut.")

if __name__ == "__main__":
    main()
