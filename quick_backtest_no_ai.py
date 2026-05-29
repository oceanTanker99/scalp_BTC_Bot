import pandas as pd
from src.backtester.engine import BacktestEngine

def main():
    print("Memuat data 30 hari terakhir...")
    data_dir = "data"
    df_1m = pd.read_csv(f"{data_dir}/BTCUSDT_1m.csv").tail(30 * 24 * 60).copy()
    df_5m = pd.read_csv(f"{data_dir}/BTCUSDT_5m.csv").tail(30 * 24 * 12).copy()
    df_15m = pd.read_csv(f"{data_dir}/BTCUSDT_15m.csv").tail(30 * 24 * 4).copy()

    engine = BacktestEngine()
    # use_ai=False
    trades = engine.run(df_1m, df_5m, df_15m, simulated_rrr=2.0, use_ai=False)

    total = len(trades)
    wins = len([t for t in trades if t['result'] == 'WIN'])
    losses = len([t for t in trades if t['result'] == 'LOSS'])
    bes = len([t for t in trades if t['result'] == 'BE'])
    
    # Calculate PNL
    start_balance = 1000.0
    bal = start_balance
    total_fee = 0.0
    
    for t in trades:
        risk = bal * 0.02
        # Asumsikan sl_distance rata-rata untuk kalkulasi posisi size
        fee = (risk / t['sl_distance']) * 0.00015 * 2 
        total_fee += fee
        
        if t['result'] == 'WIN':
            bal += (risk * 2.0) - fee
        elif t['result'] == 'LOSS':
            bal -= (risk + fee)
        else: # BE
            bal -= fee

    print("\n==================================================")
    print("📈 HASIL BACKTEST (30 HARI TERAKHIR) TANPA AI + FILTER PSO R1")
    print("==================================================")
    print(f"Modal Awal       : ${start_balance:.2f}")
    print(f"Modal Akhir      : ${bal:.2f}")
    print(f"Total Profit     : ${bal - start_balance:.2f} ({((bal - start_balance) / start_balance) * 100:.2f}%)")
    print(f"Total Potongan Fee: ${total_fee:.2f}")
    print("-" * 50)
    print(f"Total Trade      : {total}")
    print(f"Menang (WIN)     : {wins} ({wins/total*100:.1f}% jika tanpa BE)")
    print(f"Kalah (LOSS)     : {losses}")
    print(f"Impas (BE)       : {bes}")
    print("==================================================")

if __name__ == "__main__":
    main()
