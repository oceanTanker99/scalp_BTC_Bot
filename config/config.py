import os
from dotenv import load_dotenv

load_dotenv()

# API Keys
BINANCE_API_KEY = os.getenv("BINANCE_API_KEY", "")
BINANCE_SECRET_KEY = os.getenv("BINANCE_SECRET_KEY", "")
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
BINANCE_TESTNET = os.getenv("BINANCE_TESTNET", "true").lower() == "true"
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

# Strategy Parameters
SYMBOL = "BTCUSDT"
TIMEFRAME = "1m"
TIMEFRAME_HTF = "5m"

# Trading Sessions (UTC Time)
TRADE_START_HOUR_UTC = 8   # 08:00 UTC (Awal London Session)
TRADE_END_HOUR_UTC = 21    # 21:00 UTC (Akhir New York Session)

# Risk Management
MAX_DAILY_DRAWDOWN_PCT = 0.20
TRADE_RISK_PCT = 0.01  # Risk 1% per trade
LEVERAGE = 20

# TP/SL Targets
RRR_TP1 = 1.0
RRR_TP2 = 1.5
RRR_TP3 = 2.0
CLOSE_AT_TP1_PCT = 33
CLOSE_AT_TP2_PCT = 33
CLOSE_AT_TP3_PCT = 100

# Indicators
BOLLINGER_PERIOD = 20
BOLLINGER_STD = 2.5
RSI_PERIOD = 7
RSI_OVERSOLD = 20
RSI_OVERBOUGHT = 80

# Advanced Filters & Dynamic SL
ATR_PERIOD = 14
ATR_MULTIPLIER = 1.5
EMA_MTF_PERIOD = 200
ADX_PERIOD = 14
ADX_THRESHOLD = 25
