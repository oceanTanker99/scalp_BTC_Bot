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

# Trading Sessions (UTC Time)
TRADE_START_HOUR_UTC = 8   # 08:00 UTC (Awal London Session)
TRADE_END_HOUR_UTC = 21    # 21:00 UTC (Akhir New York Session)

# Risk Management
MAX_DAILY_DRAWDOWN_PCT = 0.20
TRADE_RISK_PCT = 0.01  # Risk 1% per trade
LEVERAGE = 20

# TP/SL Targets (Risk:Reward Ratio)
RRR_TP1 = 1.5   # TP1 = 1.5x SL distance

# Indicators - Bollinger Bands
BOLLINGER_PERIOD = 20
BOLLINGER_STD = 2.0   # Dilonggarkan dari 2.5 → 2.0 agar lebih sering menyentuh band

# Indicators - RSI
RSI_PERIOD = 7
RSI_OVERSOLD = 30    # Dilonggarkan dari 20 → 30 (lebih realistis di 5m)
RSI_OVERBOUGHT = 70  # Dilonggarkan dari 80 → 70 (lebih realistis di 5m)

# Advanced Filters & Dynamic SL
ATR_PERIOD = 14
ATR_MULTIPLIER = 1.5
EMA_MTF_PERIOD = 200          # EMA 200 di 15m sebagai filter tren makro
ADX_PERIOD = 14
ADX_THRESHOLD = 30            # Dinaikkan dari 25 → 30 agar lebih toleran

# Signal Scoring System
# OFI: tidak lagi wajib, tapi berkontribusi ke skor
OFI_BOOST_THRESHOLD = 0.10   # OFI di atas threshold ini menambah 1 poin skor

# Volume Spike (Konfirmasi Kepanikan/Keserakahan)
VOLUME_SPIKE_MULTIPLIER = 1.5  # Volume harus 1.5x rata-rata untuk bonus skor

# BB Squeeze Detection (Hindari masuk saat konsolidasi sempit)
# BB Width = (BBH - BBL) / Price. Jika < threshold, pasar sedang squeeze
BB_SQUEEZE_THRESHOLD = 0.015  # 1.5% — di bawah ini dianggap squeeze, skip entry

# Minimum Signal Score untuk eksekusi (dari total maks 5 poin)
# Breakdown: BB_touch(2) + EMA200_trend(1) + OFI_boost(1) + Volume_spike(1)
MIN_SIGNAL_SCORE = 3

# Cooldown pasca trade (dalam jumlah candle 5m, 1 candle = 5 menit)
COOLDOWN_CANDLES = 3  # Jeda 15 menit setelah trade selesai
