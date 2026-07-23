import multiprocessing
import os
import time
import csv
from src.backtester.tick_engine import TickBacktester

def run_month(file_path):
    print(f"Starting {file_path}...")
    tester = TickBacktester(initial_balance=100.0)
    tester.run_backtest_multi([file_path])
    
    # We will rename the output CSV so they don't overwrite each other
    month_name = os.path.basename(file_path).replace('.csv', '')
    csv_path = "data/tick_backtest_journal.csv"
    new_csv_path = f"data/journal_{month_name}.csv"
    if os.path.exists(csv_path):
        os.rename(csv_path, new_csv_path)
    
    return tester.trades

if __name__ == "__main__":
    start_time = time.time()
    
    files_to_test = [
        "data/historical_aggtrades/BTCUSDT-aggTrades-2026-01.csv",
        "data/historical_aggtrades/BTCUSDT-aggTrades-2026-02.csv",
        "data/historical_aggtrades/BTCUSDT-aggTrades-2026-03.csv",
        "data/historical_aggtrades/BTCUSDT-aggTrades-2026-04.csv",
        "data/historical_aggtrades/BTCUSDT-aggTrades-2026-05.csv",
        "data/historical_aggtrades/BTCUSDT-aggTrades-2026-06.csv"
    ]
    
    # Limit to existing files
    files_to_test = [f for f in files_to_test if os.path.exists(f)]
    
    # Use multiprocessing to run all months in parallel
    print(f"Memulai backtest paralel dengan {len(files_to_test)} CPU core...")
    
    with multiprocessing.Pool(processes=len(files_to_test)) as pool:
        all_trades_lists = pool.map(run_month, files_to_test)
        
    print("Semua proses paralel selesai. Menggabungkan jurnal...")
    
    # Merge all trades and calculate final PnL
    all_trades = []
    for trades in all_trades_lists:
        all_trades.extend(trades)
        
    # Sort chronologically
    all_trades.sort(key=lambda x: x['entry_time'])
    
    # Recalculate balance for the merged timeline
    balance = 100.0
    for trade in all_trades:
        balance += trade['pnl']
        trade['balance'] = balance
        
    # Export merged CSV
    if all_trades:
        csv_path = "data/tick_backtest_journal_merged.csv"
        keys = all_trades[0].keys()
        with open(csv_path, 'w', newline='') as f:
            dict_writer = csv.DictWriter(f, keys)
            dict_writer.writeheader()
            dict_writer.writerows(all_trades)
            
    # Calculate stats
    total_trades = len(all_trades)
    wins = len([t for t in all_trades if t['pnl'] > 0])
    losses = len([t for t in all_trades if t['pnl'] < 0])
    win_rate = (wins / total_trades * 100) if total_trades > 0 else 0
    pnl_pct = ((balance - 100.0) / 100.0) * 100
    
    end_time = time.time()
    
    print("\n========== HASIL BACKTEST TICK (PARALEL) ==========")
    print(f"Total Trade : {total_trades}")
    print(f"Win Rate    : {win_rate:.2f}% ({wins} W / {losses} L)")
    print(f"Saldo Akhir : {balance:.2f} USDT")
    print(f"Total PnL   : {pnl_pct:+.2f}%")
    print(f"Waktu Total : {end_time - start_time:.2f} detik")
    print("===================================================")
