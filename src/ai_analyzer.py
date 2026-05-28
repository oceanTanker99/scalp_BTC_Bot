import json
import logging
from openai import AsyncOpenAI
import pandas as pd
from config.config import DEEPSEEK_API_KEY

log = logging.getLogger(__name__)

# Konfigurasi retry & timeout
AI_REQUEST_TIMEOUT = 30   # Timeout per request dalam detik
AI_MAX_RETRIES = 2        # Jumlah retry jika request gagal


class DeepSeekValidator:
    def __init__(self):
        self.api_key = DEEPSEEK_API_KEY
        if not self.api_key:
            log.warning("DEEPSEEK_API_KEY tidak ditemukan! Validasi AI dinonaktifkan.")
            self.client = None
        else:
            self.client = AsyncOpenAI(
                api_key=self.api_key,
                base_url="https://api.deepseek.com/v1",
                timeout=AI_REQUEST_TIMEOUT
            )

    async def validate(self, signal: str, df_5m: pd.DataFrame, ofi: float,
                       context: dict = None) -> tuple[bool, str]:
        """
        Validasi sinyal menggunakan DeepSeek AI.

        Args:
            signal: Arah sinyal ('LONG' atau 'SHORT')
            df_5m: DataFrame candle 5 menit
            ofi: Order Flow Imbalance
            context: Dict indikator dari StrategyEngine

        Returns:
            (is_approved, reasoning): Tuple bool dan string alasan
        """
        if not self.client:
            log.warning("Client DeepSeek tidak aktif. Sinyal disetujui otomatis.")
            return True, "AI nonaktif"

        ctx = context or {}

        # Ambil 8 candle terakhir
        cols_to_show = [c for c in ['timestamp', 'open', 'high', 'low', 'close', 'volume', 'rsi']
                        if c in df_5m.columns]
        recent_candles = df_5m.tail(8)[cols_to_show].round(2).to_dict(orient='records')

        # Tentukan zona harga relatif
        price_zone = "Di atas VWAP" if ctx.get('price_vs_vwap_pct', 0) > 0 else "Di bawah VWAP"
        macro_zone = ("Di atas EMA 200 (Bullish Makro)" if ctx.get('price_vs_ema200_pct', 0) > 0
                      else "Di bawah EMA 200 (Bearish Makro)")

        prompt = f"""Anda adalah Quant Trader institusional yang menggunakan strategi Mean-Reversion.
Bot telah mendeteksi sinyal potensial: **{signal}** di grafik 5 Menit BTC/USDT.

═══ SNAPSHOT INDIKATOR SAAT INI ═══
Harga          : {ctx.get('price', 'N/A')} USDT
RSI (7)        : {ctx.get('rsi', 'N/A')} {'🟢 Oversold' if signal == 'LONG' else '🔴 Overbought'}
Bollinger Low  : {ctx.get('bbl', 'N/A')} | Bollinger High: {ctx.get('bbh', 'N/A')}
BB Width       : {ctx.get('bb_width_pct', 'N/A')}% {'(Sempit/Squeeze)' if ctx.get('bb_width_pct', 99) < 2 else '(Normal/Melebar)'}
VWAP (Harian)  : {ctx.get('vwap', 'N/A')} → Harga {price_zone} ({ctx.get('price_vs_vwap_pct', 'N/A')}%)
EMA 200 (15m)  : {ctx.get('ema_200_15m', 'N/A')} → {macro_zone} ({ctx.get('price_vs_ema200_pct', 'N/A')}%)
ADX (Tren)     : {ctx.get('adx', 'N/A')} {'(Tren Lemah ✓)' if ctx.get('adx', 99) < 25 else '(Tren Kuat ⚠️)'}
ATR Volatilitas: {ctx.get('atr', 'N/A')} ({ctx.get('atr_pct', 'N/A')}% dari harga)
OFI Orderbook  : {ctx.get('ofi', 'N/A')} {'(Dominasi Beli ✓)' if ofi > 0 else '(Dominasi Jual)'}
Volume Spike   : {'YA 🔥' if ctx.get('volume_spike') else 'Tidak'}
Skor Sinyal    : {ctx.get('score', 'N/A')}/5

═══ 8 CANDLE TERAKHIR (5 MENIT) ═══
{json.dumps(recent_candles, indent=2)}

═══ TUGAS ANDA ═══
Berdasarkan seluruh data di atas, tentukan apakah sinyal **{signal}** ini layak dieksekusi sebagai trade Mean-Reversion.
Pertimbangkan:
1. Apakah harga benar-benar sudah "terlalu jauh dari equilibrium" (VWAP/EMA 200) dan siap memantul?
2. Apakah aksi harga di 8 candle terakhir mendukung atau menentang potensi reversal?
3. Apakah ada tanda-tanda momentum berlanjut (bearish engulfing, volume terus naik saat turun) yang menunjukkan ini BUKAN reversal tapi continuation?

Jawab HANYA dengan format JSON berikut, tanpa teks lain:
{{
  "reasoning": "analisis Anda dalam 2-3 kalimat yang mencakup price action, konteks makro, dan penentuan momentum",
  "approved": true atau false
}}"""

        # --- Retry loop ---
        last_error = None
        for attempt in range(1, AI_MAX_RETRIES + 1):
            try:
                log.info(
                    f"🧠 Meminta validasi DeepSeek untuk sinyal {signal} "
                    f"(skor: {ctx.get('score', '?')}/5, percobaan {attempt}/{AI_MAX_RETRIES})..."
                )

                response = await self.client.chat.completions.create(
                    model="deepseek-chat",
                    messages=[
                        {
                            "role": "system",
                            "content": ("You are an elite institutional quantitative trader "
                                        "specializing in mean-reversion strategies. Output only strict JSON.")
                        },
                        {"role": "user", "content": prompt}
                    ],
                    response_format={"type": "json_object"},
                    temperature=0.1
                )

                result_str = response.choices[0].message.content
                result_json = json.loads(result_str)

                reasoning = result_json.get('reasoning', '-')
                is_approved = result_json.get('approved', False)

                log.info(f"[DEEPSEEK] {'✅ DISETUJUI' if is_approved else '❌ DITOLAK'} | {reasoning}")
                return is_approved, reasoning

            except json.JSONDecodeError as e:
                log.error(f"DeepSeek mengembalikan JSON tidak valid (percobaan {attempt}): {e}")
                last_error = "JSON decode error"
            except Exception as e:
                log.error(f"DeepSeek API error (percobaan {attempt}): {e}")
                last_error = str(e)

        # Semua percobaan gagal — tolak sinyal untuk keamanan
        log.warning(f"⚠️ Semua {AI_MAX_RETRIES} percobaan DeepSeek gagal. Sinyal ditolak untuk keamanan.")
        return False, f"AI gagal setelah {AI_MAX_RETRIES} percobaan: {last_error}"
