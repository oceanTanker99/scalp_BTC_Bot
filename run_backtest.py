import pandas as pd
import os
from src.backtester.engine import BacktestEngine
from src.backtester.downloader import download_klines
from config.config import RRR_TP1

def main():
    print("🚀 Memulai Modul Backtester...")
    
    symbol = "BTCUSDT"
    data_dir = "data"
    
    files = {
        '1m': os.path.join(data_dir, f"{symbol}_1m.csv"),
        '5m': os.path.join(data_dir, f"{symbol}_5m.csv"),
        '15m': os.path.join(data_dir, f"{symbol}_15m.csv")
    }
    
    # Cek ketersediaan data, jika belum ada otomatis download
    for interval, path in files.items():
        if not os.path.exists(path):
            print(f"⚠️ Data {interval} tidak ditemukan. Mengunduh data 270 hari terakhir...")
            download_klines(symbol, interval, days=270, output_dir=data_dir)
            
    print("📂 Memuat data ke memory...")
    df_1m = pd.read_csv(files['1m'])
    df_5m = pd.read_csv(files['5m'])
    df_15m = pd.read_csv(files['15m'])
    
    # Ambil 30 hari terakhir saja agar proses AI lebih cepat selesai
    print("✂️ Memotong data menjadi 30 hari terakhir...")
    df_1m = df_1m.tail(30 * 24 * 60).copy()
    df_5m = df_5m.tail(30 * 24 * 12).copy()
    df_15m = df_15m.tail(30 * 24 * 4).copy()
    
    engine = BacktestEngine()
    # Gunakan RRR dari config dan AKTIFKAN AI
    trades = engine.run(df_1m, df_5m, df_15m, simulated_rrr=RRR_TP1, use_ai=True)
    
    if not trades:
        print("ℹ️ Tidak ada trade yang tereksekusi selama periode ini.")
        return
        
    # --- Kalkulasi Metrik dengan Modal Awal $600 ---
    START_BALANCE = 600.0
    current_balance = START_BALANCE
    
    # Override risk pct khusus untuk simulasi ini
    SIMULATED_RISK_PCT = 0.01  # 1% per trade (STANDAR AMAN)
    SIMULATED_RRR = RRR_TP1
    TAKER_FEE_RATE = 0.0002  # 0.02% MAKER FEE (Limit Order)
    
    total_trades = len(trades)
    wins = 0
    losses = 0
    bes = 0
    total_fees = 0.0
    
    for t in trades:
        res = t['result']
        sl_distance = t['sl_distance']
        risk_amount = current_balance * SIMULATED_RISK_PCT
        
        # Kalkulasi Fee
        # Position Size (USDT) = risk_amount / sl_distance
        position_size = risk_amount / sl_distance
        # Fee dibayar 2x (saat open dan close)
        trade_fee = position_size * TAKER_FEE_RATE * 2
        total_fees += trade_fee
        
        if res == 'WIN':
            wins += 1
            current_balance += (risk_amount * SIMULATED_RRR) - trade_fee
        elif res == 'LOSS':
            losses += 1
            current_balance -= (risk_amount + trade_fee)
        elif res == 'BE':
            bes += 1
            current_balance -= trade_fee
            
    win_rate = (wins / total_trades) * 100
    total_pnl_usd = current_balance - START_BALANCE
    total_pnl_pct = (total_pnl_usd / START_BALANCE) * 100
        
    print("\n" + "="*50)
    print(f"📈 HASIL BACKTEST (30 HARI TERAKHIR) - MODAL $600 | RISIKO 1% | AI: ON | FEE 0.02%")
    print("="*50)
    print(f"Modal Awal       : ${START_BALANCE:.2f}")
    print(f"Modal Akhir      : ${current_balance:.2f}")
    print(f"Total Profit     : ${total_pnl_usd:.2f} ({total_pnl_pct:.2f}%)")
    print(f"Total Potongan Fee: ${total_fees:.2f}")
    print("-" * 50)
    print(f"Total Trade      : {total_trades}")
    print(f"Menang (WIN)     : {wins} ({win_rate:.1f}%)")
    print(f"Kalah (LOSS)     : {losses}")
    print(f"Impas (BE)       : {bes} (Trailing Stop Tersentuh)")
    print("="*50)
    
    # Save Trade Log
    trades_df = pd.DataFrame(trades)
    trades_df['entry_time'] = pd.to_datetime(trades_df['entry_ts'], unit='ms')
    trades_df['exit_time'] = pd.to_datetime(trades_df['exit_ts'], unit='ms')
    trades_df = trades_df.drop(columns=['entry_ts', 'exit_ts'])
    
    if not os.path.exists('logs'):
        os.makedirs('logs')
    trades_df.to_csv('logs/backtest_trades_AI.csv', index=False)
    print("📝 Detail riwayat trade disimpan ke logs/backtest_trades_AI.csv")

if __name__ == "__main__":
    main()
