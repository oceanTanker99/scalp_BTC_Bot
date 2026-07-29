import logging
import asyncio
import time
import os
import csv
import json
from datetime import datetime, timezone
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
CHASE_WAIT_SECONDS = 2       # Tunggu per percobaan sebelum cek status
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
        self._last_logged_trade_id = None
        self._state_file = "data/kill_switch_state.json"
        self._load_persistent_state()

    # --- Persistent Kill Switch State ---
    def _load_persistent_state(self):
        """Load kill switch state from disk to survive restarts."""
        try:
            if os.path.exists(self._state_file):
                with open(self._state_file, "r") as f:
                    state = json.load(f)
                saved_date = state.get("date", "")
                today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
                if saved_date == today:
                    self.start_balance = state.get("start_balance", 0.0)
                    self.is_killed = state.get("is_killed", False)
                    log.info(f"♻️ State dipulihkan: start_balance={self.start_balance}, killed={self.is_killed}")
        except Exception as e:
            log.error(f"Gagal memuat state kill switch: {e}")

    def _save_persistent_state(self):
        """Save kill switch state to disk."""
        try:
            os.makedirs("data", exist_ok=True)
            state = {
                "date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                "start_balance": self.start_balance,
                "is_killed": self.is_killed
            }
            with open(self._state_file, "w") as f:
                json.dump(state, f)
        except Exception as e:
            log.error(f"Gagal menyimpan state kill switch: {e}")

    async def _get_all_open_orders(self):
        orders = []
        try:
            std = await self.client.futures_get_open_orders(symbol=SYMBOL)
            orders.extend(std)
        except Exception:
            pass
        try:
            algo = await self.client._request_futures_api('get', 'openAlgoOrders', signed=True, data={'symbol': SYMBOL})
            if isinstance(algo, list):
                for ao in algo:
                    ao['type'] = ao.get('orderType', ao.get('type'))
                    ao['stopPrice'] = ao.get('triggerPrice', ao.get('stopPrice'))
                    ao['orderId'] = ao.get('algoId', ao.get('orderId'))
                    ao['is_algo'] = True
                    orders.append(ao)
        except Exception:
            pass
        return orders

    async def _cancel_order(self, order):
        if order.get('is_algo'):
            await self.client._request_futures_api('delete', 'algoOrder', signed=True, data={'symbol': SYMBOL, 'algoId': order['orderId']})
        else:
            await self.client.futures_cancel_order(symbol=SYMBOL, orderId=order['orderId'])

    async def sync_time(self):
        # Sync time with Binance Server to prevent Timestamp APIError (-1021)
        try:
            res = await self.client.futures_time()
            server_time = res['serverTime']
            local_time = int(time.time() * 1000)
            # Berikan buffer mundur 1000ms agar timestamp kita tidak pernah mendahului waktu server (ahead of server time).
            # Binance menerima timestamp hingga 5000ms di masa lalu (recvWindow default).
            self.client.timestamp_offset = (server_time - local_time) - 1000
            log.info(f"Waktu disinkronkan. Offset: {self.client.timestamp_offset} ms")
        except Exception as e:
            log.error(f"Gagal sinkronisasi waktu Binance: {e}")

    async def initialize(self):
        if self.client is None:
            self.client = await AsyncClient.create(
                BINANCE_API_KEY, BINANCE_SECRET_KEY, testnet=BINANCE_TESTNET
            )
        
        await self.sync_time()

        await self._set_leverage()
        if self.start_balance <= 0:
            self.start_balance = await self.get_balance()
        self._save_persistent_state()
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

    async def get_active_position_details(self) -> str:
        """Mengambil detail posisi aktif dan order terbuka untuk Telegram."""
        try:
            positions = await self.client.futures_position_information(symbol=SYMBOL)
            msg = ""
            has_position = False
            for pos in positions:
                amt = float(pos.get('positionAmt', 0))
                if amt != 0:
                    has_position = True
                    side = "LONG 🟢" if amt > 0 else "SHORT 🔴"
                    entry = float(pos.get('entryPrice', 0))
                    mark = float(pos.get('markPrice', 0))
                    unrealized_pnl = float(pos.get('unRealizedProfit', 0))
                    leverage = pos.get('leverage', LEVERAGE)
                    
                    margin_used = (abs(amt) * entry) / float(leverage)
                    roi_pct = (unrealized_pnl / margin_used * 100) if margin_used > 0 else 0
                    
                    msg += (
                        f"📊 <b>POSISI AKTIF: {SYMBOL}</b>\n"
                        f"━━━━━━━━━━━━━━━━\n"
                        f"Arah : {side}\n"
                        f"Size : <code>{abs(amt)}</code> BTC\n"
                        f"Entry: <code>{entry:,.1f}</code> USDT\n"
                        f"Mark : <code>{mark:,.1f}</code> USDT\n"
                        f"PnL  : <code>{unrealized_pnl:+.2f}</code> USDT (<b>{roi_pct:+.2f}%</b>)\n"
                        f"Lev  : {leverage}x\n\n"
                    )

            orders = await self._get_all_open_orders()
            if orders:
                msg += f"📝 <b>PROTEKSI (SL/TP)</b>\n━━━━━━━━━━━━━━━━\n"
                sl_found = False
                tp_found = False
                for o in orders:
                    o_type = o.get('type', '')
                    o_stop_price = float(o.get('stopPrice', 0))
                    
                    if o_type == 'STOP_MARKET':
                        msg += f"🛑 Stop Loss   : <code>{o_stop_price:,.1f}</code> USDT\n"
                        sl_found = True
                    elif o_type == 'TAKE_PROFIT_MARKET':
                        msg += f"🎯 Take Profit : <code>{o_stop_price:,.1f}</code> USDT\n"
                        tp_found = True
                        
                if not sl_found and not tp_found:
                    msg += "⚠️ <i>Tidak ada SL/TP yang terpasang! (Hanya Limit Entry)</i>\n"
            else:
                if not has_position:
                    return "✅ <b>STATUS AMAN</b>\nSaat ini tidak ada posisi terbuka atau limit order aktif."

            if not msg:
                return "✅ <b>STATUS AMAN</b>\nSaat ini tidak ada posisi terbuka atau limit order aktif."

            return msg.strip()
        except Exception as e:
            log.error(f"Gagal mengambil detail posisi: {e}")
            return f"❌ <b>ERROR API</b>\nGagal mengambil posisi dan order:\n<code>{e}</code>"

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
            self._save_persistent_state()
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
            log.warning(f"⚠️ Qty terlalu kecil ({qty:.6f} BTC < 0.001 minimum). Trade dibatalkan demi menjaga risk management.")
            return None, None, None

        # [AUDIT FIX] Validasi margin sebelum eksekusi
        required_margin = (qty * current_price) / LEVERAGE
        if required_margin > balance * 0.9:  # Sisakan 10% buffer margin
            log.warning(
                f"⚠️ Margin tidak cukup! Required: {required_margin:.2f} USDT, "
                f"Available: {balance:.2f} USDT. Trade dibatalkan."
            )
            return None, None, None

        side = 'BUY' if signal == 'LONG' else 'SELL'
        sl_side = 'SELL' if signal == 'LONG' else 'BUY'

        # [AUDIT P3] Fee-awareness: pastikan expected profit > biaya trading
        # Binance Futures fee: 0.02% maker per side = 0.04% round-trip
        ROUND_TRIP_FEE_PCT = 0.0004  # 0.04%
        expected_tp_distance = sl_pct * RRR_TP1  # Jarak TP sebagai fraksi harga
        if expected_tp_distance <= ROUND_TRIP_FEE_PCT * 1.5:  # Profit harus > 1.5x fee
            log.warning(
                f"⚠️ Expected TP ({expected_tp_distance*100:.3f}%) terlalu kecil vs fee "
                f"({ROUND_TRIP_FEE_PCT*100:.3f}%). Trade tidak profitable, dibatalkan."
            )
            return None, None, None

        # Hitung level SL dan TP
        if signal == 'LONG':
            sl_price = round(current_price * (1 - sl_pct), 1)
            tp_price = round(current_price * (1 + (sl_pct * RRR_TP1)), 1)
        else:
            sl_price = round(current_price * (1 + sl_pct), 1)
            tp_price = round(current_price * (1 - (sl_pct * RRR_TP1)), 1)

        # --- Chasing Limit Order ---
        filled = False
        final_order = None

        for attempt in range(1, CHASE_MAX_ATTEMPTS + 1):
            try:
                # Ambil Best Bid/Ask terbaru agar Post-Only (GTX) pasti diterima
                ob_ticker = await self.client.futures_orderbook_ticker(symbol=SYMBOL)
                if signal == 'LONG':
                    limit_price = round(float(ob_ticker['bidPrice']) * (1 + CHASE_OFFSET_PCT * attempt), 1)
                else:
                    limit_price = round(float(ob_ticker['askPrice']) * (1 - CHASE_OFFSET_PCT * attempt), 1)

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

            except BinanceAPIException as e:
                log.warning(f"⚠️ Binance API Error di percobaan {attempt}: {e}. Mencoba ulang...")
                await asyncio.sleep(1)
                continue
            except Exception as e:
                log.error(f"Error saat eksekusi trade di percobaan {attempt}: {e}")
                return None, None, None

        if not filled:
            log.warning(f"❌ Gagal mengisi order setelah {CHASE_MAX_ATTEMPTS} percobaan. Trade dibatalkan.")
            return None, None, None

        # --- Pasang SL & TP setelah entry terisi ---
        try:
            actual_entry = float(final_order.get('avgPrice', limit_price))

            # Rekalkulasi SL/TP berdasarkan harga entry aktual (bukan estimasi awal)
            if signal == 'LONG':
                sl_price = round(actual_entry * (1 - sl_pct), 1)
                tp_price = round(actual_entry * (1 + (sl_pct * RRR_TP1)), 1)
            else:
                sl_price = round(actual_entry * (1 + sl_pct), 1)
                tp_price = round(actual_entry * (1 - (sl_pct * RRR_TP1)), 1)

            log.info("🛡️ Memasang perlindungan Stop Loss dan Take Profit...")

            # Stop Loss
            await self.client._request_futures_api('post', 'algoOrder', signed=True, data={
                'symbol': SYMBOL,
                'side': sl_side,
                'type': 'STOP_MARKET',
                'algoType': 'CONDITIONAL',
                'triggerPrice': str(sl_price),
                'closePosition': 'TRUE'
            })

            # Take Profit
            await self.client._request_futures_api('post', 'algoOrder', signed=True, data={
                'symbol': SYMBOL,
                'side': sl_side,
                'type': 'TAKE_PROFIT_MARKET',
                'algoType': 'CONDITIONAL',
                'triggerPrice': str(tp_price),
                'closePosition': 'TRUE'
            })

            log.info(
                f"✅ Trade berhasil! Entry: {actual_entry}, SL: {sl_price}, TP: {tp_price}"
            )
            return sl_price, tp_price, qty

        except Exception as e:
            log.error(f"🚨 KRITIS: Entry terisi tapi SL/TP gagal dipasang: {e}. Menjalankan reconciliation...")
            await self.reconcile_protection()
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
                orders = await self._get_all_open_orders()
                sl_orders = [o for o in orders if o['type'] == 'STOP_MARKET']
                if not sl_orders:
                    return

                sl_order = sl_orders[0]
                current_sl = float(sl_order['stopPrice'])

                target_sl = round(entry_price, 1)

                needs_move = False
                if direction == "LONG" and current_sl < target_sl:
                    needs_move = True
                elif direction == "SHORT" and current_sl > target_sl:
                    needs_move = True

                if needs_move:
                    if len(sl_orders) > 0:
                        for sl_order in sl_orders:
                            try:
                                await self._cancel_order(sl_order)
                            except Exception as e:
                                log.error(f"Gagal membatalkan SL lama: {e}")
                                return
                    
                    side = "SELL" if direction == "LONG" else "BUY"
                    try:
                        await self.client._request_futures_api('post', 'algoOrder', signed=True, data={
                            'symbol': SYMBOL, 'side': side, 'type': 'STOP_MARKET', 'algoType': 'CONDITIONAL',
                            'triggerPrice': str(round(entry_price, 1)), 'closePosition': 'TRUE'
                        })
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
                            await self.client._request_futures_api('post', 'algoOrder', signed=True, data={
                                'symbol': SYMBOL, 'side': side, 'type': 'STOP_MARKET', 'algoType': 'CONDITIONAL',
                                'triggerPrice': str(current_sl), 'closePosition': 'TRUE'
                            })
                            log.info("🛡️ SL lama berhasil dipulihkan.")
                        except Exception as e2:
                            log.error(f"🚨🚨 KRITIKAL: Gagal memulihkan SL lama: {e2}. Menutup posisi darurat...")
                            try:
                                await self.client.futures_create_order(
                                    symbol=SYMBOL, side=side, type='MARKET',
                                    reduceOnly='true'
                                )
                                log.info("🚨 Posisi ditutup secara darurat (MARKET ORDER) karena SL gagal dipasang.")
                                if self._notifier:
                                    await self._notifier.notify_error(
                                        "🚨🚨 DARURAT: SL gagal dipasang ulang saat trailing stop!\n"
                                        "Posisi telah DITUTUP PAKSA via Market Order untuk melindungi modal."
                                    )
                            except Exception as e3:
                                log.error(f"🚨🚨🚨 GAGAL TOTAL menutup posisi darurat: {e3}")
                                if self._notifier:
                                    await self._notifier.notify_error(
                                        f"🚨🚨🚨 KRITIS TOTAL: Posisi TANPA SL dan gagal ditutup darurat!\n"
                                        f"SEGERA TUTUP MANUAL DI BINANCE!\nError: {e3}"
                                    )
        except Exception as e:
            log.error(f"Error di manage_trailing_stop: {e}")

    async def reconcile_protection(self):
        """
        [C-1 FIX] Background Safety Net: Jika ada posisi terbuka tanpa SL/TP,
        otomatis pasang proteksi darurat berdasarkan entry price.
        """
        try:
            positions = await self.client.futures_position_information(symbol=SYMBOL)
            active = [p for p in positions if float(p.get('positionAmt', 0)) != 0]
            if not active:
                return

            pos = active[0]
            entry_price = float(pos['entryPrice'])
            qty = float(pos['positionAmt'])
            direction = "LONG" if qty > 0 else "SHORT"
            sl_side = "SELL" if direction == "LONG" else "BUY"

            # Cek apakah sudah ada SL/TP
            orders = await self._get_all_open_orders()
            has_sl = any(o['type'] == 'STOP_MARKET' for o in orders)
            has_tp = any(o['type'] == 'TAKE_PROFIT_MARKET' for o in orders)

            if has_sl and has_tp:
                return  # Proteksi sudah lengkap

            # Pasang proteksi darurat dengan SL 0.5% dan TP 1.0% dari entry
            emergency_sl_pct = 0.005
            emergency_tp_pct = 0.01

            if not has_sl:
                if direction == "LONG":
                    sl_price = round(entry_price * (1 - emergency_sl_pct), 1)
                else:
                    sl_price = round(entry_price * (1 + emergency_sl_pct), 1)

                await self.client._request_futures_api('post', 'algoOrder', signed=True, data={
                    'symbol': SYMBOL, 'side': sl_side, 'type': 'STOP_MARKET', 'algoType': 'CONDITIONAL',
                    'triggerPrice': str(sl_price), 'closePosition': 'TRUE'
                })
                log.warning(f"🚨 RECONCILIATION: SL darurat dipasang @ {sl_price}")
                if self._notifier:
                    await self._notifier.notify_error(
                        f"🚨 RECONCILIATION: Posisi {direction} terdeteksi TANPA Stop Loss!\n"
                        f"SL darurat dipasang otomatis @ {sl_price:,.1f}"
                    )

            if not has_tp:
                if direction == "LONG":
                    tp_price = round(entry_price * (1 + emergency_tp_pct), 1)
                else:
                    tp_price = round(entry_price * (1 - emergency_tp_pct), 1)

                await self.client._request_futures_api('post', 'algoOrder', signed=True, data={
                    'symbol': SYMBOL, 'side': sl_side, 'type': 'TAKE_PROFIT_MARKET', 'algoType': 'CONDITIONAL',
                    'triggerPrice': str(tp_price), 'closePosition': 'TRUE'
                })
                log.warning(f"🚨 RECONCILIATION: TP darurat dipasang @ {tp_price}")

        except Exception as e:
            log.error(f"Error di reconcile_protection: {e}")

    async def log_closed_trade(self):
        """
        Mengambil detail trade terakhir yang menutup posisi dari API Binance,
        lalu mencatatnya ke CSV jika belum dicatat.
        """
        try:
            trades = await self.client.futures_account_trades(symbol=SYMBOL, limit=10)
            if not trades:
                return

            # Filter trade yang merealisasikan PnL (berarti menutup sebagian/seluruh posisi)
            closing_trades = [t for t in trades if float(t.get('realizedPnl', 0)) != 0]
            if not closing_trades:
                return

            last_trade = closing_trades[-1]
            trade_id = last_trade.get('id')

            if self._last_logged_trade_id == trade_id:
                return  # Sudah dicatat sebelumnya

            self._last_logged_trade_id = trade_id

            pnl = float(last_trade.get('realizedPnl', 0))
            fee = float(last_trade.get('commission', 0))
            net_pnl = pnl - fee
            exit_price = float(last_trade.get('price', 0))
            qty = float(last_trade.get('qty', 0))
            
            # Jika trade penutup adalah BUY, berarti posisi awalnya adalah SHORT.
            # Jika trade penutup adalah SELL, berarti posisi awalnya adalah LONG.
            side = "SHORT" if last_trade.get('side') == "BUY" else "LONG"
            ts_ms = int(last_trade.get('time', 0))
            dt_str = datetime.fromtimestamp(ts_ms / 1000).strftime('%Y-%m-%d %H:%M:%S')

            os.makedirs("data", exist_ok=True)
            csv_path = "data/live_trade_journal.csv"
            file_exists = os.path.exists(csv_path)

            with open(csv_path, 'a', newline='') as f:
                writer = csv.writer(f)
                if not file_exists:
                    writer.writerow(["time", "trade_id", "side", "qty", "exit_price", "realized_pnl", "fee", "net_pnl"])
                
                writer.writerow([dt_str, trade_id, side, qty, exit_price, pnl, fee, net_pnl])

            log.info(f"✅ Trade Jurnal dicatat: {side} | Net PnL: {net_pnl:.2f} USDT")

        except Exception as e:
            log.error(f"Gagal mencatat trade jurnal: {e}")
