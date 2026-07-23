# Architecture & Technology Deep Dive

## 1. Dual-Engine Architecture
Scalp BTC Bot menggunakan arsitektur *Dual-Engine* yang memisahkan logika kalkulasi intensif (HFT) dengan lapisan orkestrasi dan integrasi API AI.

### a. Execution Layer (Rust Engine via C-FFI)
Untuk memastikan tidak ada latensi pada level *tick* WebSocket Binance, semua pengolahan *Order Flow* (seperti Volume Profile, Value Area, VWAP, dan CVD) didelegasikan ke mesin eksekusi yang ditulis dalam Rust (`rust_engine`). 
- **Kompleksitas O(1):** Penggunaan memori blok statis dan ring buffer (`VecDeque`) menjamin penambahan dan penghapusan data *tick* dalam waktu konstan.
- **Histogram Dinamis:** Alih-alih melakukan scanning O(N) ke seluruh array harga, *engine* menggunakan rentang batas atas/bawah (`global_max_idx` & `global_min_idx`) yang dipersempit secara cerdas saat harga berubah untuk menjaga kecepatan kalkulasi Value Area (VAH/VAL/POC).
- **C-FFI Bridge:** Pustaka Rust dikompilasi menjadi *shared object* (`.so` / `.dll`) dan diakses langsung oleh Python melalui modul `ctypes`. Ini menembus keterbatasan *Global Interpreter Lock* (GIL) Python, sehingga proses kalkulasi dapat memanfaatkan kinerja multi-threading CPU.

### b. Tuning & Execution Layer (Python)
Lapis Python bertugas mengelola siklus hidup bot:
- **Asynchronous I/O:** Memanfaatkan `asyncio` dan `aiohttp` untuk mengelola stream WebSocket dari Binance dan pemanggilan API HTTP (ke Telegram dan DeepSeek) secara *non-blocking*.
- **Task Terpisah:** Orkestrasi dilakukan melalui *background tasks* (seperti `start_polling` untuk Telegram, `start_tuning_loop` untuk kalibrasi AI, dan `reconciliation_loop` untuk pengecekan keamanan order).

## 2. Artificial Intelligence Integration
Bot ini terintegrasi dengan **DeepSeek V4 Pro** (atau LLM lain yang kompatibel) sebagai *AI Validator* lapis kedua.
- **Berkala, Bukan Real-time:** Untuk menghindari latensi LLM (yang memakan waktu 2-5 detik per *request*), AI **tidak** dipanggil pada setiap *tick* atau pada saat sinyal muncul. Alih-alih, AI Tuning Task berjalan di *background* secara berkala untuk membaca data sentimen dan memberikan bobot *threshold* baru kepada strategi *execution layer*.
- **Kemandirian Execution Layer:** Jika API AI gagal, lambat, atau kehabisan kredit, Execution Layer (Python + Rust) tetap beroperasi penuh menggunakan parameter cache sebelumnya (yang sekarang dioptimalkan menggunakan fungsi sinkronisasi *mtime*).

## 3. Sistem Proteksi & Keamanan (Audit Verified)
Bot dilengkapi berbagai instrumen keamanan (berdasarkan rekomendasi *Comprehensive Audit*):
- **Naked Position Safety Net (Reconciliation):** Task latar belakang berjalan setiap 10 detik memastikan bahwa jika posisi berstatus *OPEN* tetapi Stop Loss (SL) atau Take Profit (TP) gagal terpasang karena kegagalan jaringan (API Error -1021), bot akan langsung melikuidasi paksa (*Market Close*) posisi tersebut.
- **Persistent Kill Switch:** Jika *Drawdown* harian menembus batas maksimal (20%), bot mematikan dirinya sendiri (Kill Switch). Status ini disimpan di dalam file `.json` persisten, sehingga me-restart Docker tidak akan mereset perlindungan keamanan hingga hari berganti (00:00 UTC).
- **Hardened Docker Infrastructure:**
  - *Multi-stage Build:* Mesin Rust dikompilasi dalam kontainer *builder* terpisah, meminimalisasi ukuran *image* akhir secara signifikan.
  - *Non-Root User:* *Runtime* Python berjalan menggunakan *user* `botuser` tanpa akses *root*, menetralkan risiko eksploitasi dan memberikan perlindungan sistem tingkat OS.
- **Dependency Pinning:** Semua dependensi (`aiohttp`, `python-binance`, dll) dikunci versinya di `requirements.txt` agar pembaruan tidak merusak eksekusi (*breaking changes*).

## 4. Mekanisme Order & Sinkronisasi
Bot menggunakan eksekusi `LIMIT` untuk order reguler dengan mekanisme *retry loop* (*GTX/Post Only*). Jika harga bergeser terlalu cepat, loop *retry* dengan manajemen eksepsi yang aman akan mencoba menyesuaikan harga order kembali. Bot secara otomatis menolak order yang kuantitasnya kurang dari spesifikasi minimal kuantitas dari Binance (*Notional/Min Qty*) untuk mencegah error eksekusi yang tak terduga.
