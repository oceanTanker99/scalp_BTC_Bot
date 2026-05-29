import pandas as pd

try:
    df = pd.read_csv('logs/backtest_trades_AI.csv')
    START_BALANCE = 1000.0
    current_balance = START_BALANCE
    SIMULATED_RISK_PCT = 0.02
    SIMULATED_RRR = 2.0  # RRR_TP1
    TAKER_FEE_RATE = 0.00015 # 0.015%

    total_fees = 0.0
    wins = 0
    losses = 0
    bes = 0

    for _, t in df.iterrows():
        res = t['result']
        sl_distance = float(t['sl_distance'])
        risk_amount = current_balance * SIMULATED_RISK_PCT
        position_size = risk_amount / sl_distance
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

    total_trades = len(df)
    total_pnl_usd = current_balance - START_BALANCE
    total_pnl_pct = (total_pnl_usd / START_BALANCE) * 100

    print(f"Hyperliquid Simulation - Fee 0.015%")
    print(f"Modal Akhir: ${current_balance:.2f}")
    print(f"Total Profit: ${total_pnl_usd:.2f} ({total_pnl_pct:.2f}%)")
    print(f"Total Potongan Fee: ${total_fees:.2f}")

except Exception as e:
    print(f"Error: {e}")
