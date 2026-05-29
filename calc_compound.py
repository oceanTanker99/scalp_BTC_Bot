capital = 1000.0
monthly_profit_pct = 0.20 # 20% per month based on Hyperliquid calculation

print("Bulan | Modal Awal | Profit | Modal Akhir")
print("-" * 45)
for month in range(1, 13):
    start = capital
    profit = start * monthly_profit_pct
    capital += profit
    print(f"{month:^5} | ${start:,.2f} | ${profit:,.2f} | ${capital:,.2f}")
    
print("-" * 45)
print(f"Total Pertumbuhan: {((capital - 1000) / 1000) * 100:.2f}%")
