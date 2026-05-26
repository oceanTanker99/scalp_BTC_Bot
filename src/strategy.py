import pandas as pd
import pandas_ta as ta
import logging
from config.config import BOLLINGER_PERIOD, BOLLINGER_STD, RSI_PERIOD, RSI_OVERSOLD, RSI_OVERBOUGHT

log = logging.getLogger(__name__)

class StrategyEngine:
    def __init__(self):
        pass

    def analyze(self, df_1m: pd.DataFrame, df_5m: pd.DataFrame, ofi: float):
        """
        Analyze the market and return a signal.
        Returns:
            signal (str): 'LONG', 'SHORT', or 'NEUTRAL'
            price (float): current price
        """
        if len(df_1m) < BOLLINGER_PERIOD or len(df_5m) < 10:
            return "NEUTRAL", 0.0

        # Calculate Indicators on 1m
        df_1m['rsi'] = ta.rsi(df_1m['close'], length=RSI_PERIOD)
        bbands = ta.bbands(df_1m['close'], length=BOLLINGER_PERIOD, std=BOLLINGER_STD)
        if bbands is not None:
            df_1m = pd.concat([df_1m, bbands], axis=1)
            
        # VWAP calculation (Daily reset)
        # Using typical price
        df_1m['typical_price'] = (df_1m['high'] + df_1m['low'] + df_1m['close']) / 3
        # Assuming we just do a simple cumulative VWAP over the loaded window (e.g. last 100 mins) for scalping
        df_1m['vwap'] = (df_1m['typical_price'] * df_1m['volume']).cumsum() / df_1m['volume'].cumsum()
        
        current_1m = df_1m.iloc[-1]
        
        # Check if indicators are ready
        if pd.isna(current_1m['rsi']) or f'BBL_{BOLLINGER_PERIOD}_{float(BOLLINGER_STD)}' not in df_1m.columns:
            return "NEUTRAL", current_1m['close']

        bbl = current_1m[f'BBL_{BOLLINGER_PERIOD}_{float(BOLLINGER_STD)}']
        bbh = current_1m[f'BBU_{BOLLINGER_PERIOD}_{float(BOLLINGER_STD)}']
        rsi = current_1m['rsi']
        price = current_1m['close']
        vwap = current_1m['vwap']
        
        # MACRO TREND: Price vs VWAP
        is_bullish = price > vwap
        is_bearish = price < vwap

        # Trigger
        # Long: Price hits/pierces lower bollinger band AND RSI is oversold
        long_trigger = (price <= bbl * 1.0005) and (rsi < RSI_OVERSOLD)
        
        # Short: Price hits/pierces upper bollinger band AND RSI is overbought
        short_trigger = (price >= bbh * 0.9995) and (rsi > RSI_OVERBOUGHT)

        # OFI Confirmation
        ofi_bullish = ofi > 0.1 # More bids than asks
        ofi_bearish = ofi < -0.1 # More asks than bids

        signal = "NEUTRAL"
        if is_bullish and long_trigger and ofi_bullish:
            log.info(f"[SIGNAL] LONG Triggered! Price: {price}, BBL: {bbl}, RSI: {rsi}, OFI: {ofi}")
            signal = "LONG"
        elif is_bearish and short_trigger and ofi_bearish:
            log.info(f"[SIGNAL] SHORT Triggered! Price: {price}, BBH: {bbh}, RSI: {rsi}, OFI: {ofi}")
            signal = "SHORT"
            
        return signal, price
