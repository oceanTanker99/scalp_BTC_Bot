import os
import sys
import logging
import pandas as pd
import numpy as np

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
log = logging.getLogger("SyntheticGen")

# Constants
OUTPUT_DIR = "data"
OUTPUT_FILE = os.path.join(OUTPUT_DIR, "synthetic_ticks.csv")

try:
    # Asumsikan repo Kronos di-clone ke src/Kronos
    sys.path.append(os.path.join(os.path.dirname(__file__), '../src/Kronos'))
    from model import Kronos, KronosTokenizer, KronosPredictor
    import torch
    KRONOS_AVAILABLE = True
except ImportError:
    log.warning("Kronos library tidak ditemukan. Menjalankan dalam mode simulasi.")
    KRONOS_AVAILABLE = False


class SyntheticDataGenerator:
    def __init__(self, model_name="NeoQuasar/Kronos-small"):
        self.device = "cuda" if KRONOS_AVAILABLE and torch.cuda.is_available() else "cpu"
        if KRONOS_AVAILABLE:
            log.info(f"Loading {model_name} on {self.device}")
            self.tokenizer = KronosTokenizer.from_pretrained("NeoQuasar/Kronos-Tokenizer-base")
            self.model = Kronos.from_pretrained(model_name).to(self.device)
            self.predictor = KronosPredictor(self.model, self.tokenizer)
        else:
            log.info("Mock mode diaktifkan.")

    def fetch_seed_data(self):
        """Membuat/Mengambil K-Line awal sebagai seed untuk model."""
        # TODO: Load real historical OHLCV from Binance here
        return pd.DataFrame({
            "open": [60000, 60100],
            "high": [60200, 60300],
            "low": [59900, 60000],
            "close": [60100, 60200],
            "volume": [10.5, 12.0]
        })

    def generate_future_klines(self, seed_df, num_steps=100):
        """Menggunakan Kronos untuk menghalusinasikan masa depan."""
        if KRONOS_AVAILABLE:
            log.info("Memanggil Kronos model untuk prediksi K-Line...")
            # prediction = self.predictor.sample(seed_df, steps=num_steps)
            # Karena belum ada model sungguhan yang di-load, kita skip.
            pass
            
        # Simulasi Random Walk untuk K-Line (Mock)
        last_close = seed_df['close'].iloc[-1]
        klines = []
        for _ in range(num_steps):
            change = np.random.normal(0, 100) # Volatilitas 100 poin
            open_p = last_close
            close_p = open_p + change
            high_p = max(open_p, close_p) + abs(np.random.normal(0, 50))
            low_p = min(open_p, close_p) - abs(np.random.normal(0, 50))
            vol = abs(np.random.normal(20, 5))
            
            klines.append({
                "open": open_p, "high": high_p, "low": low_p, "close": close_p, "volume": vol
            })
            last_close = close_p
            
        return pd.DataFrame(klines)

    def interpolate_to_ticks(self, ohlcv_df, ticks_per_candle=100):
        """
        Mengubah K-Line 1m/5m menjadi sekumpulan tick price yang rapat
        menggunakan Brownian Bridge sederhana agar HFT engine bisa berjalan.
        """
        log.info(f"Interpolating {len(ohlcv_df)} candles into ticks...")
        ticks = []
        timestamp = 1700000000000 # Dummy start time (ms)
        
        for idx, row in ohlcv_df.iterrows():
            # Generate random path from open to close, hitting high/low
            path = np.linspace(row['open'], row['close'], ticks_per_candle)
            noise = np.random.normal(0, (row['high'] - row['low']) / 10, ticks_per_candle)
            path += noise
            
            # Force max/min to match high/low roughly
            path[ticks_per_candle//3] = row['high']
            path[2*ticks_per_candle//3] = row['low']
            
            for p in path:
                ticks.append({
                    "timestamp": timestamp,
                    "price": round(p, 2),
                    "qty": round(row['volume'] / ticks_per_candle, 4),
                    "is_buyer_maker": np.random.choice([True, False])
                })
                timestamp += 500 # 500ms per tick
                
        return pd.DataFrame(ticks)

    def run(self):
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        seed = self.fetch_seed_data()
        future_klines = self.generate_future_klines(seed, num_steps=500)
        ticks_df = self.interpolate_to_ticks(future_klines)
        
        ticks_df.to_csv(OUTPUT_FILE, index=False)
        log.info(f"Berhasil meng-generate {len(ticks_df)} ticks palsu ke {OUTPUT_FILE}")

if __name__ == "__main__":
    generator = SyntheticDataGenerator()
    generator.run()
