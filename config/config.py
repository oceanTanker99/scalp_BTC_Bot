import os
from dotenv import load_dotenv

load_dotenv()

# API Keys
BINANCE_API_KEY = os.getenv("BINANCE_API_KEY", "")
BINANCE_SECRET_KEY = os.getenv("BINANCE_SECRET_KEY", "")
BINANCE_TESTNET = os.getenv("BINANCE_TESTNET", "true").lower() == "true"
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

# Strategy Parameters
SYMBOL = "BTCUSDT"
TIMEFRAME = "1m"
TIMEFRAME_HTF = "5m"

# Risk Management
MAX_DAILY_DRAWDOWN_PCT = 0.05
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
BOLLINGER_STD = 2.0
RSI_PERIOD = 14
RSI_OVERSOLD = 30
RSI_OVERBOUGHT = 70
