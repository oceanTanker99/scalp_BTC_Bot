import json
import asyncio
import logging
import os
from openai import AsyncOpenAI
from config.config import AI_API_KEY

log = logging.getLogger(__name__)

# Konfigurasi
TUNING_INTERVAL_SECONDS = 3600  # 1 Jam
PARAMS_FILE = "config/ai_params.json"
AI_REQUEST_TIMEOUT = 120

class AITuner:
    def __init__(self, engine):
        self.api_key = AI_API_KEY
        self.engine = engine
        self._running = True
        
        # Default fallback parameters
        self.default_params = {
            "cvd_divergence_threshold": 5.0, # Minimum CVD delta to consider valid
            "imbalance_threshold": 0.3,      # Order book imbalance needed
            "vwap_distance_pct": 0.1,        # How far from VWAP to trigger
            "reasoning": "Default system params"
        }
        
        os.makedirs("config", exist_ok=True)
        if not os.path.exists(PARAMS_FILE):
            self._save_params(self.default_params)
            
        if not self.api_key:
            log.warning("AI_API_KEY tidak ditemukan! AI Tuner dinonaktifkan.")
            self.client = None
        else:
            # Use host.docker.internal to reach the Windows host from inside Docker
            self.client = AsyncOpenAI(
                api_key=self.api_key,
                base_url=os.getenv("AI_BASE_URL", "https://api.9router.com/v1"),
                timeout=AI_REQUEST_TIMEOUT
            )

    def _save_params(self, params):
        try:
            with open(PARAMS_FILE, "w") as f:
                json.dump(params, f, indent=4)
            log.info(f"✅ Parameter AI berhasil diperbarui: {params}")
        except Exception as e:
            log.error(f"Gagal menyimpan parameter AI: {e}")

    async def start_tuning_loop(self):
        if not self.client:
            return
            
        log.info("🤖 AI Tuning Layer (Background) mulai berjalan...")
        
        while self._running:
            try:
                # Ambil data makro 4 jam terakhir
                metrics_4h = self.engine.get_metrics()
                
                # Cek jika data sudah cukup lewat ketersediaan VWAP dan POC
                if metrics_4h.get('vwap', 0) == 0 or metrics_4h.get('poc', 0) == 0:
                    log.info(f"Data belum cukup untuk AI Tuning (VWAP: {metrics_4h.get('vwap', 0)}, POC: {metrics_4h.get('poc', 0)}). Skip siklus ini.")
                    await asyncio.sleep(60)
                    continue
                    
                prompt = f"""Anda adalah "Quantitative Strategist" untuk mesin High-Frequency Order Flow.
Tugas Anda adalah meracik parameter sensitivitas eksekusi (Thresholds) untuk mesin Python lokal, berdasarkan metrik 4 Jam terakhir.

Data 4 Jam Terakhir:
- CVD (Delta Volume): {metrics_4h.get('cvd', 0)}
- VWAP: {metrics_4h.get('vwap', 0)}
- Orderbook Imbalance Rata-Rata: {metrics_4h.get('imbalance', 0)}

Volume Profile (4 Jam):
- Harga Saat Ini: {metrics_4h.get('current_price', 0)}
- POC (Point of Control): {metrics_4h.get('poc', 0)}
- VAH (Value Area High): {metrics_4h.get('vah', 0)}
- VAL (Value Area Low): {metrics_4h.get('val', 0)}

Tentukan threshold yang optimal untuk scalping saat ini:
1. `cvd_divergence_threshold`: Batas deviasi CVD yang dianggap sebagai sinyal valid (biasanya antara 1.0 hingga 15.0 tergantung volatilitas).
2. `imbalance_threshold`: Persentase dominasi Orderbook (misal 0.2 untuk 20% imbalance).
3. `vwap_distance_pct`: Jarak persentase dari VWAP untuk mendeteksi over-extension (misal 0.05 hingga 0.2).

Keluarkan HANYA JSON murni dengan format:
{{
    "cvd_divergence_threshold": float,
    "imbalance_threshold": float,
    "vwap_distance_pct": float,
    "reasoning": "Alasan analisis makro singkat"
}}
"""
                log.info("🧠 Meminta 9router menganalisis dan menyetel ulang parameter strategi...")
                response = await self.client.chat.completions.create(
                    model="freetier", # 9router will route this appropriately
                    messages=[
                        {"role": "system", "content": "You are an elite quantitative strategist tuning an HFT bot. Output JSON only."},
                        {"role": "user", "content": prompt}
                    ],
                    response_format={"type": "json_object"}
                )
                
                result_str = response.choices[0].message.content
                result_json = json.loads(result_str)
                
                # Validasi kunci
                if "cvd_divergence_threshold" in result_json:
                    self._save_params(result_json)
                    
            except json.JSONDecodeError:
                log.error("AI mengembalikan JSON yang tidak valid.")
            except Exception as e:
                log.error(f"Error pada siklus AI Tuning: {e}")
                
            # Tunggu 1 jam untuk siklus berikutnya
            await asyncio.sleep(TUNING_INTERVAL_SECONDS)
