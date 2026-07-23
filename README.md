# 🚀 Scalp BTC Bot (AI-Powered High-Probability Mean-Reversion)

Bot trading algoritma otomatis yang beroperasi **24 Jam Nonstop** dan dirancang khusus untuk melakukan *scalping* pada pasangan mata uang **BTC/USDT** di Binance Futures. Bot ini menggunakan arsitektur *event-driven* berkecepatan tinggi via Binance WebSockets dan menerapkan strategi **SMC/FVG & Mean-Reversion multi-timeframe** yang dipadukan secara langsung dengan validasi Artificial Intelligence (DeepSeek V4 Pro).

> [!CAUTION]
> **PERINGATAN RISIKO TINGGI (HIGH RISK WARNING)**
> Bot ini dikonfigurasi menggunakan **Leverage sangat agresif yaitu 60x** sesuai preferensi eksperimental. Dengan leverage sebesar ini, fluktuasi harga kurang dari 2% yang berlawanan dengan posisi Anda dapat menyebabkan likuidasi total (*Margin Call*). Selalu gunakan fitur *Stop Loss*, jangan gunakan dana utama Anda, dan jalankan di Binance Testnet terlebih dahulu sebelum menggunakan uang sungguhan!

---

## 🧠 Arsitektur Dual-Engine & Strategi Inti

Bot ini dibangun menggunakan **Dual-Layer Architecture** untuk menjamin kecepatan eksekusi tanpa mengorbankan kecerdasan buatan:
- **Execution Layer (Rust Engine):** Seluruh kalkulasi tingkat *tick* seperti *Volume Profile*, *Value Area* (VAH/VAL/POC), VWAP, dan CVD (*Cumulative Volume Delta*) dijalankan di memori Rust (O(1) kompleksitas waktu) via C-FFI. Menjamin tidak ada antrean yang tersumbat meskipun pasar sangat *volatile*.
- **Tuning Layer (Python + AI):** Lapisan atas menggunakan Python dan DeepSeek V4 Pro untuk membaca kondisi makro secara periodik tanpa memblokir jalur eksekusi utama.

Sistem skor 5 poin menggabungkan beberapa lapisan analisis:

1. **Macro Trend Filter (EMA 200 — 15m):** Bot memastikan kita tidak melawan tren pasar makro. Jika harga di atas EMA 200 pada timeframe 15 menit, bot hanya mencari peluang *Long*, dan sebaliknya. **(Wajib — 1 poin)**
2. **Mean-Reversion Trigger (Bollinger Bands + RSI — 5m):** Mendeteksi momen "koreksi berlebihan" dengan membaca harga yang menyentuh batas Bollinger Band (Deviasi 2.0) bersamaan dengan RSI yang menunjukkan kondisi jenuh (30/70). **(Wajib — 2 poin)**
3. **Volume Spike Confirmation:** Bonus skor jika volume *candle* saat sinyal melebihi 1.5x rata-rata volume 20 *candle* terakhir. **(Opsional — 1 poin)**
4. **Order Flow Imbalance (OFI):** Bonus skor berdasarkan dominasi pesanan *bid/ask* di 5 level teratas *orderbook* secara real-time via WebSocket. **(Opsional — 1 poin)**
5. **AI Validator (DeepSeek):** Setelah menembus ambang batas skor (≥3/5), sinyal diteruskan ke model AI DeepSeek untuk validasi logika terakhir. AI akan mengkaji data *market sentiment* dan mengonfirmasi atau menolak (*auto-reject*) sinyal.

### 🛡️ Filter Lingkungan Makro & Sentimen (Sentinel)
- **Economic Calendar (News Filter):** Bot otomatis menunda perdagangan (*pause*) 30 menit sebelum dan sesudah rilis berita *High Impact* makroekonomi AS (seperti CPI, NFP, atau Keputusan Suku Bunga The Fed) untuk menghindari badai volatilitas.
- **Binance Sentiment Data:** Integrasi data API sentimen pasar, termasuk *Funding Rate*, *Open Interest*, *Top Trader Long/Short Ratio*, dan *Global Long/Short Ratio* sebagai bahan evaluasi AI.
- **ADX Filter:** Sinyal ditolak jika ADX > 30 (tren terlalu kuat untuk strategi *mean-reversion* yang melawan arah sementara).
- **BB Squeeze Detection:** Sinyal otomatis ditolak jika pasar sedang konsolidasi di rentang sangat sempit (Bollinger Band Width < 0.2%).

---

## ⚙️ Persyaratan Sistem

- **Docker & Docker Compose** (Sangat Direkomendasikan untuk stabilitas dan kompatibilitas Linux/Windows).
- Akun Binance Futures (API Key & Secret Key).
- API Key DeepSeek (Wajib. Jika kosong, bot otomatis menolak eksekusi *trade*).
- Bot Telegram + Chat ID (Untuk memonitor aktivitas bot dan memberi komando).

---

## 📦 Panduan Instalasi & Menjalankan Bot

### 🔑 Langkah 1: Persiapan Konfigurasi (.env)

Salin template dan isi dengan API key Anda:
```bash
cp .env.example .env
```

Edit file `.env`:
```ini
# Binance Futures API Keys
BINANCE_API_KEY=Kunci_API_Anda
BINANCE_SECRET_KEY=Rahasia_API_Anda
BINANCE_TESTNET=true  # Ubah ke 'false' untuk menggunakan uang sungguhan

# DeepSeek AI Validator
DEEPSEEK_API_KEY=Kunci_API_DeepSeek_Anda

# Notifikasi Telegram
TELEGRAM_BOT_TOKEN=Token_Bot_Anda
TELEGRAM_CHAT_ID=ID_Chat_Anda
```

### 🐳 Langkah 2: Menjalankan dengan Docker (Direkomendasikan)

Arsitektur Docker telah diamankan sedemikian rupa dengan limitasi *resource* dan penggunaan `botuser` (non-root) untuk proteksi serangan.

```bash
# Bangun dan jalankan container
docker compose up -d --build

# Lihat log secara langsung
docker compose logs -f

# Hentikan bot
docker compose down
```

---

## 📱 Perintah Interaktif Telegram

Bot ini dilengkapi dengan *Long-Polling* interaktif via Telegram. Kirim pesan ke bot Telegram Anda dengan perintah berikut:
- `/status`  — Melihat detail posisi trading yang saat ini sedang aktif (Entry, Harga Saat ini, PnL, ROE).
- `/market`  — Melihat metrik *Order Flow* terkini (VWAP, CVD, Imbalance) dan *Volume Profile* 4-Jam (VAH, POC, VAL) dari Rust Engine.
- `/ai`      — Melihat parameter *tuning* terbaru yang disuntikkan oleh 9Router AI.
- `/balance` — Mengecek saldo dompet (*wallet balance*) Anda di Binance Futures.
- `/kill`    — **Kill Switch Manual!** Memaksa bot untuk berhenti mengeksekusi *trade* selama sisa hari itu (akan me-reset otomatis keesokan harinya di 00:00 UTC).
- `/ping`    — Memeriksa apakah *server* bot Anda masih merespons.

---

## 🛡️ Fitur Manajemen Risiko & Proteksi Darurat

- **Kill Switch Harian Automatis:** Jika *drawdown* harian menyentuh kerugian > 20% dari saldo awal di hari tersebut, bot otomatis mogok (*shutdown*) untuk mencegah terkurasnya margin lebih lanjut.
- **Trailing Stop (Break Even):** Jika posisi telah mendapatkan profit ≥ 0.5%, Stop Loss otomatis dipindahkan ke harga balik modal (*Break Even*) agar posisi dijamin tanpa kerugian.
- **Emergency Market Close:** Fitur proteksi ekstrem; apabila Binance API gagal menerima pembaruan parameter perlindungan dari *Trailing Stop* (yang membiarkan *open position* tanpa jaring pengaman), bot akan menembak order `MARKET CLOSE` secara darurat untuk menutup posisi di harga saat itu.
- **Cooldown Timer:** Pemberlakuan jeda 15 menit (3 candle) setelah transaksi selesai untuk melindungi dari perdagangan membabi-buta (*overtrading*).

---

## 📂 Struktur Proyek

```
scalp_BTC_Bot/
├── main.py                    # Titik masuk utama, orkestrator sistem
├── run_backtest.py            # Skrip untuk simulasi backtest masa lalu
├── run_parallel.py            # Skrip backtest paralel multifaktor
├── config/
│   └── config.py              # Parameter inti, pengaturan leverage 60x, dll
├── rust_engine/               # [BARU] Mesin Kalkulasi O(1) berbasis Rust
│   ├── src/lib.rs             # C-FFI memory engine untuk Volume Profile
│   └── Cargo.toml             # Konfigurasi dependensi Rust
├── src/
│   ├── market_stream.py       # Engine WebSocket Binance (OFI, Candle Live)
│   ├── strategy.py            # Engine teknikal (SMC/FVG, Scoring System)
│   ├── live_trader.py         # Eksekusi limit order & manajemen SL/TP
│   ├── ai_analyzer.py         # Penghubung DeepSeek Validator
│   ├── notifier.py            # Poller & Pengirim notifikasi Telegram
│   ├── order_flow_engine.py   # Jembatan komunikasi C-FFI Python ke Rust
│   └── backtester/            # Modul mesin simulasi
├── docs/                      # Laporan PDF dan Markdown (Audit & Analisis)
├── tools/                     # Skrip alat bantu (cancel_orders, check_balance)
├── tests/                     # Skrip pengujian komponen
├── research/                  # Skrip riset kuantitatif dan penggalian data
├── Dockerfile                 # Image konfigurasi terisolasi (Non-Root User)
├── docker-compose.yml         # Manajemen orkestrasi & Resource Limit
└── requirements.txt           # Dependensi pustaka Python
```

---

## 📚 Dokumentasi Lanjutan (Deep Dive)
Bagi para *Quant Developer* atau kontributor teknis yang ingin memahami lebih dalam tentang bagaimana bot ini menangani isu memori C-FFI, algoritma perburuan celah *Volume Profile*, dan arsitektur *High-Frequency Trading*, silakan baca selengkapnya di:
👉 **[Architecture & Technology Deep Dive](docs/Architecture_and_Technology.md)**

---

*Penafian (Disclaimer): Algoritma trading ini melibatkan risiko finansial yang ekstrim. Tidak ada garansi atas kerugian Anda. Pengembang tidak bertanggung jawab atas likuidasi saldo.*
