import pandas as pd
import numpy as np

def run_analysis():
    print("Membaca jurnal backtest...")
    df = pd.read_csv("data/tick_backtest_journal.csv")
    
    print(f"Total trade dianalisa: {len(df)}")
    
    # Konversi waktu UNIX ke datetime jam
    df['datetime'] = pd.to_datetime(df['entry_time'], unit='s')
    df['hour'] = df['datetime'].dt.hour
    
    # Filter trade gagal (Stop Loss)
    failed_trades = df[df['reason'] == 'SL']
    successful_trades = df[df['reason'] == 'TP']
    print(f"Total kegagalan (SL): {len(failed_trades)}")
    
    if len(failed_trades) == 0:
        print("Tidak ada trade gagal ditemukan.")
        return
        
    print("\n--- ANALISA KEGAGALAN (STOP LOSS) ---")
    
    # Analisa 1: Jam dengan kegagalan tertinggi
    print("\n1. Waktu Kejadian (Jam)")
    hour_counts = failed_trades['hour'].value_counts().sort_index()
    for hour, count in hour_counts.items():
        print(f"Jam {hour:02d}:00 - {count} kegagalan")
        
    # Analisa 2: Ekstrem CVD pada saat Entry
    print("\n2. Rata-rata CVD saat Gagal vs Sukses")
    avg_cvd_fail = failed_trades['cvd'].abs().mean()
    avg_cvd_succ = successful_trades['cvd'].abs().mean()
    print(f"Rata-rata magnitudo CVD (Gagal)  : {avg_cvd_fail:.2f}")
    print(f"Rata-rata magnitudo CVD (Sukses) : {avg_cvd_succ:.2f}")
    
    # Analisa 3: Kedekatan dengan VWAP
    failed_trades['dist_to_vwap'] = ((failed_trades['entry_price'] - failed_trades['vwap']) / failed_trades['vwap']) * 100
    successful_trades['dist_to_vwap'] = ((successful_trades['entry_price'] - successful_trades['vwap']) / successful_trades['vwap']) * 100
    
    avg_dist_fail = failed_trades['dist_to_vwap'].abs().mean()
    avg_dist_succ = successful_trades['dist_to_vwap'].abs().mean()
    
    print("\n3. Rata-rata jarak harga dari VWAP (%) saat Entry")
    print(f"Gagal  : {avg_dist_fail:.4f}%")
    print(f"Sukses : {avg_dist_succ:.4f}%")
    
    # Analisa 4: Kesimpulan Otomatis
    print("\n--- KESIMPULAN ---")
    if avg_cvd_fail < avg_cvd_succ:
        print("- Sinyal gagal lebih sering terjadi saat tekanan volume (CVD) RENDAH. Indikasi: Pasar ranging/sideways menyebabkan whipsaw (SL tersentuh sebelum bergerak searah).")
    else:
        print("- Sinyal gagal terjadi saat tekanan volume (CVD) TINGGI. Indikasi: Terjadi anomali likuiditas atau fakeout kuat oleh market maker.")
        
    if avg_dist_fail > avg_dist_succ:
        print("- Harga entry trade yang gagal cenderung LEBIH JAUH dari VWAP. Indikasi: Membuka posisi di ujung tren (overextended) berisiko tinggi terkena reversion (kembali ke rata-rata).")
    else:
        print("- Jarak harga dari VWAP tidak menunjukkan perbedaan signifikan atau malah lebih dekat. Kegagalan mungkin murni noise market.")

if __name__ == "__main__":
    run_analysis()
