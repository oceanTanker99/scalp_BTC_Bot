# Scalp BTC Bot: Architecture & Technology Deep Dive

Dokumen ini membedah arsitektur kuantitatif *High-Frequency Trading* (HFT) yang menggerakkan Scalp BTC Bot. Bot ini bukan sekadar skrip Python biasa, melainkan penggabungan performa tingkat rendah (*low-level*) dari bahasa pemrograman **Rust** dan fleksibilitas *machine learning* dari **Python (DeepSeek AI)**.

## 1. Dual-Layer Architecture (Pembagian Otak)

Di dunia *trading* kripto *futures*, latensi adalah musuh utama. Menjalankan indikator, merespons *tick* harga, sekaligus menunggu respons API dari AI di dalam satu putaran waktu (*thread*) yang sama akan menyebabkan bot ketinggalan momen berharga (*slippage*).

Oleh karena itu, bot ini dipecah menjadi dua sistem yang beroperasi secara independen:

### A. Execution Layer (Rust Engine)
- **Tugas**: Berjalan secara *synchronous* secepat kilat untuk menyedot jutaan *tick* data dari Binance WebSockets.
- **Karakteristik**: Lapisan ini murni kuantitatif. Sama sekali tidak ada panggilan internet ke OpenAI/DeepSeek di sini. Semuanya berfokus pada matematika murni (VWAP, CVD, Volume Profile) dan mendeteksi kondisi *Mean-Reversion*.
- **Bahasa**: Ditulis di dalam `lib.rs` (Rust) dan dikompilasi menjadi *Dynamic Library* (.dll/.so).

### B. Tuning Layer (Python + DeepSeek V4)
- **Tugas**: Berjalan di *background* secara asinkron atau periodik (berbasis interval). Lapisan ini bertugas menyerap data sentimen (*Funding Rate*, *Open Interest*) dan mengirimkannya ke AI DeepSeek.
- **Output**: Menghasilkan parameter JSON seperti penyesuaian bobot ambang batas (*threshold*) yang kemudian "disuntikkan" kembali ke *Execution Layer*.

---

## 2. Zero-Copy Latency via C-FFI (Python ↔ Rust)

Bagaimana Python bisa berkomunikasi dengan Rust tanpa lag?
Jika kita menggunakan JSON atau API REST lokal antara Python dan Rust, proses serialisasi-deserialisasi akan memakan waktu milidetik yang berharga. 

Kita menggunakan **C-FFI (Foreign Function Interface)**.
Dalam metode ini, Python menggunakan modul `ctypes` untuk **berbagi alamat memori yang sama persis** dengan Rust. 
Python mengalokasikan *array* 1 Dimensi tipe Double (`ctypes.c_double * N`), dan memberikan alamat kursor (*pointer*) tersebut ke Rust. 

Rust kemudian membakar hasil kalkulasi VWAP, CVD, dan Volume Profile langsung ke alamat memori fisik tersebut. Karena memori tersebut adalah milik Python sedari awal, Python tidak perlu melakukan sinkronisasi atau menyalin ulang *array* tersebut. Waktu pembacaan indikator murni **O(1)**.

> [!WARNING]
> **C-FFI Memory Synchronization Safety:** Kesalahan satu digit saja dalam mengalokasikan besaran *array* di Python dan apa yang diekspektasikan oleh Rust akan memicu **Buffer Overflow (Segfault)** yang membunuh proses secara instan tanpa pesan *error* apa pun.

---

## 3. Algoritma "The Gap Abyss" pada Volume Profile

Salah satu tantangan terbesar HFT di aset kripto adalah **ketiadaan pergerakan yang mulus**. Harga BTCUSDT tidak bergerak dari 60,000 ke 60,001 lalu ke 60,002. Harga bisa langsung melompat dari 60,000 ke 60,015 dalam satu *tick*, meninggalkan "celah harga" (*price gap*) dengan volume transaksi absolut `0.0`.

Pada algoritma standar perhitungan *Value Area High* (VAH) dan *Value Area Low* (VAL) di Volume Profile, algoritma akan membandingkan volume di atas POC (*Point of Control*) dan di bawah POC.
- *Jika Volume Atas > Volume Bawah, masukkan Atas ke rentang.*
- *Jika Volume Bawah > Volume Atas, masukkan Bawah ke rentang.*

**Bencana The Gap Abyss:**
Jika sisi atas dan sisi bawah sama-sama kosong (`0.0`), algoritma yang bodoh akan terjebak, memilih salah satu arah ke dalam kehampaan hingga indeksnya mencapai angka `0` (menyebabkan indikator VAL terjun payung ke harga yang tidak masuk akal).

**Solusi Algoritmik di Rust:**
Mesin Rust ini dirancang mendeteksi celah kosong. Jika indeks `up_vol` dan `down_vol` sama dengan `0.0`, mesin akan memicu protokol jembatan (*bridging*) dengan merentangkan indeks secara simetris ke atas dan ke bawah sekaligus hingga ia "menemukan" bongkahan volume di kedua sisi tebing. Ini menjaga integritas kurva distribusi normal.

---

## 4. Sinkronisasi Waktu Ekstrem (Manajemen RecvWindow)

Kesalahan klasik bot *trading* adalah terkena **APIError -1021 (Timestamp for this request is outside of the recvWindow)**. Hal ini terjadi karena latensi jaringan (*ping*) antara server *cloud* Anda dan server Binance.

Bot ini tidak menggunakan waktu sistem lokal (jam OS) secara mentah. Bot ini melakukan penyesuaian (*offset*):
```python
offset = server_time - local_time - 1000  # Buffer agresif
```
Pengurangan `1000` milidetik (1 detik) tambahan memastikan bahwa *request payload* dari bot kita dikirim "seolah-olah" berasal dari masa lalu yang aman, sehingga selalu mendarat tepat dalam jendela penerimaan (*recvWindow*) 5000ms milik Binance, tidak peduli seberapa padatnya lalu lintas internet saat itu.

---
*Dokumentasi ini adalah gambaran fundamental. Kode implementasi teknis dapat dilihat di direktori `rust_engine/` dan skrip `order_flow_engine.py`.*
