capital = 1000.0
ceiling = 50000.0
monthly_profit_pct = 0.20
total_withdrawn = 0.0

print("Bulan | Modal Trading | Profit Bulan Ini | Total Penarikan (Cash Out)")
print("-" * 75)

for month in range(1, 37):
    profit = capital * monthly_profit_pct
    
    if capital + profit > ceiling:
        # Jika melebihi ceiling, sisa profit ditarik
        withdraw = (capital + profit) - ceiling
        total_withdrawn += withdraw
        capital = ceiling
    else:
        # Jika belum mencapai ceiling, di-compound
        capital += profit
        withdraw = 0.0
        
    if month % 6 == 0 or capital == ceiling:
        # Print milestone tiap 6 bulan, atau saat pertama kali nyentuh ceiling
        if withdraw > 0:
            print(f"Bulan {month:<2} | ${capital:,.2f}    | +${profit:,.2f}       | ${total_withdrawn:,.2f}")
        elif month % 6 == 0:
            print(f"Bulan {month:<2} | ${capital:,.2f}    | +${profit:,.2f}       | ${total_withdrawn:,.2f}")

print("-" * 75)
print(f"Ringkasan 3 Tahun (36 Bulan):")
print(f"- Mesin Pencetak Uang (Modal Aktif) : ${capital:,.2f}")
print(f"- Total Uang Tunai yang Ditarik     : ${total_withdrawn:,.2f}")
print(f"- Total Nilai Aset (Mesin + Tunai)  : ${(capital + total_withdrawn):,.2f}")
