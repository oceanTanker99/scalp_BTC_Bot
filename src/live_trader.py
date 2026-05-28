import logging
import asyncio
from binance import AsyncClient
from binance.exceptions import BinanceAPIException
from config.config import (
    BINANCE_API_KEY, BINANCE_SECRET_KEY, BINANCE_TESTNET, SYMBOL,
    TRADE_RISK_PCT, LEVERAGE, RRR_TP1, MAX_DAILY_DRAWDOWN_PCT,
    BREAK_EVEN_TRIGGER_PCT
)

log = logging.getLogger(__name__)

# --- Konfigurasi Chasing Limit Order ---
CHASE_MAX_ATTEMPTS = 3       # Maksimum percobaan re-place order
CHASE_WAIT_SECONDS = 5       # Tunggu per percobaan sebelum cek status
CHASE_OFFSET_PCT = 0.0003    # Offset harga 0.03% ke arah pasar setiap percobaan


class LiveTrader:
    def __init__(self, client: AsyncClient = None):
        """
        Args:
            client: Instance AsyncClient Binance yang sudah diinisialisasi.
                    Jika None, akan dibuat di initialize().
        """
        self.client = client
        self.start_balance = 0.0
        self._notifier = None  # Diisi oleh main.py
        self.is_killed = False  # Flag kill switch — aktif = berhenti trading hari ini

    async def initialize(self):
        if self.client is None:
            self.client = await AsyncClient.create(
                BINANCE_API_KEY, BINANCE_SECRET_KEY, testnet=BINANCE_TESTNET
            )
        await self._set_leverage()
        self.start_balance = await self.get_balance()
        log.info(f"Live Trader diinisialisasi. Saldo awal: {self.start_balance} USDT")

    async def _set_leverage(self):
        try:
            await self.client.futures_change_leverage(symbol=SYMBOL, leverage=LEVERAGE)
        except Exception:
            pass
        try:
            await self.client.futures_change_margin_type(symbol=SYMBOL, marginType='ISOLATED')
        except Exception:
            pass  # Abaikan jika sudah ISOLATED

    async def get_balance(self) -> float:
        try:
            res = await self.client.futures_account_balance()
            usdt = next((item for item in res if item['asset'] == 'USDT'), None)
            return float(usdt['balance']) if usdt else 0.0
        except Exception as e:
            log.error(f"Gagal mengambil saldo: {e}")
            return 0.0

    async def has_open_position(self) -> bool:
        """Cek posisi nyata dari Binance API."""
        try:
            positions = await self.client.futures_position_information(symbol=SYMBOL)
            for pos in positions:
                if float(pos.get('positionAmt', 0)) != 0:
                    return True
            return False
        except Exception as e:
            log.error(f"Gagal mengecek posisi: {e}")
            return True  # Failsafe: anggap ada posisi jika API error

    async def check_kill_switch(self) -> bool:
        """
        Cek apakah drawdown harian melebihi batas.
        Jika ya, aktifkan flag is_killed dan kirim notifikasi.
        """
        if self.is_killed:
            return True

        if self.start_balance <= 0:
            return False

        current_balance = await self.get_balance()
        drawdown = (self.start_balance - current_balance) / self.start_balance

        if drawdown >= MAX_DAILY_DRAWDOWN_PCT:
            self.is_killed = True
            log.error(
                f"🚨 KILL SWITCH AKTIF! Drawdown {drawdown:.2%} melebihi batas {MAX_DAILY_DRAWDOWN_PCT:.0%}. "
                f"Bot berhenti trading hari ini."
            )
            if self._notifier:
                await self._notifier.notify_kill_switch(drawdown, current_balance)
            return True

        return False

    async def execute_trade(self, signal: str, current_price: float, sl_distance: float):
        """
        Eksekusi Chasing Limit Order dan pasang SL/TP.

        Strategi Chasing:
        1. Tempatkan limit order sedikit lebih agresif dari harga saat ini
        2. Tunggu CHASE_WAIT_SECONDS, cek apakah terisi
        3. Jika belum, cancel dan re-place dengan harga yang lebih agresif
        4. Ulangi hingga CHASE_MAX_ATTEMPTS kali

        Returns:
            (sl_price, tp_price, qty) jika berhasil, atau (None, None, None) jika gagal.
        """
        if await self.check_kill_switch():
            return None, None, None

        balance = await self.get_balance()
        risk_amount = balance * TRADE_RISK_PCT

        sl_pct = sl_distance
        if sl_pct <= 0:
            log.error("sl_pct nol atau negatif, trade dibatalkan.")
            return None, None, None

        # Hitung kuantitas berdasarkan risiko: risk_amount = qty * price * sl_pct
        qty = risk_amount / (current_price * sl_pct)
        qty = round(qty, 3)
        if qty < 0.001:
            qty = 0.001

        side = 'BUY' if signal == 'LONG' else 'SELL'
        sl_side = 'SELL' if signal == 'LONG' else 'BUY'

        # Hitung level SL dan TP
        if signal == 'LONG':
            sl_price = round(current_price * (1 - sl_pct), 1)
            tp_price = round(current_price * (1 + (sl_pct * RRR_TP1)), 1)
        else:
            sl_price = round(current_price * (1 + sl_pct), 1)
            tp_price = round(current_price * (1 - (sl_pct * RRR_TP1)), 1)

        try:
            # --- Chasing Limit Order ---
            filled = False
            final_order = None

            for attempt in range(1, CHASE_MAX_ATTEMPTS + 1):
                # Ambil Best Bid/Ask terbaru agar Post-Only (GTX) pasti diterima
                ob_ticker = await self.client.futures_orderbook_ticker(symbol=SYMBOL)
                if signal == 'LONG':
                    limit_price = float(ob_ticker['bidPrice'])
                else:
                    limit_price = float(ob_ticker['askPrice'])

                log.info(
                    f"📤 Percobaan {attempt}/{CHASE_MAX_ATTEMPTS} — "
                    f"Menempatkan {side} LIMIT (Post-Only) @ {limit_price} | Qty: {qty}"
                )

                entry_order = await self.client.futures_create_order(
                    symbol=SYMBOL,
                    side=side,
                    type='LIMIT',
                    quantity=qty,
                    price=limit_price,
                    timeInForce='GTX'  # GTX = Post-Only
                )
                order_id = entry_order['orderId']

                log.info(f"⏳ Menunggu {CHASE_WAIT_SECONDS} detik agar order (ID: {order_id}) terisi...")
                await asyncio.sleep(CHASE_WAIT_SECONDS)

                # Cek status order
                order_status = await self.client.futures_get_order(symbol=SYMBOL, orderId=order_id)

                if order_status['status'] == 'FILLED':
                    filled = True
                    final_order = order_status
                    log.info(f"✅ Limit order terisi di percobaan {attempt}!")
                    break
                else:
                    log.warning(
                        f"⚠️ Order belum terisi (status: {order_status['status']}). "
                        f"Membatalkan order ID: {order_id}..."
                    )
                    try:
                        await self.client.futures_cancel_order(symbol=SYMBOL, orderId=order_id)
                    except BinanceAPIException:
                        pass  # Order mungkin sudah expired/canceled

            if not filled:
                log.warning(f"❌ Gagal mengisi order setelah {CHASE_MAX_ATTEMPTS} percobaan. Trade dibatalkan.")
                return None, None, None

            # --- Pasang SL & TP setelah entry terisi ---
            log.info("🛡️ Memasang perlindungan Stop Loss dan Take Profit...")

            # Stop Loss
            await self.client.futures_create_order(
                symbol=SYMBOL,
                side=sl_side,
                type='STOP_MARKET',
                stopPrice=sl_price,
                closePosition=True,
                timeInForce='GTE_GTC'
            )

            # Take Profit
            await self.client.futures_create_order(
                symbol=SYMBOL,
                side=sl_side,
                type='TAKE_PROFIT_MARKET',
                stopPrice=tp_price,
                closePosition=True,
                timeInForce='GTE_GTC'
            )

            actual_entry = float(final_order.get('avgPrice', limit_price))
            log.info(
                f"✅ Trade berhasil! Entry: {actual_entry}, SL: {sl_price}, TP: {tp_price}"
            )
            return sl_price, tp_price, qty

        except BinanceAPIException as e:
            log.error(f"Binance API Error saat eksekusi trade: {e}")
            return None, None, None
        except Exception as e:
            log.error(f"Error saat eksekusi trade: {e}")
            return None, None, None

    async def manage_trailing_stop(self):
        """
        Pindahkan Stop Loss ke Break Even jika posisi sudah untung
        lebih dari BREAK_EVEN_TRIGGER_PCT.
        """
        try:
            positions = await self.client.futures_position_information(symbol=SYMBOL)
            active = [p for p in positions if float(p.get('positionAmt', 0)) != 0]
            if not active:
                return

            pos = active[0]
            entry_price = float(pos['entryPrice'])
            mark_price = float(pos['markPrice'])
            qty = float(pos['positionAmt'])
            direction = "LONG" if qty > 0 else "SHORT"

            if direction == "LONG":
                pnl_pct = (mark_price - entry_price) / entry_price
            else:
                pnl_pct = (entry_price - mark_price) / entry_price

            if pnl_pct >= BREAK_EVEN_TRIGGER_PCT:
                orders = await self.client.futures_get_open_orders(symbol=SYMBOL)
                sl_orders = [o for o in orders if o['type'] == 'STOP_MARKET']
                if not sl_orders:
                    return

                sl_order = sl_orders[0]
                current_sl = float(sl_order['stopPrice'])

                needs_move = False
                if direction == "LONG" and current_sl < entry_price:
                    needs_move = True
                elif direction == "SHORT" and current_sl > entry_price:
                    needs_move = True

                if needs_move:
                    log.info(f"🛡️ Menggeser SL ke Break Even ({entry_price})...")
                    try:
                        await self.client.futures_cancel_order(symbol=SYMBOL, orderId=sl_order['orderId'])
                    except Exception as e:
                        log.error(f"Gagal membatalkan SL lama: {e}")
                        return
                    
                    side = "SELL" if direction == "LONG" else "BUY"
                    try:
                        await self.client.futures_create_order(
                            symbol=SYMBOL, side=side, type="STOP_MARKET",
                            stopPrice=round(entry_price, 1), closePosition="true", timeInForce="GTE_GTC"
                        )
                        log.info(f"🛡️ Trailing Stop aktif! SL dipindah ke {round(entry_price, 1)}")
                        if self._notifier:
                            await self._notifier.notify_info(
                                f"🛡️ <b>Trailing Stop Aktif!</b>\n"
                                f"Profit mencapai > {BREAK_EVEN_TRIGGER_PCT*100}%. "
                                f"SL telah dipindah ke titik impas: <code>{round(entry_price, 1):,.1f}</code>"
                            )
                    except Exception as e:
                        log.error(f"🚨 FATAL: Gagal membuat SL baru di {entry_price}: {e}. Mencoba mengembalikan SL lama...")
                        try:
                            # Coba pasang ulang SL lama sebagai jaring pengaman terakhir
                            await self.client.futures_create_order(
                                symbol=SYMBOL, side=side, type="STOP_MARKET",
                                stopPrice=current_sl, closePosition="true", timeInForce="GTE_GTC"
                            )
                            log.info("🛡️ SL lama berhasil dipulihkan.")
                        except Exception as e2:
                            log.error(f"🚨🚨 KRITIKAL: Gagal memulihkan SL lama: {e2}. POSISI SAAT INI TANPA STOP LOSS!")
        except Exception as e:
            log.error(f"Error di manage_trailing_stop: {e}")
