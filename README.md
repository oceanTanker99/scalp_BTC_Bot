# 🚀 Scalp BTC Bot (High-Probability Mean-Reversion)

Bot trading algoritma otomatis yang dirancang **khusus** untuk melakukan *scalping* pada pasangan mata uang **BTC/USDT** di Binance Futures. Bot ini menggunakan arsitektur *event-driven* berkecepatan tinggi via Binance WebSockets dan menerapkan strategi **Mean-Reversion multi-timeframe** yang digabungkan dengan validasi AI (DeepSeek).

---

## 🧠 Strategi Inti (Multi-Factor Scoring System)

Bot menggunakan sistem skor 5 poin yang menggabungkan beberapa lapisan analisis:

1. **Macro Trend Filter (EMA 200 — 15m):** Bot memastikan kita tidak melawan tren pasar makro. Jika harga di atas EMA 200 pada timeframe 15 menit, bot hanya mencari peluang *Long*, dan sebaliknya. **(Wajib — 1 poin)**
2. **Mean-Reversion Trigger (Bollinger Bands + RSI — 5m):** Bot menangkap momen "koreksi berlebihan" dengan mendeteksi harga yang menyentuh batas Bollinger Band (Deviasi 2.0) bersamaan dengan RSI yang menunjukkan kondisi jenuh (30/70). **(Wajib — 2 poin)**
3. **Volume Spike Confirmation:** Bonus skor jika volume candle saat sinyal melebihi 1.5x rata-rata volume 20 candle terakhir. **(Opsional — 1 poin)**
4. **Order Flow Imbalance (OFI):** Bonus skor berdasarkan dominasi bid/ask di 5 level teratas orderbook via WebSocket depth stream. **(Opsional — 1 poin)**
5. **AI Validator (DeepSeek):** Setelah lolos skor minimum (≥3/5), sinyal dikirim ke DeepSeek AI untuk validasi kontekstual akhir sebelum eksekusi.

### Filter Tambahan
- **ADX Filter:** Sinyal ditolak jika ADX > 30 (tren terlalu kuat untuk mean-reversion).
- **BB Squeeze Detection:** Sinyal ditolak jika BB Width < 0.2% (pasar sedang konsolidasi sempit).
- **Trading Session:** Bot hanya aktif pada jam 08:00–21:00 UTC (London + New York session).

---

## ⚙️ Persyaratan Sistem

- Python 3.12+ (jika menjalankan secara lokal)
- Docker & Docker Compose (Direkomendasikan)
- Akun Binance Futures (Testnet / Mainnet)
- API Key DeepSeek (untuk validasi AI)
- Bot Telegram + Chat ID (opsional, untuk notifikasi)

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
BINANCE_TESTNET=true  # Ubah ke 'false' untuk Live Trading

# DeepSeek AI Validator
DEEPSEEK_API_KEY=Kunci_API_DeepSeek_Anda

# (Opsional) Notifikasi Telegram
TELEGRAM_BOT_TOKEN=Token_Bot_Anda
TELEGRAM_CHAT_ID=ID_Chat_Anda
```

### 🐳 Langkah 2: Menjalankan dengan Docker (Direkomendasikan)

```bash
# Bangun dan jalankan container
docker compose up -d --build

# Lihat log secara langsung
docker compose logs -f

# Hentikan bot
docker compose down
```

### 💻 Langkah 2 Alternatif: Menjalankan Secara Lokal

```bash
# Instal dependensi
pip install -r requirements.txt

# Jalankan bot
python main.py
```

### 📊 Menjalankan Backtest

```bash
# Backtest otomatis mengunduh data jika belum ada
python run_backtest.py
```

---

## 🛡️ Fitur Manajemen Risiko

- **Kill Switch Harian:** Jika drawdown melebihi 20% dari saldo awal harian, bot berhenti trading untuk sisa hari itu. Reset otomatis setiap 00:00 UTC.
- **Chasing Limit Order:** Entry menggunakan Post-Only Limit Order dengan mekanisme *price chasing* — harga di-offset secara progresif hingga 3 percobaan agar terisi tanpa membayar taker fee.
- **Trailing Stop (Break Even):** Jika profit mencapai ≥ 0.5%, Stop Loss otomatis dipindahkan ke titik impas.
- **Cooldown Timer:** Jeda 3 candle (15 menit) antar trade untuk menghindari overtrading.
- **Risk Per Trade:** 1% dari saldo per trade dengan leverage 60x.

---

## 📂 Struktur Proyek

```
scalp_BTC_Bot/
├── main.py                    # Titik masuk utama, orkestrasi bot
├── config/
│   └── config.py              # Konfigurasi terpusat (leverage, indikator, risiko)
├── src/
│   ├── market_stream.py       # WebSocket stream (Klines 1m/5m/15m + Depth)
│   ├── strategy.py            # Mesin analisis teknikal & scoring system
│   ├── live_trader.py         # Eksekusi order & trailing stop management
│   ├── ai_analyzer.py         # Validasi sinyal via DeepSeek AI
│   ├── notifier.py            # Notifikasi Telegram
│   └── backtester/
│       ├── engine.py          # Mesin backtesting dengan simulasi 1m
│       └── downloader.py      # Pengunduh data historis Binance
├── run_backtest.py            # Script untuk menjalankan backtest
├── tools/                     # Script debug & utilitas (tidak untuk produksi)
├── Dockerfile                 # Container image
├── docker-compose.yml         # Konfigurasi Docker Compose
├── requirements.txt           # Dependensi Python
└── .env.example               # Template environment variables
```

---

*Penafian (Disclaimer): Algoritma trading ini melibatkan risiko finansial yang signifikan. Selalu lakukan pengujian di Binance Testnet sebelum mempertaruhkan uang sungguhan.*
