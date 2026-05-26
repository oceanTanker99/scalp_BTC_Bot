# 🚀 Scalp BTC Bot (High-Probability)

Bot trading algoritma otomatis yang dirancang **khusus** untuk melakukan *scalping* pada pasangan mata uang **BTC/USDT** di Binance Futures. Bot ini menggunakan arsitektur *event-driven* berkecepatan tinggi via Binance WebSockets dan menerapkan strategi *Mean-Reversion* tingkat mahir yang digabungkan dengan analisis *Order Flow Imbalance* (OFI).

---

## 🧠 Strategi Inti (High-Probability Hybrid)

Berbeda dengan bot *trend-following* biasa yang lambat, bot ini menggabungkan 3 lapisan analisis keamanan institusional:

1. **Macro Trend Filter (VWAP):** Bot memastikan kita tidak melawan tren pasar secara keseluruhan. Jika harga Bitcoin berada di atas VWAP (*Volume Weighted Average Price*), bot hanya akan mencari peluang *Long/Buy*.
2. **Micro Mean-Reversion Trigger (Bollinger Bands + RSI):** Bot menangkap momen "koreksi berlebihan" sesaat. Sinyal masuk terpicu jika harga menyentuh batas ekstrim Bollinger Bands (Deviasi 2) pada *timeframe* 1 menit, dengan syarat RSI menunjukkan kondisi jenuh jual/beli.
3. **L2 Orderbook Confirmation (OFI):** Sebagai senjata anti-"pisau jatuh", sebelum bot menekan tombol beli, ia memindai 5 tingkat teratas *Orderbook*. Eksekusi hanya dilakukan jika volume antrean pembeli (bids) lebih dominan dari penjual (asks).

---

## ⚙️ Persyaratan Sistem

- Python 3.12+ (jika menjalankan secara lokal)
- Docker & Docker Compose (Direkomendasikan)
- Akun Binance Futures (Testnet / Mainnet)

---

## 📦 Panduan Instalasi & Menjalankan Bot

Anda dapat menjalankan bot ini menggunakan **Docker** (paling aman & stabil) atau secara langsung di mesin lokal.

### 🔑 Langkah 1: Persiapan Konfigurasi (.env)
Buat atau edit *file* `.env` di dalam *folder* utama proyek dan isi parameter berikut:
```ini
# Binance Futures API Keys
BINANCE_API_KEY=Kunci_API_Anda
BINANCE_SECRET_KEY=Rahasia_API_Anda
BINANCE_TESTNET=true  # Ubah ke 'false' untuk Live Trading

# (Opsional) Notifikasi Telegram
TELEGRAM_BOT_TOKEN=Token_Bot_Anda
TELEGRAM_CHAT_ID=ID_Chat_Anda
```

### 🐳 Langkah 2: Menjalankan dengan Docker (Direkomendasikan)
Menjalankan bot via Docker memastikan bot Anda berjalan 24/7 di *background* tanpa terganggu oleh kendala sistem operasi.

1. Buka terminal (CMD/Powershell/Terminal).
2. Arahkan ke direktori proyek:
   ```bash
   cd scalp_BTC_Bot
   ```
3. Bangun dan jalankan *container*:
   ```bash
   docker-compose up -d --build
   ```
4. Untuk melihat *log* (catatan aktivitas bot) secara langsung:
   ```bash
   docker-compose logs -f
   ```
5. Untuk mematikan bot:
   ```bash
   docker-compose down
   ```

### 💻 Langkah 2 Alternatif: Menjalankan Secara Lokal (Tanpa Docker)
Jika Anda ingin menguji bot secara langsung untuk keperluan *debugging*:

1. Instal dependensi Python:
   ```bash
   pip install -r requirements.txt
   ```
2. Jalankan bot:
   ```bash
   python main.py
   ```

---

## 🛡️ Fitur Manajemen Risiko (Kill Switch)

Bot ini tidak akan membiarkan akun Anda hancur dalam sehari. Fitur manajemen risiko *prop-firm* telah ditanamkan:
- **Daily Max Drawdown:** Jika akun Anda mengalami kerugian lebih dari **5%** dari saldo awal harian, bot akan memicu *Kill Switch* dan berhenti beroperasi (mogok) untuk hari itu guna menghindari *revenge trading*.
- **Endpoint AlgoOrder:** Penempatan Stop-Loss dan Take-Profit sepenuhnya dikelola oleh mesin algoritma Binance API (`/fapi/v1/algoOrder`) guna menghindari kendala teknis *rate-limit* atau penolakan order bersyarat standar.
- **Risk Per Trade:** Secara bawaan, bot hanya merisikokan 1% dari margin akun pada setiap perdagangan.

---

## 📂 Struktur Proyek

- `main.py`: Titik masuk utama aplikasi yang merangkai aliran data dan logika *trading*.
- `config/config.py`: Konfigurasi terpusat (Timeframe, Leverage, Target Take-Profit).
- `src/market_stream.py`: *Event-listener* yang menangani koneksi WebSocket Binance (Klines & L2 Depth).
- `src/strategy.py`: Otak perhitungan matematika (VWAP, RSI, Bollinger Bands, OFI).
- `src/live_trader.py`: Eksekutor API untuk *Market Order* dan pemasangan Algo SL/TP.
- `Dockerfile` & `docker-compose.yml`: Lingkungan kontainer standar siap pakai.

---
*Penafian (Disclaimer): Algoritma trading ini melibatkan risiko finansial yang signifikan. Selalu lakukan pengujian di Binance Testnet sebelum mempertaruhkan uang sungguhan.*
