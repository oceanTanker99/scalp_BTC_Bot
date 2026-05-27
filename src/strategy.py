import pandas as pd
import pandas_ta as ta
import logging
import datetime
import csv
import os
from config.config import BOLLINGER_PERIOD, BOLLINGER_STD, RSI_PERIOD, RSI_OVERSOLD, RSI_OVERBOUGHT, TRADE_START_HOUR_UTC, TRADE_END_HOUR_UTC, ATR_PERIOD, ATR_MULTIPLIER, EMA_MTF_PERIOD, ADX_PERIOD, ADX_THRESHOLD

log = logging.getLogger(__name__)

class StrategyEngine:
    def __init__(self):
        self.log_file = "logs/analysis_report.csv"
        os.makedirs("logs", exist_ok=True)
        if not os.path.exists(self.log_file):
            with open(self.log_file, mode='w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(["timestamp_utc", "price", "rsi", "bbl", "bbh", "vwap", "adx", "ema_200", "ofi", "signal", "sl_distance"])

    def analyze(self, df_1m: pd.DataFrame, df_5m: pd.DataFrame, df_15m: pd.DataFrame, ofi: float):
        """
        Analyze the market and return a signal.
        Returns:
            signal (str): 'LONG', 'SHORT', or 'NEUTRAL'
            price (float): current price
            sl_distance (float): distance for dynamic stop loss
        """
        current_hour_utc = datetime.datetime.utcnow().hour
        if current_hour_utc < TRADE_START_HOUR_UTC or current_hour_utc >= TRADE_END_HOUR_UTC:
            return "NEUTRAL", 0.0, 0.0

        if len(df_5m) < BOLLINGER_PERIOD or len(df_15m) < EMA_MTF_PERIOD:
            return "NEUTRAL", 0.0, 0.0

        # Calculate Indicators on 5m
        df_5m['rsi'] = ta.rsi(df_5m['close'], length=RSI_PERIOD)
        bbands = ta.bbands(df_5m['close'], length=BOLLINGER_PERIOD, std=BOLLINGER_STD)
        if bbands is not None:
            df_5m = pd.concat([df_5m, bbands], axis=1)
            
        # Calculate ADX and ATR
        adx = ta.adx(df_5m['high'], df_5m['low'], df_5m['close'], length=ADX_PERIOD)
        if adx is not None:
            df_5m = pd.concat([df_5m, adx], axis=1)
            
        atr = ta.atr(df_5m['high'], df_5m['low'], df_5m['close'], length=ATR_PERIOD)
        if atr is not None:
            df_5m['atr'] = atr
            
        # Calculate MTF EMA 200
        df_15m['ema_200'] = ta.ema(df_15m['close'], length=EMA_MTF_PERIOD)
            
        # VWAP calculation (Daily reset)
        # Using typical price
        df_5m['typical_price'] = (df_5m['high'] + df_5m['low'] + df_5m['close']) / 3
        # Assuming we just do a simple cumulative VWAP over the loaded window
        df_5m['vwap'] = (df_5m['typical_price'] * df_5m['volume']).cumsum() / df_5m['volume'].cumsum()
        
        current_5m = df_5m.iloc[-1]
        current_15m = df_15m.iloc[-1]
        
        # Check if indicators are ready
        if pd.isna(current_5m['rsi']) or f'BBL_{BOLLINGER_PERIOD}_{float(BOLLINGER_STD)}' not in df_5m.columns or 'atr' not in df_5m.columns or f'ADX_{ADX_PERIOD}' not in df_5m.columns or pd.isna(current_15m['ema_200']):
            return "NEUTRAL", current_5m['close'], 0.0

        bbl = current_5m[f'BBL_{BOLLINGER_PERIOD}_{float(BOLLINGER_STD)}']
        bbh = current_5m[f'BBU_{BOLLINGER_PERIOD}_{float(BOLLINGER_STD)}']
        rsi = current_5m['rsi']
        price = current_5m['close']
        vwap = current_5m['vwap']
        current_adx = current_5m[f'ADX_{ADX_PERIOD}']
        current_atr = current_5m['atr']
        current_ema_200 = current_15m['ema_200']
        
        # Volatility Filter (ADX)
        if current_adx > ADX_THRESHOLD:
            return "NEUTRAL", price, 0.0

        # MACRO TREND: Price vs VWAP and MTF EMA
        is_bullish = (price > vwap) and (price > current_ema_200)
        is_bearish = (price < vwap) and (price < current_ema_200)

        # Trigger
        # Long: Price hits/pierces lower bollinger band AND RSI is oversold
        long_trigger = (price <= bbl * 1.0005) and (rsi < RSI_OVERSOLD)
        
        # Short: Price hits/pierces upper bollinger band AND RSI is overbought
        short_trigger = (price >= bbh * 0.9995) and (rsi > RSI_OVERBOUGHT)

        # OFI Confirmation
        ofi_bullish = ofi > 0.25 # More bids than asks
        ofi_bearish = ofi < -0.25 # More asks than bids

        sl_distance = (current_atr * ATR_MULTIPLIER) / price
        
        signal = "NEUTRAL"
        if is_bullish and long_trigger and ofi_bullish:
            log.info(f"[SIGNAL] LONG Triggered! Price: {price}, BBL: {bbl}, RSI: {rsi}, OFI: {ofi}, ADX: {current_adx}")
            signal = "LONG"
        elif is_bearish and short_trigger and ofi_bearish:
            log.info(f"[SIGNAL] SHORT Triggered! Price: {price}, BBH: {bbh}, RSI: {rsi}, OFI: {ofi}, ADX: {current_adx}")
            signal = "SHORT"
            
        # Log to CSV
        try:
            with open(self.log_file, mode='a', newline='') as f:
                writer = csv.writer(f)
                ts = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
                writer.writerow([ts, price, round(rsi,2), round(bbl,2), round(bbh,2), round(vwap,2), round(current_adx,2), round(current_ema_200,2), round(ofi,4), signal, round(sl_distance, 4)])
        except Exception as e:
            log.error(f"Error writing to analysis CSV: {e}")
            
        return signal, price, sl_distance
