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
                       context: dict = None, sentiment: dict = None) -> tuple[bool, str]:
        """
        Validasi sinyal menggunakan DeepSeek AI dengan parameter Sentiment.
        """
        if not self.client:
            log.warning("Client DeepSeek tidak aktif. Sinyal disetujui otomatis.")
            return True, "AI nonaktif"

        ctx = context or {}
        sent = sentiment or {}

        # Ambil 8 candle terakhir
        cols_to_show = [c for c in ['timestamp', 'open', 'high', 'low', 'close', 'volume', 'rsi']
                        if c in df_5m.columns]
        recent_candles = df_5m.tail(8)[cols_to_show].round(2).to_dict(orient='records')

        price_zone = "Di atas VWAP" if ctx.get('price_vs_vwap_pct', 0) > 0 else "Di bawah VWAP"
        macro_zone = ("Di atas EMA 200 (Bullish Makro)" if ctx.get('price_vs_ema200_pct', 0) > 0
                      else "Di bawah EMA 200 (Bearish Makro)")
        strategy_type = ctx.get('strategy_type', 'MEAN_REVERSION')
        
        if strategy_type == 'MEAN_REVERSION':
            strategy_instruction = """Anda adalah Quant Trader institusional beraliran MEAN-REVERSION (Pemulihan ke Rata-Rata).
Bot telah mendeteksi sinyal potensial: **{signal}** di grafik 5 Menit BTC/USDT.
Harga saat ini sedang berada di luar batas wajar (Bollinger Bands) dan ada potensi memantul kembali ke tengah.
            """
            evaluation_instruction = """
Pertimbangkan:
1. Sentimen Derivatives: Apakah Funding Rate terlalu berlawanan? Apakah Top Traders sedang berada di sisi yang berlawanan dengan sinyal ini? (Misal: Sinyal Long tapi Top L/S < 0.95, artinya paus sedang nge-Short).
2. Apakah harga benar-benar sudah "terlalu jauh dari equilibrium" (VWAP/EMA 200) dan siap memantul?
3. Apakah aksi harga di 8 candle terakhir mendukung atau menentang potensi reversal?
4. Apakah ada tanda-tanda momentum berlanjut (bearish engulfing, volume terus naik saat turun) yang menunjukkan ini BUKAN reversal tapi continuation?
            """
        elif strategy_type == 'SMC_FVG':
            strategy_instruction = """Anda adalah Quant Trader institusional beraliran SMART MONEY CONCEPTS (SMC).
Bot telah mendeteksi sinyal potensial: **{signal}** di grafik 5 Menit BTC/USDT berdasarkan mitigasi Fair Value Gap (FVG).
Harga baru saja masuk kembali ke area celah kosong yang ditinggalkan oleh pelarian harga institusional (Displacement).
            """
            evaluation_instruction = """
Pertimbangkan:
1. Sentimen Derivatives: Apakah mayoritas paus (Top L/S Ratio) mendukung arah FVG ini?
2. Konteks Harga: Apakah FVG ini terjadi searah dengan tren makro (EMA 200)? Jika melawan tren makro, pastikan ada tanda pelemahan yang sangat kuat.
3. Apakah aksi harga di 8 candle terakhir menunjukkan penolakan (rejection wick) saat menyentuh FVG, atau malah menembusnya dengan agresif?
4. Tolak jika harga terlihat menembus zona FVG dengan volume yang makin membesar (momentum berlawanan arah sangat kuat).
            """
        else:
            strategy_instruction = """Anda adalah Quant Trader institusional beraliran TREND-FOLLOWING (Pengikut Tren).
Bot telah mendeteksi sinyal potensial: **{signal}** di grafik 5 Menit BTC/USDT.
Pasar sedang berada dalam tren MAHA KUAT (Dikonfirmasi oleh ADX, DMI, dan Jarak Makro EMA 800).
Ini adalah setup "Buy on Dip" (Pullback ke garis EMA 20) atau "Breakout" searah dengan tren makro.
            """
            evaluation_instruction = """
Pertimbangkan:
1. Sentimen Derivatives: Apakah mayoritas ritel melawan tren ini (Funding Rate sangat negatif tapi harga naik terus)? Jika ya, itu bensin tambahan untuk trend.
2. Pullback/Breakout: Apakah volume mengering saat harga pullback (konsolidasi sehat), dan siap melonjak lagi?
3. Jangan takut untuk menyetujui sinyal jika harga memang sedang pullback dangkal di tengah tren yang sangat kuat.
4. Tolak jika ada pola pembalikan arah skala besar (misal: Head and Shoulders, volume buang barang raksasa di pucuk).
            """

        prompt = f"""{strategy_instruction}
═══ DATA SENTIMEN DERIVATIVES (BINANCE) ═══
Funding Rate          : {sent.get('funding_rate', 0)*100:.4f}%
Open Interest         : {sent.get('open_interest', 0):,.0f}
Top L/S Ratio (Paus)  : {sent.get('top_long_short_ratio', 1.0):.2f} ( >1: Banyak Long, <1: Banyak Short)
Global L/S Ratio      : {sent.get('global_long_short_ratio', 1.0):.2f}

═══ SNAPSHOT INDIKATOR SAAT INI ═══
Tipe Strategi  : {strategy_type}
Harga          : {ctx.get('price', 'N/A')} USDT
RSI (7)        : {ctx.get('rsi', 'N/A')}
Bollinger Low  : {ctx.get('bbl', 'N/A')} | Bollinger High: {ctx.get('bbh', 'N/A')}
BB Width       : {ctx.get('bb_width_pct', 'N/A')}%
VWAP (Harian)  : {ctx.get('vwap', 'N/A')} → Harga {price_zone} ({ctx.get('price_vs_vwap_pct', 'N/A')}%)
EMA 200 (15m)  : {ctx.get('ema_200_15m', 'N/A')} → {macro_zone} ({ctx.get('price_vs_ema200_pct', 'N/A')}%)
EMA 800 (15m)  : {ctx.get('ema_800_15m', 'N/A')} (Macro Baseline)
ADX (Tren)     : {ctx.get('adx', 'N/A')} (Tren Kuat jika > 25)
DMI (+DI/-DI)  : +DI {ctx.get('dmp', 'N/A')} | -DI {ctx.get('dmn', 'N/A')}
ATR Volatilitas: {ctx.get('atr', 'N/A')} ({ctx.get('atr_pct', 'N/A')}% dari harga)
OFI Orderbook  : {ofi:.2f} {'(Dominasi Beli ✓)' if ofi > 0 else '(Dominasi Jual)'}
Volume Spike   : {'YA 🔥' if ctx.get('volume_spike') else 'Tidak'}
Skor Sinyal    : {ctx.get('score', 'N/A')}/5

═══ 8 CANDLE TERAKHIR (5 MENIT) ═══
{json.dumps(recent_candles, indent=2)}

═══ TUGAS ANDA ═══
Berdasarkan seluruh data di atas, tentukan apakah sinyal **{signal}** ini layak dieksekusi.
{evaluation_instruction}

Jawab HANYA dengan format JSON berikut, tanpa teks lain:
{{
  "reasoning": "analisis Anda dalam 2-3 kalimat yang mencakup sentimen, price action, dan kecocokan dengan {strategy_type}",
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
