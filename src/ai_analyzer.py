import os
import json
import logging
from openai import AsyncOpenAI
import pandas as pd
from config.config import DEEPSEEK_API_KEY

log = logging.getLogger(__name__)

class DeepSeekValidator:
    def __init__(self):
        self.api_key = DEEPSEEK_API_KEY
        if not self.api_key:
            log.warning("DEEPSEEK_API_KEY is missing! AI validation will be disabled.")
            self.client = None
        else:
            self.client = AsyncOpenAI(api_key=self.api_key, base_url="https://api.deepseek.com/v1")

    async def validate(self, signal: str, df_5m: pd.DataFrame, ofi: float) -> bool:
        if not self.client:
            log.warning("No DeepSeek Client initialized. Approving by default.")
            return True
            
        try:
            # Mengambil 5 candle terakhir untuk menunjukkan price action terbaru
            recent_candles = df_5m.tail(5)[['timestamp', 'open', 'high', 'low', 'close', 'volume', 'rsi']].to_dict(orient='records')
            current = df_5m.iloc[-1]
            
            # Mendapatkan ADX column name secara dinamis
            adx_col = [col for col in df_5m.columns if col.startswith('ADX_')][0]
            
            prompt = f"""Anda adalah Quant Trader elit. Bot algoritmik mendeteksi sinyal {signal} di grafik 5 Menit.
            Data terkini:
            Harga: {current['close']}
            RSI: {current['rsi']}
            ADX: {current[adx_col]}
            OFI (Order Flow Imbalance): {ofi}
            
            5 Candle Terakhir (OHLCV):
            {json.dumps(recent_candles, indent=2)}
            
            Berdasarkan data teknikal murni ini, validasi apakah sinyal {signal} ini memiliki probabilitas tinggi untuk sukses (berupa pantulan mean-reversion) atau berisiko tinggi terjebak dalam tren kuat (fakeout).
            Anda harus menjawab HANYA dengan format JSON yang valid, tanpa tambahan teks apapun.
            Format JSON yang WAJIB digunakan:
            {{
              "reasoning": "alasan singkat analisis anda (max 2 kalimat)",
              "approved": true atau false
            }}
            """
            
            log.info(f"Meminta validasi dari DeepSeek AI untuk sinyal {signal}...")
            response = await self.client.chat.completions.create(
                model="deepseek-chat",
                messages=[
                    {"role": "system", "content": "You are an elite quantitative trader AI. You must output strict JSON."},
                    {"role": "user", "content": prompt}
                ],
                response_format={"type": "json_object"},
                temperature=0.1
            )
            
            result_str = response.choices[0].message.content
            result_json = json.loads(result_str)
            
            log.info(f"[DEEPSEEK REASONING] {result_json.get('reasoning')}")
            is_approved = result_json.get('approved', False)
            log.info(f"[DEEPSEEK DECISION] {'✅ APPROVED' if is_approved else '❌ REJECTED'}")
            
            return is_approved
            
        except json.JSONDecodeError:
            log.error(f"DeepSeek mengembalikan format JSON yang tidak valid: {result_str}")
            return False
        except Exception as e:
            log.error(f"Error memanggil DeepSeek API: {e}")
            # Failsafe: Jika API mati/error, tolak sinyal demi keamanan
            return False
