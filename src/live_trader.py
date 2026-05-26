import logging
from binance import AsyncClient
from binance.exceptions import BinanceAPIException
from config.config import BINANCE_API_KEY, BINANCE_SECRET_KEY, BINANCE_TESTNET, SYMBOL, TRADE_RISK_PCT, LEVERAGE, RRR_TP1, RRR_TP2, RRR_TP3, MAX_DAILY_DRAWDOWN_PCT

log = logging.getLogger(__name__)

class LiveTrader:
    def __init__(self):
        self.client = None
        self.start_balance = 0.0

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
            await self.client.futures_change_margin_type(symbol=SYMBOL, marginType='ISOLATED')
        except Exception as e:
            # Ignore if already isolated
            pass

    async def get_balance(self):
        try:
            res = await self.client.futures_account_balance()
            usdt = next((item for item in res if item['asset'] == 'USDT'), None)
            return float(usdt['balance']) if usdt else 0.0
        except Exception as e:
            log.error(f"Error getting balance: {e}")
            return 0.0

    async def check_kill_switch(self):
        current_balance = await self.get_balance()
        drawdown = (self.start_balance - current_balance) / self.start_balance
        if drawdown >= MAX_DAILY_DRAWDOWN_PCT:
            log.error(f"KILL SWITCH ACTIVATED! Drawdown {drawdown:.2%} exceeds limit.")
            return True
        return False

    async def execute_trade(self, signal, current_price):
        if await self.check_kill_switch():
            return
            
        balance = await self.get_balance()
        # Risk 1% of balance
        risk_amount = balance * TRADE_RISK_PCT
        
        # Stop loss percentage (e.g. 0.5% price movement)
        sl_pct = 0.005 
        
        # Calculate quantity based on risk
        # risk_amount = qty * current_price * sl_pct
        qty = risk_amount / (current_price * sl_pct)
        # Round qty to 3 decimals (BTC precision usually 3 on futures)
        qty = round(qty, 3)
        if qty == 0:
            qty = 0.001
            
        side = 'BUY' if signal == 'LONG' else 'SELL'
        
        try:
            log.info(f"Placing {side} Market Order for {qty} BTC")
            # Entry Order
            entry = await self.client.futures_create_order(
                symbol=SYMBOL,
                side=side,
                type='MARKET',
                quantity=qty
            )
            
            # Place SL/TP via AlgoOrder Endpoint (to bypass -4120 error)
            await self._place_sl_tp(signal, current_price, qty, sl_pct)
            
        except BinanceAPIException as e:
            log.error(f"Binance API Error executing trade: {e}")
        except Exception as e:
            log.error(f"Error executing trade: {e}")

    async def _place_sl_tp(self, signal, entry_price, qty, sl_pct):
        # Calculate levels
        if signal == 'LONG':
            sl_price = round(entry_price * (1 - sl_pct), 1)
            tp_price = round(entry_price * (1 + (sl_pct * RRR_TP1)), 1)
            sl_side = 'SELL'
            tp_side = 'SELL'
        else:
            sl_price = round(entry_price * (1 + sl_pct), 1)
            tp_price = round(entry_price * (1 - (sl_pct * RRR_TP1)), 1)
            sl_side = 'BUY'
            tp_side = 'BUY'

        log.info(f"Placing SL: {sl_price}, TP: {tp_price}")
        
        # SL Algo Order
        try:
            await self.client._request_futures_api('post', 'algoOrder', True, data={
                'symbol': SYMBOL,
                'side': sl_side,
                'type': 'STOP_MARKET',
                'stopPrice': sl_price,
                'closePosition': 'true',
                'timeInForce': 'GTE_GTC'
            })
        except BinanceAPIException as e:
            log.error(f"Failed to place SL Algo Order: {e}")

        # TP Algo Order
        try:
            await self.client._request_futures_api('post', 'algoOrder', True, data={
                'symbol': SYMBOL,
                'side': tp_side,
                'type': 'TAKE_PROFIT_MARKET',
                'stopPrice': tp_price,
                'closePosition': 'true',
                'timeInForce': 'GTE_GTC'
            })
        except BinanceAPIException as e:
            log.error(f"Failed to place TP Algo Order: {e}")
