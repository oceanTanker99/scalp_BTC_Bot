import os
from dotenv import load_dotenv

load_dotenv()

# API Keys
BINANCE_API_KEY = os.getenv("BINANCE_API_KEY", "")
BINANCE_SECRET_KEY = os.getenv("BINANCE_SECRET_KEY", "")
AI_API_KEY = os.getenv("AI_API_KEY") or os.getenv("DEEPSEEK_API_KEY") or os.getenv("9ROUTER_API_KEY", "")
BINANCE_TESTNET = os.getenv("BINANCE_TESTNET", "true").lower() == "true"
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_IDS = [x.strip() for x in os.getenv("TELEGRAM_CHAT_ID", "").split(",") if x.strip()]

# Strategy Parameters
SYMBOL = "BTCUSDT"

# Trading Sessions (UTC Time)
TRADE_START_HOUR_UTC = 0   # 00:00 UTC (Buka 24 Jam)
TRADE_END_HOUR_UTC = 24    # 24:00 UTC (Tutup 24 Jam)

# Risk Management
MAX_DAILY_DRAWDOWN_PCT = 0.08  # Max 8% drawdown harian
TRADE_RISK_PCT = 0.05  # Risk 5% per trade
LEVERAGE = 20  # Diturunkan dari 60x (audit: risiko likuidasi terlalu tinggi)

# TP/SL Targets (Risk:Reward Ratio)
RRR_TP1 = 2.0 # Take Profit (1:2 RRR)x SL distance

# Indicators - Bollinger Bands
BOLLINGER_PERIOD = 20
BOLLINGER_STD = 2.0   # Dilonggarkan dari 2.5 → 2.0 agar lebih sering menyentuh band

# Indicators - RSI
RSI_PERIOD = 7
RSI_OVERSOLD = 25    # Diperketat (ML DeepSeek: WR naik tajam jika < 25)
RSI_OVERBOUGHT = 75  # Diperketat (ML DeepSeek: WR naik tajam jika > 75)

# Advanced Filters & Dynamic SL
ATR_PERIOD = 14
ATR_MULTIPLIER = 3.0
EMA_MTF_PERIOD = 200          # EMA 200 di 15m sebagai filter tren makro
ADX_PERIOD = 14
ADX_THRESHOLD = 30            # Maksimal tren untuk Mean-Reversion (ML DeepSeek)
STRONG_TREND_ADX = 55         # Tsunami Trend untuk Trend-Following (ML DeepSeek WR 71%)

# BB Squeeze Detection (Hindari masuk saat konsolidasi sempit)
MIN_BB_WIDTH_MR = 0.005  # 0.5% (ML DeepSeek: WR hancur jika di bawah ini)
MIN_BB_WIDTH_TF = 0.030  # 3.0% (ML DeepSeek: WR 71% jika volatility meledak)

# Signal Scoring System
# OFI: tidak lagi wajib, tapi berkontribusi ke skor
OFI_BOOST_THRESHOLD = 0.10   # OFI di atas threshold ini menambah 1 poin skor

# Volume Spike (Konfirmasi Kepanikan/Keserakahan)
VOLUME_SPIKE_MULTIPLIER = 1.5  # Volume harus 1.5x rata-rata untuk bonus skor

# Minimum Signal Score untuk eksekusi (dari total maks 5 poin)
MIN_SIGNAL_SCORE = 3

# Trailing Stop / Break Even
BREAK_EVEN_TRIGGER_PCT = 0.003  # Pindah SL ke titik impas jika profit > 0.3% (leverage lebih rendah = trigger lebih cepat)

# Cooldown pasca trade (dalam jumlah candle 5m, 1 candle = 5 menit)
COOLDOWN_CANDLES = 3  # Jeda 15 menit setelah trade selesai

# --- Validasi Startup ---
def validate_config():
    """Validasi konfigurasi wajib saat bot dimulai."""
    errors = []
    if not BINANCE_API_KEY:
        errors.append("BINANCE_API_KEY tidak diset di .env")
    if not BINANCE_SECRET_KEY:
        errors.append("BINANCE_SECRET_KEY tidak diset di .env")
    if not AI_API_KEY:
        errors.append("AI_API_KEY tidak diset di .env (AI Validator tidak akan berfungsi)")
    if not TELEGRAM_BOT_TOKEN:
        errors.append("TELEGRAM_BOT_TOKEN tidak diset di .env")
    if not TELEGRAM_CHAT_IDS:
        errors.append("TELEGRAM_CHAT_ID tidak diset di .env")
    
    if errors:
        for e in errors:
            print(f"❌ CONFIG ERROR: {e}")
        # Hanya raise jika API key exchange kosong (kritis untuk trading)
        if not BINANCE_API_KEY or not BINANCE_SECRET_KEY:
            raise ValueError("Konfigurasi Binance API wajib diisi! Cek file .env")
