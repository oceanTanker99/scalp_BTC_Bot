import pandas as pd
import pandas_ta as ta
import logging
from datetime import datetime, timezone
import csv
import os
from config.config import (
    BOLLINGER_PERIOD, BOLLINGER_STD, RSI_PERIOD, RSI_OVERSOLD, RSI_OVERBOUGHT,
    TRADE_START_HOUR_UTC, TRADE_END_HOUR_UTC, ATR_PERIOD, ATR_MULTIPLIER,
    EMA_MTF_PERIOD, ADX_PERIOD, ADX_THRESHOLD, OFI_BOOST_THRESHOLD,
    VOLUME_SPIKE_MULTIPLIER, BB_SQUEEZE_THRESHOLD, MIN_SIGNAL_SCORE
)

log = logging.getLogger(__name__)

class StrategyEngine:
    def __init__(self):
        self.log_file = "logs/analysis_report.csv"
        os.makedirs("logs", exist_ok=True)
        if not os.path.exists(self.log_file):
            with open(self.log_file, mode='w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow([
                    "timestamp_utc", "price", "rsi", "bbl", "bbh", "bb_width",
                    "vwap", "adx", "ema_200", "ofi", "volume_spike",
                    "score", "signal", "sl_distance", "reject_reason"
                ])

    def analyze(self, df_1m: pd.DataFrame, df_5m: pd.DataFrame, df_15m: pd.DataFrame, ofi: float):
        """
        Analyze the market and return a signal using a multi-factor scoring system.

        Returns:
            signal (str): 'LONG', 'SHORT', or 'NEUTRAL'
            price (float): current price
            sl_distance (float): dynamic stop loss distance (as fraction of price)
            context (dict): full indicator snapshot for AI enrichment
        """
        # --- Filter Jam Trading ---
        current_hour_utc = datetime.now(timezone.utc).hour
        if current_hour_utc < TRADE_START_HOUR_UTC or current_hour_utc >= TRADE_END_HOUR_UTC:
            return "NEUTRAL", 0.0, 0.0, {}

        if len(df_5m) < BOLLINGER_PERIOD + 5 or len(df_15m) < EMA_MTF_PERIOD:
            return "NEUTRAL", 0.0, 0.0, {}

        # ── Hitung Indikator ──────────────────────────────────────────────────

        # RSI
        df_5m = df_5m.copy()
        df_5m['rsi'] = ta.rsi(df_5m['close'], length=RSI_PERIOD)

        # Bollinger Bands
        bbands = ta.bbands(df_5m['close'], length=BOLLINGER_PERIOD, std=BOLLINGER_STD)
        if bbands is not None:
            df_5m = pd.concat([df_5m, bbands], axis=1)

        # ADX & ATR
        adx_df = ta.adx(df_5m['high'], df_5m['low'], df_5m['close'], length=ADX_PERIOD)
        if adx_df is not None:
            df_5m = pd.concat([df_5m, adx_df], axis=1)

        atr_series = ta.atr(df_5m['high'], df_5m['low'], df_5m['close'], length=ATR_PERIOD)
        if atr_series is not None:
            df_5m['atr'] = atr_series

        # EMA 200 di 15m (Macro Trend)
        df_15m = df_15m.copy()
        df_15m['ema_200'] = ta.ema(df_15m['close'], length=EMA_MTF_PERIOD)

        # VWAP dengan Daily Reset (00:00 UTC)
        df_5m['date_utc'] = pd.to_datetime(df_5m['timestamp'], unit='ms', utc=True).dt.date
        df_5m['typical_price'] = (df_5m['high'] + df_5m['low'] + df_5m['close']) / 3
        
        # Gunakan kolom sementara untuk menghindari bug apply() di Pandas >= 2.2
        df_5m['tp_vol'] = df_5m['typical_price'] * df_5m['volume']
        df_5m['cum_tp_vol'] = df_5m.groupby('date_utc')['tp_vol'].cumsum()
        df_5m['cum_vol'] = df_5m.groupby('date_utc')['volume'].cumsum()
        df_5m['vwap'] = df_5m['cum_tp_vol'] / df_5m['cum_vol']

        # Volume Moving Average (untuk deteksi volume spike)
        df_5m['volume_ma'] = df_5m['volume'].rolling(window=20).mean()

        # ── Ambil Nilai Terkini ───────────────────────────────────────────────
        current = df_5m.iloc[-1]
        current_15m = df_15m.iloc[-1]

        bbl_col = [col for col in df_5m.columns if col.startswith('BBL_')][0]
        bbh_col = [col for col in df_5m.columns if col.startswith('BBU_')][0]
        adx_col = [col for col in df_5m.columns if col.startswith('ADX_')][0]

        required_cols = [bbl_col, bbh_col, adx_col, 'rsi', 'atr', 'vwap', 'volume_ma']
        if any(col not in df_5m.columns or pd.isna(current.get(col, float('nan'))) for col in required_cols):
            return "NEUTRAL", current['close'], 0.0, {}
        if pd.isna(current_15m['ema_200']):
            return "NEUTRAL", current['close'], 0.0, {}

        price       = current['close']
        rsi         = current['rsi']
        bbl         = current[bbl_col]
        bbh         = current[bbh_col]
        adx         = current[adx_col]
        atr         = current['atr']
        vwap        = current['vwap']
        ema_200     = current_15m['ema_200']
        volume      = current['volume']
        volume_ma   = current['volume_ma']

        sl_distance = (atr * ATR_MULTIPLIER) / price

        # ── Kalkulasi Derivatif ───────────────────────────────────────────────

        # BB Width (untuk squeeze detection)
        bb_width = (bbh - bbl) / price

        # Volume Spike
        is_volume_spike = volume > (volume_ma * VOLUME_SPIKE_MULTIPLIER)

        # ── Perbaikan #5: BB Squeeze Detection ───────────────────────────────
        if bb_width < BB_SQUEEZE_THRESHOLD:
            reason = f"BB Squeeze (width={bb_width:.4f} < {BB_SQUEEZE_THRESHOLD})"
            self._log_csv(current, price, rsi, bbl, bbh, bb_width, vwap, adx,
                          ema_200, ofi, is_volume_spike, 0, "NEUTRAL (BB Squeeze)", sl_distance, reason)
            return "NEUTRAL", price, sl_distance, {}

        # ── Perbaikan #1: Filter Tren — hanya EMA 200, tanpa VWAP ────────────
        is_bullish_macro = price > ema_200   # Harga di atas EMA 200 (15m) → tren bullish
        is_bearish_macro = price < ema_200   # Harga di bawah EMA 200 (15m) → tren bearish

        # ── Perbaikan #2: Trigger dengan RSI 30/70 ───────────────────────────
        long_bb_touch  = price <= bbl * 1.001   # Harga menyentuh/menembus BB bawah
        short_bb_touch = price >= bbh * 0.999   # Harga menyentuh/menembus BB atas

        long_rsi_ok  = rsi < RSI_OVERSOLD    # RSI oversold (< 30)
        short_rsi_ok = rsi > RSI_OVERBOUGHT  # RSI overbought (> 70)

        # ADX Filter (tren terlalu kuat = bukan lingkungan mean-reversion)
        if adx > ADX_THRESHOLD:
            reason = f"ADX Terlalu Tinggi ({adx:.1f} > {ADX_THRESHOLD})"
            self._log_csv(current, price, rsi, bbl, bbh, bb_width, vwap, adx,
                          ema_200, ofi, is_volume_spike, 0, f"NEUTRAL (ADX>{ADX_THRESHOLD})", sl_distance, reason)
            return "NEUTRAL", price, sl_distance, {}

        # ── Perbaikan #3: Sistem Skor (mengganti OFI wajib) ──────────────────
        signal = "NEUTRAL"
        score = 0
        reject_reason = "Kondisi tidak terpenuhi"

        for direction in ['LONG', 'SHORT']:
            score = 0
            bb_touch  = long_bb_touch  if direction == 'LONG' else short_bb_touch
            rsi_ok    = long_rsi_ok    if direction == 'LONG' else short_rsi_ok
            macro_ok  = is_bullish_macro if direction == 'LONG' else is_bearish_macro
            ofi_ok    = ofi > OFI_BOOST_THRESHOLD if direction == 'LONG' else ofi < -OFI_BOOST_THRESHOLD

            if not (bb_touch and rsi_ok):
                continue  # Trigger utama wajib ada

            # BB touch + RSI = 2 poin dasar
            score += 2

            # Perbaikan #1: Macro filter = 1 poin wajib (tanpa ini, skip)
            if macro_ok:
                score += 1
            else:
                reject_reason = f"Tren Makro EMA 200 berlawanan (price={price:.1f}, ema200={ema_200:.1f})"
                continue

            # Perbaikan #3: OFI sebagai booster (1 poin opsional)
            if ofi_ok:
                score += 1

            # Perbaikan #4: Volume spike sebagai booster (1 poin opsional)
            if is_volume_spike:
                score += 1

            # Minimum skor untuk eksekusi
            if score >= MIN_SIGNAL_SCORE:
                signal = direction
                reject_reason = ""
                log.info(
                    f"[SIGNAL] {direction} | Score: {score}/5 | Price: {price:.1f} | "
                    f"RSI: {rsi:.1f} | ADX: {adx:.1f} | OFI: {ofi:.3f} | "
                    f"VolSpike: {is_volume_spike} | BBW: {bb_width:.4f}"
                )
                break
            else:
                reject_reason = f"Skor tidak cukup ({score}/{MIN_SIGNAL_SCORE} min)"

        # ── Susun Konteks untuk AI ────────────────────────────────────────────
        context = {
            "price": round(price, 2),
            "rsi": round(rsi, 2),
            "bbl": round(bbl, 2),
            "bbh": round(bbh, 2),
            "bb_width_pct": round(bb_width * 100, 3),
            "vwap": round(vwap, 2),
            "price_vs_vwap_pct": round(((price - vwap) / vwap) * 100, 3),
            "ema_200_15m": round(ema_200, 2),
            "price_vs_ema200_pct": round(((price - ema_200) / ema_200) * 100, 3),
            "adx": round(adx, 2),
            "atr": round(atr, 2),
            "atr_pct": round((atr / price) * 100, 3),
            "ofi": round(ofi, 4),
            "volume_spike": is_volume_spike,
            "score": score,
        }

        # ── Log ke CSV ────────────────────────────────────────────────────────
        self._log_csv(current, price, rsi, bbl, bbh, bb_width, vwap, adx,
                      ema_200, ofi, is_volume_spike, score, signal, sl_distance, reject_reason)

        return signal, price, sl_distance, context

    def _log_csv(self, current, price, rsi, bbl, bbh, bb_width, vwap, adx,
                 ema_200, ofi, volume_spike, score, signal, sl_distance, reject_reason):
        try:
            with open(self.log_file, mode='a', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
                writer.writerow([
                    ts, price, round(rsi, 2), round(bbl, 2), round(bbh, 2),
                    round(bb_width, 4), round(vwap, 2), round(adx, 2), round(ema_200, 2),
                    round(ofi, 4), volume_spike, score, signal,
                    round(sl_distance, 4), reject_reason
                ])
        except Exception as e:
            log.error(f"Error writing to analysis CSV: {e}")
