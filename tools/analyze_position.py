"""
analyze_position.py
Mengambil posisi terbuka Binance Futures secara real-time dan meminta
analisa komprehensif dari DeepSeek AI (SMC + Price Action + Multi-TF).
"""
import os, asyncio, json
from dotenv import load_dotenv
from binance import AsyncClient
from openai import AsyncOpenAI
import pandas as pd

# ── Hitung Indikator Sederhana ─────────────────────────────────────────────
def calc_indicators(klines_raw):
    df = pd.DataFrame(klines_raw, columns=[
        'ts','open','high','low','close','volume',
        'close_time','qav','trades','tbbav','tbqav','ignore'
    ])
    df = df[['ts','open','high','low','close','volume']].astype({
        'open': float, 'high': float, 'low': float,
        'close': float, 'volume': float
    })

    # RSI 14
    delta = df['close'].diff()
    gain  = delta.clip(lower=0).rolling(14).mean()
    loss  = (-delta.clip(upper=0)).rolling(14).mean()
    rs    = gain / loss.replace(0, 1e-9)
    df['rsi'] = (100 - 100 / (1 + rs)).round(2)

    # EMA 50 & EMA 200
    df['ema_50']  = df['close'].ewm(span=50,  adjust=False).mean().round(2)
    df['ema_200'] = df['close'].ewm(span=200, adjust=False).mean().round(2)

    # Bollinger Bands 20/2
    df['bb_mid'] = df['close'].rolling(20).mean()
    df['bb_std'] = df['close'].rolling(20).std()
    df['bb_low'] = (df['bb_mid'] - 2 * df['bb_std']).round(2)
    df['bb_high']= (df['bb_mid'] + 2 * df['bb_std']).round(2)
    df['bb_mid'] = df['bb_mid'].round(2)

    # ATR 14
    df['tr'] = pd.concat([
        df['high'] - df['low'],
        (df['high'] - df['close'].shift()).abs(),
        (df['low']  - df['close'].shift()).abs()
    ], axis=1).max(axis=1)
    df['atr'] = df['tr'].rolling(14).mean().round(2)

    # VWAP (Daily Reset via date)
    df['date'] = pd.to_datetime(df['ts'], unit='ms', utc=True).dt.date
    today = df['date'].iloc[-1]
    today_df = df[df['date'] == today].copy()
    today_df['tp'] = (today_df['high'] + today_df['low'] + today_df['close']) / 3
    today_df['vwap'] = (today_df['tp'] * today_df['volume']).cumsum() / today_df['volume'].cumsum()
    df = df.merge(today_df[['ts','vwap']], on='ts', how='left')
    df['vwap'] = df['vwap'].ffill().round(2)

    return df

def candle_summary(df, n=10):
    """Ambil ringkasan n candle terakhir untuk prompt."""
    cols = ['open','high','low','close','volume','rsi','ema_50','ema_200','vwap','bb_low','bb_high','atr']
    return df.tail(n)[cols].round(2).to_dict(orient='records')

# ── Main ───────────────────────────────────────────────────────────────────
async def main():
    load_dotenv()
    BINANCE_KEY    = os.getenv("BINANCE_API_KEY")
    BINANCE_SECRET = os.getenv("BINANCE_SECRET_KEY")
    DEEPSEEK_KEY   = os.getenv("DEEPSEEK_API_KEY")
    TESTNET        = os.getenv("BINANCE_TESTNET", "true").lower() == "true"
    SYMBOL         = "BTCUSDT"

    # ── Ambil Data Binance ────────────────────────────────────────────────
    print("📡 Menghubungi Binance...")
    client = await AsyncClient.create(api_key=BINANCE_KEY, api_secret=BINANCE_SECRET, testnet=TESTNET)

    # Posisi terbuka
    positions = await client.futures_position_information(symbol=SYMBOL)
    active = [p for p in positions if float(p.get('positionAmt', 0)) != 0]

    if not active:
        print("ℹ️  Tidak ada posisi terbuka untuk BTCUSDT saat ini.")
        await client.close_connection()
        return

    pos = active[0]
    pos_amt    = float(pos['positionAmt'])
    entry      = float(pos['entryPrice'])
    mark       = float(pos['markPrice'])
    pnl        = float(pos['unRealizedProfit'])
    leverage   = int(pos.get('leverage', 1))
    direction  = "LONG" if pos_amt > 0 else "SHORT"
    pnl_pct    = ((mark - entry) / entry * 100) if direction == "LONG" else ((entry - mark) / entry * 100)

    # Open orders (SL/TP)
    orders = await client.futures_get_open_orders(symbol=SYMBOL)
    sl_levels, tp_levels = [], []
    for o in orders:
        if o['type'] == 'STOP_MARKET':
            sl_levels.append(float(o['stopPrice']))
        elif o['type'] in ['TAKE_PROFIT_MARKET', 'TAKE_PROFIT']:
            tp_levels.append(float(o.get('stopPrice') or o.get('price')))

    # Multi-timeframe klines
    print("📊 Mengambil data multi-timeframe (15m, 1H, 4H)...")
    kl_15m = await client.futures_klines(symbol=SYMBOL, interval="15m", limit=220)
    kl_1h  = await client.futures_klines(symbol=SYMBOL, interval="1h",  limit=100)
    kl_4h  = await client.futures_klines(symbol=SYMBOL, interval="4h",  limit=60)

    await client.close_connection()

    df_15m = calc_indicators(kl_15m)
    df_1h  = calc_indicators(kl_1h)
    df_4h  = calc_indicators(kl_4h)

    cur_15m = df_15m.iloc[-1]
    cur_1h  = df_1h.iloc[-1]
    cur_4h  = df_4h.iloc[-1]

    # ── Susun Prompt ──────────────────────────────────────────────────────
    print("🤖 Mengirim ke DeepSeek AI untuk analisa komprehensif...\n")

    sl_str = f"{sl_levels[0]:,.1f}" if sl_levels else "TIDAK TERPASANG ⚠️"
    tp_str = f"{tp_levels[0]:,.1f}" if tp_levels else "TIDAK TERPASANG ⚠️"

    prompt = f"""Anda adalah Kepala Riset di hedge fund kripto institusional.
Seorang trader meminta Anda untuk menganalisa dan memberikan REKOMENDASI KONKRET
atas posisi yang sedang terbuka berikut ini.

═══════════════════════════════════════════
  DETAIL POSISI AKTIF
═══════════════════════════════════════════
Aset       : BTC/USDT Perpetual Futures
Arah       : {direction}
Jumlah     : {abs(pos_amt):.3f} BTC
Leverage   : {leverage}x
Entry Price: {entry:,.2f} USDT
Mark Price : {mark:,.2f} USDT
PnL Float  : {pnl:+.4f} USDT ({pnl_pct:+.2f}%)
Stop Loss  : {sl_str}
Take Profit: {tp_str}

═══════════════════════════════════════════
  SNAPSHOT INDIKATOR MULTI-TIMEFRAME
═══════════════════════════════════════════

▶ TIMEFRAME 4 JAM (Tren Jangka Menengah)
  Close   : {cur_4h['close']:,.2f} | RSI: {cur_4h['rsi']}
  EMA 50  : {cur_4h['ema_50']:,.2f} | EMA 200: {cur_4h['ema_200']:,.2f}
  BB Low  : {cur_4h['bb_low']:,.2f} | BB High: {cur_4h['bb_high']:,.2f}
  VWAP    : {cur_4h['vwap']:,.2f}  | ATR: {cur_4h['atr']:,.2f}

▶ TIMEFRAME 1 JAM (Tren Jangka Pendek)
  Close   : {cur_1h['close']:,.2f} | RSI: {cur_1h['rsi']}
  EMA 50  : {cur_1h['ema_50']:,.2f} | EMA 200: {cur_1h['ema_200']:,.2f}
  BB Low  : {cur_1h['bb_low']:,.2f} | BB High: {cur_1h['bb_high']:,.2f}
  VWAP    : {cur_1h['vwap']:,.2f}  | ATR: {cur_1h['atr']:,.2f}

▶ TIMEFRAME 15 MENIT (Entry/Exit Timing)
  Close   : {cur_15m['close']:,.2f} | RSI: {cur_15m['rsi']}
  EMA 50  : {cur_15m['ema_50']:,.2f} | EMA 200: {cur_15m['ema_200']:,.2f}
  BB Low  : {cur_15m['bb_low']:,.2f} | BB High: {cur_15m['bb_high']:,.2f}
  VWAP    : {cur_15m['vwap']:,.2f}  | ATR: {cur_15m['atr']:,.2f}

▶ 10 CANDLE TERAKHIR (15 MENIT) — Untuk Price Action
{json.dumps(candle_summary(df_15m, 10), indent=2)}

═══════════════════════════════════════════
  TUGAS ANDA
═══════════════════════════════════════════
Berikan analisa KOMPREHENSIF yang mencakup:
1. **Kesehatan Posisi**: Apakah posisi ini masih valid secara teknikal?
2. **Analisa Multi-TF**: Apa yang dikatakan 4H, 1H, dan 15m secara bersamaan?
3. **Risiko Skenario Terburuk**: Apa yang harus diwaspadai?
4. **Rekomendasi Aksi Konkret**: Pilih salah satu dan jelaskan mengapa:
   - HOLD (tahan tanpa perubahan)
   - ADJUST SL/TP (geser ke level berapa, dan mengapa)
   - PARTIAL CLOSE (tutup berapa persen, dan mengapa)
   - FULL CLOSE (tutup semua, dan mengapa)

Jawab dengan bahasa Indonesia yang jelas, ringkas, dan to-the-point (maksimal 4 paragraf).
"""

    ai = AsyncOpenAI(api_key=DEEPSEEK_KEY, base_url="https://api.deepseek.com/v1")
    resp = await ai.chat.completions.create(
        model="deepseek-chat",
        messages=[
            {"role": "system", "content": "Anda adalah kepala riset hedge fund kripto yang objektif dan memberikan saran trading berdasarkan data teknikal murni."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.3
    )

    answer = resp.choices[0].message.content

    # Simpan & tampilkan
    out_file = "position_analysis.txt"
    with open(out_file, "w", encoding="utf-8") as f:
        f.write(f"=== ANALISA POSISI {direction} BTC/USDT ===\n")
        f.write(f"Entry: {entry:,.2f} | Mark: {mark:,.2f} | PnL: {pnl:+.4f} USDT\n")
        f.write(f"SL: {sl_str} | TP: {tp_str}\n\n")
        f.write(answer)

    print("═" * 60)
    print(f"  ANALISA DEEPSEEK — POSISI {direction} BTC/USDT")
    print("═" * 60)
    print(answer)
    print("═" * 60)
    print(f"\n✅ Hasil tersimpan di: {out_file}")

if __name__ == "__main__":
    asyncio.run(main())
