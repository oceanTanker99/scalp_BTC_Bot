# Aturan Trading Bot (Scalp BTC)

Dokumen ini menjelaskan aturan, filter, dan manajemen risiko yang digunakan oleh bot dalam mengeksekusi perdagangan secara otomatis. Logika ini dirancang khusus untuk strategi *High-Frequency Trading* (HFT) dan *Scalping* berbasis Order Flow.

## 1. Filter Global
Sebelum sinyal dievaluasi lebih lanjut, bot menerapkan filter berikut:
- **NY Session Kill Zone**: Bot **tidak akan** melakukan open posisi (mengabaikan sinyal) antara pukul **13:00 hingga 15:59 UTC**.
- **Jarak VWAP Dinamis**: Sinyal akan diabaikan jika jarak harga saat ini ke VWAP (Volume Weighted Average Price) kurang dari *threshold* AI. Jarak ini bisa dikalikan hingga 2x lipat jika melawan *trend* Kronos Foundation Model.

## 2. Kondisi Entry (Order Flow & Kronos Soft Filter)
Evaluasi entry menggunakan parameter dinamis yang disesuaikan oleh AI Tuning (Background Process), dengan kombinasi kondisi berikut. **Penting:** Jika arah sinyal berlawanan dengan arah prediksi makro **Kronos AI (Soft Filter)**, maka *threshold* `vwap_pct` dan `cvd_divergence_threshold` akan digandakan (2.0x) secara *real-time* untuk memperketat keamanan *entry*.

### Sinyal LONG
Sinyal LONG akan terpicu jika semua kondisi berikut terpenuhi:
1. **Oversold terhadap VWAP**: Harga berada di bawah VWAP sejauh batas toleransi AI (`vwap_pct`, default 0.1%).
2. **Undervalued (Value Area)**: Harga berada di sekitar atau di bawah **VAL (Value Area Low)** dengan toleransi pantulan 0.2% (`Harga <= VAL * 1.002`).
3. **CVD Positif**: *Cumulative Volume Delta* berada di atas ambang batas AI (`cvd_divergence_threshold`, default 5.0), menandakan Taker Buy yang dominan.
4. **Orderbook Imbalance Positif**: Rasio bid/ask imbalance lebih besar dari ambang batas AI (`imbalance_threshold`, default 0.3).

### Sinyal SHORT
Sinyal SHORT akan terpicu jika semua kondisi berikut terpenuhi:
1. **Overbought terhadap VWAP**: Harga berada di atas VWAP sejauh batas toleransi AI (`vwap_pct`, default 0.1%).
2. **Overvalued (Value Area)**: Harga berada di sekitar atau di atas **VAH (Value Area High)** dengan toleransi pantulan 0.2% (`Harga >= VAH * 0.998`).
3. **CVD Negatif**: *Cumulative Volume Delta* berada di bawah ambang batas AI (`-cvd_divergence_threshold`, default -5.0), menandakan Taker Sell yang dominan.
4. **Orderbook Imbalance Negatif**: Rasio bid/ask imbalance lebih kecil dari ambang batas AI (`-imbalance_threshold`, default -0.3).

## 3. Manajemen Risiko (Risk Management)

- **Risiko per Trade**: Bot hanya mempertaruhkan **5%** dari total saldo untuk setiap perdagangan (`TRADE_RISK_PCT = 0.05`).
- **Leverage**: Bot menggunakan leverage **60x**. Kuantitas pesanan (Qty) dihitung secara dinamis berdasarkan risiko 5% dibagi jarak Stop Loss.

## 4. Proteksi Posisi (SL & TP)

- **Jarak Stop Loss (SL)**: 
  - SL awal bersifat **dinamis**, dihitung sebesar **setengah dari jarak harga ke VWAP**.
  - Jika perhitungan jarak SL terlalu ketat, bot akan menggunakan batas SL minimum sebesar **0.5%** (`0.005`).
  - **Emergency SL**: Jika karena alasan apa pun (masalah API/Jaringan) order SL gagal terpasang, sistem rekonsiliasi (*background check* tiap 10 detik) akan mendeteksi dan secara otomatis memasang *Emergency SL* sebesar **0.5%** dari harga entry.
  
- **Jarak Take Profit (TP)**:
  - TP diatur secara otomatis menggunakan *Risk:Reward Ratio* (RRR) **1:2** (`RRR_TP1 = 2.0`). Jika jarak SL adalah 1%, maka jarak TP adalah 2%.

- **Trailing Stop (Break-Even)**:
  - Jika posisi sudah mencapai keuntungan (profit) sebesar **0.5%** (`BREAK_EVEN_TRIGGER_PCT = 0.005`), bot akan secara otomatis membatalkan SL awal dan memindahkan SL ke titik impas (harga Entry / *Break-Even*). Hal ini dilakukan untuk mengamankan modal (bebas risiko) saat tren sedang berjalan menguntungkan.
