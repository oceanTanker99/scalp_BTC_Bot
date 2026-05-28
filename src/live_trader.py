import logging
from binance import AsyncClient
from binance.exceptions import BinanceAPIException
from config.config import (
    BINANCE_API_KEY, BINANCE_SECRET_KEY, BINANCE_TESTNET, SYMBOL,
    TRADE_RISK_PCT, LEVERAGE, RRR_TP1, MAX_DAILY_DRAWDOWN_PCT
)

log = logging.getLogger(__name__)

class LiveTrader:
    def __init__(self):
        self.client = None
        self.start_balance = 0.0
        self._notifier = None  # Diisi oleh main jika perlu

    async def initialize(self):
        self.client = await AsyncClient.create(
            BINANCE_API_KEY, BINANCE_SECRET_KEY, testnet=BINANCE_TESTNET
        )
        await self._set_leverage()
        self.start_balance = await self.get_balance()
        log.info(f"Live Trader Initialized. Start Balance: {self.start_balance} USDT")

    async def _set_leverage(self):
        try:
            await self.client.futures_change_leverage(symbol=SYMBOL, leverage=LEVERAGE)
        except Exception:
            pass
        try:
            await self.client.futures_change_margin_type(symbol=SYMBOL, marginType='ISOLATED')
        except Exception:
            pass  # Ignore if already isolated

    async def get_balance(self) -> float:
        try:
            res = await self.client.futures_account_balance()
            usdt = next((item for item in res if item['asset'] == 'USDT'), None)
            return float(usdt['balance']) if usdt else 0.0
        except Exception as e:
            log.error(f"Error getting balance: {e}")
            return 0.0

    # --- Perbaikan Bug #1: Cek posisi nyata dari Binance ---
    async def has_open_position(self) -> bool:
        try:
            positions = await self.client.futures_position_information(symbol=SYMBOL)
            for pos in positions:
                if float(pos.get('positionAmt', 0)) != 0:
                    return True
            return False
        except Exception as e:
            log.error(f"Error checking position: {e}")
            return True  # Failsafe: anggap ada posisi jika API error

    async def check_kill_switch(self) -> bool:
        if self.start_balance <= 0:
            return False
        current_balance = await self.get_balance()
        drawdown = (self.start_balance - current_balance) / self.start_balance
        if drawdown >= MAX_DAILY_DRAWDOWN_PCT:
            log.error(f"KILL SWITCH ACTIVATED! Drawdown {drawdown:.2%} exceeds limit.")
            return True
        return False

    async def execute_trade(self, signal: str, current_price: float, sl_distance: float):
        """
        Eksekusi market order dan pasang SL/TP.
        Returns: (sl_price, tp_price, qty) jika berhasil, atau (None, None, None) jika gagal.
        """
        if await self.check_kill_switch():
            return None, None, None
            
        balance = await self.get_balance()
        risk_amount = balance * TRADE_RISK_PCT
        
        sl_pct = sl_distance
        if sl_pct <= 0:
            log.error("sl_pct is zero or negative, aborting trade.")
            return None, None, None
        
        # Hitung kuantitas berdasarkan risiko
        # risk_amount = qty * current_price * sl_pct
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
            log.info(f"Placing {side} Market Order | Qty: {qty} BTC | SL: {sl_price} | TP: {tp_price}")
            
            # --- Entry Order ---
            await self.client.futures_create_order(
                symbol=SYMBOL,
                side=side,
                type='MARKET',
                quantity=qty
            )
            
            # --- Perbaikan Bug #3: Gunakan API standar, bukan private method ---
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
            
            log.info(f"✅ Order berhasil! Entry: {current_price}, SL: {sl_price}, TP: {tp_price}")
            return sl_price, tp_price, qty
            
        except BinanceAPIException as e:
            log.error(f"Binance API Error executing trade: {e}")
            return None, None, None
        except Exception as e:
            log.error(f"Error executing trade: {e}")
            return None, None, None
