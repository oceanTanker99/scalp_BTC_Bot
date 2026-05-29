capital = 1000.0
monthly_profit_pct = 0.20

print("Tahun | Bulan | Modal Akhir")
print("-" * 35)
for month in range(1, 37):
    profit = capital * monthly_profit_pct
    capital += profit
    if month % 12 == 0:
        year = month // 12
        print(f"{year:^5} | {month:^5} | ${capital:,.2f}")
    
print("-" * 35)
print(f"Total Pertumbuhan: {((capital - 1000) / 1000) * 100:,.2f}%")
