import pandas as pd
import pandas_ta as ta
import logging
import datetime
from config.config import BOLLINGER_PERIOD, BOLLINGER_STD, RSI_PERIOD, RSI_OVERSOLD, RSI_OVERBOUGHT, TRADE_START_HOUR_UTC, TRADE_END_HOUR_UTC, ATR_PERIOD, ATR_MULTIPLIER, EMA_MTF_PERIOD, ADX_PERIOD, ADX_THRESHOLD

log = logging.getLogger(__name__)

class StrategyEngine:
    def __init__(self):
        pass

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

        if len(df_1m) < BOLLINGER_PERIOD or len(df_15m) < EMA_MTF_PERIOD:
            return "NEUTRAL", 0.0, 0.0

        # Calculate Indicators on 1m
        df_1m['rsi'] = ta.rsi(df_1m['close'], length=RSI_PERIOD)
        bbands = ta.bbands(df_1m['close'], length=BOLLINGER_PERIOD, std=BOLLINGER_STD)
        if bbands is not None:
            df_1m = pd.concat([df_1m, bbands], axis=1)
            
        # Calculate ADX and ATR
        adx = ta.adx(df_1m['high'], df_1m['low'], df_1m['close'], length=ADX_PERIOD)
        if adx is not None:
            df_1m = pd.concat([df_1m, adx], axis=1)
            
        atr = ta.atr(df_1m['high'], df_1m['low'], df_1m['close'], length=ATR_PERIOD)
        if atr is not None:
            df_1m['atr'] = atr
            
        # Calculate MTF EMA 200
        df_15m['ema_200'] = ta.ema(df_15m['close'], length=EMA_MTF_PERIOD)
            
        # VWAP calculation (Daily reset)
        # Using typical price
        df_1m['typical_price'] = (df_1m['high'] + df_1m['low'] + df_1m['close']) / 3
        # Assuming we just do a simple cumulative VWAP over the loaded window (e.g. last 100 mins) for scalping
        df_1m['vwap'] = (df_1m['typical_price'] * df_1m['volume']).cumsum() / df_1m['volume'].cumsum()
        
        current_1m = df_1m.iloc[-1]
        current_15m = df_15m.iloc[-1]
        
        # Check if indicators are ready
        if pd.isna(current_1m['rsi']) or f'BBL_{BOLLINGER_PERIOD}_{float(BOLLINGER_STD)}' not in df_1m.columns or 'atr' not in df_1m.columns or f'ADX_{ADX_PERIOD}' not in df_1m.columns or pd.isna(current_15m['ema_200']):
            return "NEUTRAL", current_1m['close'], 0.0

        bbl = current_1m[f'BBL_{BOLLINGER_PERIOD}_{float(BOLLINGER_STD)}']
        bbh = current_1m[f'BBU_{BOLLINGER_PERIOD}_{float(BOLLINGER_STD)}']
        rsi = current_1m['rsi']
        price = current_1m['close']
        vwap = current_1m['vwap']
        current_adx = current_1m[f'ADX_{ADX_PERIOD}']
        current_atr = current_1m['atr']
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
            
        return signal, price, sl_distance
