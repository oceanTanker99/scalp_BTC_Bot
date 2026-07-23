# 🔍 Laporan Audit Komprehensif — Scalp BTC Bot
**Tanggal:** 23 Juli 2026  
**Auditor:** Antigravity AI (Rust, Python, Crypto Order Flow, Algo Trading)  
**Cakupan:** Rust Engine, Python Trading Logic, Infrastruktur Docker, Keamanan

---

## Ringkasan Eksekutif

Proyek ini memiliki arsitektur *Dual-Layer* (Rust + Python) yang solid secara fundamental. Pemisahan *hot execution path* dari panggilan AI sudah benar dan sesuai prinsip HFT. Namun, audit menemukan **14 temuan** yang perlu ditangani sebelum memperbesar modal trading.

| Severity | Jumlah | Domain |
|----------|--------|--------|
| 🔴 CRITICAL | 2 | Python Trading, Keamanan |
| 🟠 HIGH | 4 | Python Trading, Rust Engine, Infrastruktur |
| 🟡 MEDIUM | 4 | Python, Infrastruktur |
| 🟢 LOW/INFO | 4 | Semua Domain |

---

## 🔴 CRITICAL — Harus Diperbaiki Segera

### C-1: Posisi Telanjang (*Naked Position*) Saat SL/TP Gagal Dipasang
- **File:** `src/live_trader.py` (Baris 220-304)
- **Deskripsi:** Setelah *limit order* terisi (filled), bot memasang SL dan TP secara **sekuensial**. Jika bot *crash*, jaringan terputus, atau Binance me-*rate-limit* setelah entry terisi tetapi sebelum SL/TP terpasang, posisi akan terbuka **tanpa perlindungan apa pun** dengan leverage 60x.
- **Dampak:** Kerugian tak terbatas (*unbounded loss*). Satu insiden saja bisa menghabiskan seluruh saldo.
- **Rekomendasi:**
  1. Buat *background reconciliation task* yang secara periodik (tiap 10 detik) mengecek: "Apakah ada posisi aktif tanpa SL/TP?" Jika ya, pasang segera.
  2. Simpan *state* order yang sedang diproses ke file JSON/SQLite agar saat restart, bot bisa melanjutkan pemasangan SL/TP.

### C-2: API Key AI Ter-*hardcode* di Source Code
- **File:** `config/config.py` (Baris 9)
- **Kode:** `AI_API_KEY = os.getenv("AI_API_KEY", "sk-576a2de93e8466b2-zunoj9-5d2d0166")`
- **Deskripsi:** API Key DeepSeek/9router disematkan sebagai *fallback value* di dalam kode sumber. Kode ini sudah di-*push* ke GitHub, artinya kunci ini sudah bocor secara publik.
- **Rekomendasi:**
  1. **Segera revoke/rotate** API key tersebut di dashboard penyedia AI Anda.
  2. Ubah baris menjadi: `AI_API_KEY = os.getenv("AI_API_KEY", "")`
  3. Pastikan kunci baru hanya disimpan di file `.env` (yang sudah di-*gitignore*).

---

## 🟠 HIGH — Harus Diperbaiki Sebelum Produksi Serius

### H-1: Exception Handler Menghancurkan Retry Loop GTX
- **File:** `src/live_trader.py` (Baris 237-315)
- **Deskripsi:** Order entry menggunakan `timeInForce='GTX'` (Post-Only). Jika harga bergerak dan order akan *cross the spread* (menjadi Taker), Binance menolak dengan `BinanceAPIException (-2010)`. Namun, blok `try-except` berada **di luar** loop `for attempt`, sehingga satu kali penolakan GTX langsung membatalkan seluruh mekanisme *chasing* tanpa mencoba ulang.
- **Rekomendasi:** Pindahkan `try-except BinanceAPIException` ke **dalam** loop `for attempt`.

### H-2: Kill Switch Reset Saat Restart
- **File:** `src/live_trader.py` (Baris 158-164) & `main.py` (Baris 92)
- **Deskripsi:** `start_balance` dan `is_killed` hanya disimpan di *memory*. Jika bot mengalami *drawdown* parah lalu *crash*/direstart, `start_balance` akan di-reset ke saldo yang sudah terdeplesi, sehingga batas *drawdown* 20% dihitung ulang dari titik yang sudah rendah. Ini memungkinkan kerugian tak terbatas dalam satu hari.
- **Rekomendasi:** Simpan `start_balance`, `is_killed`, dan `last_kill_switch_date` ke file JSON persisten. Saat startup, baca file ini.

### H-3: Rust `global_min_idx` / `global_max_idx` Tidak Pernah Menyusut
- **File:** `rust_engine/src/lib.rs` (Baris 70-74, 85-100)
- **Deskripsi:** Ketika tick baru masuk, `global_min_idx` dan `global_max_idx` diperluas. Namun, ketika tick lama dihapus dari VecDeque, indeks global **tidak pernah dikecilkan kembali**. Setelah beberapa jam berjalan, rentang histogram yang dipindai oleh `get_val_vah()` dan `get_chop()` akan semakin lebar meskipun tick-tick di ujung sudah tidak relevan. Ini menyebabkan:
  1. Pemindaian `for i in min_idx..=max_idx` menjadi O(N) yang semakin lambat.
  2. POC, VAH, VAL bisa tercemar oleh "hantu" volume residual dari pembulatan floating-point.
- **Rekomendasi:** Lakukan *shrink* berkala di `update_htf_cache()`: pindai dari kedua ujung histogram ke dalam untuk menemukan indeks non-nol yang sebenarnya.

### H-4: Dockerfile Single-Stage Membengkak
- **File:** `Dockerfile` (Baris 11-21)
- **Deskripsi:** Seluruh Rust toolchain (`rustup`, `cargo`, `build-essential`) tertinggal di image final. Ini meningkatkan ukuran image secara drastis (~1.5GB+) dan memperluas *attack surface*.
- **Rekomendasi:** Gunakan *multi-stage build*: kompilasi Rust di stage `builder`, salin hanya `.so` ke stage final.

---

## 🟡 MEDIUM — Sebaiknya Diperbaiki

### M-1: Minimum Order Size Memaksa Risiko Berlebih
- **File:** `src/live_trader.py` (Baris 205-206)
- **Kode:** `if qty < 0.001: qty = 0.001`
- **Deskripsi:** Jika saldo kecil atau SL distance lebar, kalkulasi risiko mungkin menghasilkan `qty < 0.001`. Memaksanya menjadi 0.001 BTC berarti bot melanggar aturan risiko 5%-nya sendiri.
- **Rekomendasi:** Tolak trade jika `qty < 0.001` alih-alih memaksakan.

### M-2: Sesi HTTP aiohttp Bocor (*Resource Leak*)
- **File:** `src/notifier.py` (Baris 34-36)
- **Deskripsi:** Saat terjadi exception, `self._session = None` tanpa memanggil `await self._session.close()` terlebih dahulu. Koneksi HTTP lama tidak ditutup, menyebabkan kebocoran memori dan soket seiring waktu.
- **Rekomendasi:** Panggil `await self._session.close()` sebelum me-reset ke `None`.

### M-3: File I/O Sinkron Memblokir Event Loop
- **File:** `src/strategy.py` (Baris 22-25)
- **Deskripsi:** `_load_params()` membaca `ai_params.json` secara sinkron setiap 3 detik. Ini memblokir asyncio event loop sesaat dan bisa menyebabkan *slippage* pada parsing WebSocket.
- **Rekomendasi:** Cek `os.path.getmtime()` sebelum membaca, atau cache parameter di memori dan hanya reload saat AI Tuner menulis.

### M-4: Log Tanpa Rotasi
- **File:** `main.py` (Baris 27)
- **Deskripsi:** Menggunakan `FileHandler` biasa. Bot HFT yang berjalan 24/7 akan menghasilkan file log yang membesar tanpa batas hingga disk penuh.
- **Rekomendasi:** Gunakan `RotatingFileHandler(maxBytes=10*1024*1024, backupCount=5)`.

---

## 🟢 LOW / INFO — Peningkatan Kualitas

### L-1: `rust_engine/target/` Tidak Ada di `.gitignore`
- **File:** `.gitignore`
- **Deskripsi:** Artefak build Rust (~ratusan MB) tidak dikecualikan dan sudah terlanjur masuk ke Git.
- **Rekomendasi:** Tambahkan `rust_engine/target/` ke `.gitignore` dan `.dockerignore`, lalu jalankan `git rm -r --cached rust_engine/target/`.

### L-2: Dependency Python Tidak Di-*pin* Ketat
- **File:** `requirements.txt`
- **Deskripsi:** Menggunakan range versi (`pandas>=2.2,<3.0`). Build tidak deterministik.
- **Rekomendasi:** Gunakan versi eksak (misal: `pandas==2.2.3`).

### L-3: Duplikasi Data di Prompt AI
- **File:** `src/ai_analyzer.py` (Baris 73-77)
- **Deskripsi:** Field `CVD` dan `Orderbook Imbalance Rata-Rata` dikirim dua kali di prompt AI. Pemborosan token.
- **Rekomendasi:** Hapus baris duplikat.

### L-4: `lookback_seconds` Parameter Diabaikan Rust
- **File:** `src/market_stream.py` (Baris 73-76) & `src/order_flow_engine.py` (Baris 85)
- **Deskripsi:** `get_metrics()` menerima parameter `lookback_seconds` (900, 3600, 14400) tetapi Rust selalu mengembalikan data 4-jam penuh. Metrik `15m` dan `1h` identik dengan `4h`.
- **Rekomendasi:** Implementasikan lookback yang berbeda di Rust, atau akui bahwa semua timeframe menggunakan profil 4-jam dan hapus parameter yang menyesatkan.

---

## ✅ Temuan Positif (Best Practices yang Sudah Diterapkan)

| Aspek | Status | Detail |
|-------|--------|--------|
| C-FFI Array Alignment | ✅ Aman | Python `ctypes.c_double * 8` cocok dengan Rust `from_raw_parts_mut(_, 8)` |
| AI Isolation | ✅ Benar | LLM call di background task terpisah, tidak memblokir hot path |
| Docker Non-Root | ✅ Aman | `botuser` digunakan dengan `no-new-privileges:true` |
| Resource Limits | ✅ Aman | CPU (1.0) dan Memory (512M) dibatasi di Compose |
| Restart Policy | ✅ Aman | `unless-stopped` mencegah bot mati permanen |
| Null Pointer Guard | ✅ Aman | Semua fungsi FFI Rust mengecek `engine.is_null()` |
| Emergency Market Close | ✅ Aman | Trilateral fallback: SL baru → SL lama → Market Close |
| WebSocket Reconnect | ✅ Aman | Auto-reconnect dengan delay 5 detik |
| Secrets via .env | ✅ Aman | `.env` di-gitignore, `.env.example` disediakan |

---

> **Prioritas Tertinggi:** Perbaiki **C-1** (Naked Position) dan **C-2** (API Key Leak) sebelum menjalankan bot dengan dana sungguhan. Kedua temuan ini berpotensi menyebabkan kerugian finansial total.

> **Catatan:** Semua temuan HIGH dan MEDIUM bisa diperbaiki secara bertahap tanpa perlu menghentikan bot yang sedang berjalan. Saya siap mengimplementasikan perbaikan mana pun yang Anda setujui.
