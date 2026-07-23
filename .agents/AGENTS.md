## Aturan Arsitektur AI untuk High-Frequency Trading (HFT)
Setiap kali merancang atau memodifikasi bot trading atau sistem *real-time* yang membutuhkan eksekusi dalam hitungan milidetik (misalnya: Order Flow, Scalping, Arbitrage):
1. **DILARANG KERAS** meletakkan pemanggilan API LLM (seperti OpenAI/DeepSeek) di dalam jalur eksekusi utama (*hot execution path*). Menunggu respons AI akan menyebabkan bot kehilangan harga *entry/exit* terbaik.
2. **SELALU** pisahkan sistem menjadi dua lapisan (Layered Architecture):
   - **Execution Layer (Lapis Eksekusi):** Mesin kuantitatif murni berbasis Python/Numpy yang berjalan secara sinkron/cepat kilat.
   - **Tuning Layer (Lapis AI):** AI berjalan secara berkala (misal: setiap jam) di *background* untuk menganalisis data makro dan mengeluarkan output berupa parameter JSON (*threshold*, bobot, deviasi) yang disuntikkan ke Lapis Eksekusi.

3. **Aturan Evaluasi Strategi (Anti-Overfitting):**
   - **DILARANG** menilai keberhasilan strategi hanya dari lonjakan PnL sesaat (Puncak Profit).
   - **SELALU** uji strategi melintasi minimal 3-6 bulan data untuk memastikan ketahanan melintasi berbagai Rezim Pasar (*Trending*, *Ranging*, *Choppy*).
   - Strategi yang mencetak PnL konsisten namun moderat (misal: kurva ekuitas mulus) JAUH LEBIH SUPERIOR dibandingkan strategi yang mencetak lonjakan ekstrim namun hancur di bulan berikutnya (*Regime Dependent*).
   - *Rolling Volume Profile* (misal: 4H) terbukti lebih tangguh (*robust*) daripada *Session Profile* murni untuk instrumen kripto 24/7.

4. **Aturan Skala HFT & Komputasi O(1):**
   - **Hindari Indikator Tradisional:** DILARANG menggunakan rumus indikator berperiode (seperti RSI, Hurst/CHOP) di skala jutaan *tick*. Skala normalisasinya (N) akan merusak nilai akhir. Gunakan indikator murni Order Flow seperti *Value Area Width* (VAW) untuk mengukur volatilitas.
   - **Wajib Caching:** DILARANG meletakkan pencarian/pemindaian array O(N) di dalam *loop* eksekusi per-*tick*. Matriks HTF (Area Nilai) harus di-*cache* dan hanya diperbarui secara periodik (misal: tiap 60 detik) untuk menjaga kecepatan kilat algoritma O(1).

5. **Penanganan API Binance & Infrastruktur:**
   - **Aturan Sinkronisasi Waktu (Timestamp):** Untuk menghindari `APIError -1021 (Ahead of server time)`, JANGAN HANYA mengurangi `serverTime - localTime`. WAJIB kurangi hasil *offset* tersebut dengan *buffer* ekstra (misal: `-1000` ms) agar *request* klien selalu aman di wilayah *recvWindow* masa lalu, tidak peduli seberapa tinggi latensi jaringan.

6. **Keamanan Eksekusi C-FFI (Python-Rust):**
   - **Aturan Sinkronisasi Memori:** Saat mengirim array via C-FFI, SELALU pastikan alokasi ukuran array di Python (`ctypes.c_double * N`) **SAMA PERSIS** dengan yang diekspektasikan dan ditulis oleh Rust. Kesalahan alokasi akan menyebabkan *Buffer Overflow* (Segfault) yang membunuh proses secara instan tanpa log *error*.
   - **Audit Ketergantungan Ekspor:** Jika memigrasikan logika variabel dari Python ke modul C/Rust, pastikan seluruh variabel hilir yang masih digunakan oleh Python (seperti VWAP, Volume, atau `current_price`) tetap dilempar kembali (diekspor) ke Python. Kegagalan mengekspor data yang esensial akan menyebabkan *silent failure* (contoh: eksekusi order tertahan karena harga dianggap 0).

7. **Kalkulasi Kuantitatif Level Tick (Volume Profile):**
   - **Bahaya Celah Kosong (The Gap Abyss):** Pada aset dengan volatilitas tinggi, pergerakan harga sering kali melompat, menyisakan celah harga dengan volume persis `0.0`. Saat membuat algoritma distribusi seperti *Value Area*, algoritma TIDAK BOLEH membandingkan (`Atas > Bawah`) jika kedua sisinya adalah `0.0`. SELALU deteksi celah kosong secara eksplisit dan rentangkan pemindaian ke kedua sisi secara bersamaan untuk mencegah indikator (seperti VAL) terjun ke nilai `0`.

8. **Deployment Docker & Perubahan Kode:**
   - **Rebuild vs Restart:** Jika memodifikasi kode sumber (seperti `.py`) di dalam proyek Docker di mana direktori sumbernya **tidak di-mount** (*bind mount*) pada `docker-compose.yml`, menggunakan perintah `docker-compose restart` TIDAK AKAN menerapkan perubahan. SELALU gunakan `docker-compose up -d --build` untuk membakar ulang kode ke dalam kontainer baru.
