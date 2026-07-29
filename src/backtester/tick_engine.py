import os
import csv
import logging
import time
from datetime import datetime
from config.config import TRADE_RISK_PCT, RRR_TP1
from src.order_flow_engine import OrderFlowEngine
from src.strategy import StrategyEngine

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
log = logging.getLogger(__name__)

class TickBacktester:
    def __init__(self, initial_balance=100.0):
        self.engine = OrderFlowEngine()
        self.strategy = StrategyEngine()
        
        self.balance = initial_balance
        self.start_balance = initial_balance
        self.position = None # None, or dict with keys: side, entry_price, qty, sl, tp
        self.trades = []
        
        self.last_eval_time = 0
        
    def run_backtest_multi(self, csv_file_paths):
        valid_paths = [p for p in csv_file_paths if os.path.exists(p)]
        if not valid_paths:
            log.error(f"Tidak ada file CSV yang valid ditemukan dari {csv_file_paths}")
            return
            
        log.info(f"Memulai backtest multi-bulan dari {len(valid_paths)} file...")
        log.info(f"Saldo Awal: {self.balance} USDT")
        
        start_time_real = time.time()
        row_count = 0
        
        # Override imbalance parameter in strategy since we don't have L2 data
        self.strategy.current_params['imbalance_threshold'] = -999.0 # Effectively disable imbalance requirement
        
        for csv_file_path in valid_paths:
            log.info(f"== Memproses {csv_file_path} ==")
            with open(csv_file_path, 'r') as f:
                reader = csv.reader(f)
                header = next(reader, None) # Skip header if exists
                
                # agg_trade_id, price, quantity, first_trade_id, last_trade_id, transact_time, is_buyer_maker
                for row in reader:
                    try:
                        price = float(row[1])
                        qty = float(row[2])
                        ts_ms = int(row[5])
                        ts_sec = int(ts_ms / 1000)
                        is_buyer_maker = row[6].lower() == 'true'
                        
                        msg = {
                            'T': ts_ms,
                            'p': price,
                            'q': qty,
                            'm': is_buyer_maker
                        }
                        
                        self.engine.process_agg_trade(msg)
                        row_count += 1
                        
                        # Manage existing position (SL/TP)
                        if self.position:
                            self._manage_position(price, ts_sec)
                        
                        # Evaluate Strategy every 3 seconds (simulated)
                        if not self.position and ts_sec - self.last_eval_time >= 3:
                            self.last_eval_time = ts_sec
                            metrics = self.engine.get_metrics()
                            
                            # Mock imbalance because we lack depth data
                            # We force it to follow CVD direction so it bypasses the strategy check
                            cvd_15m = metrics.get('15m', {}).get('cvd', 0)
                            imb = 1.0 if cvd_15m > 0 else -1.0
                            for tf in ['15m', '1h', '4h']:
                                if tf in metrics:
                                    metrics[tf]['imbalance'] = imb
                            
                            signal, eval_price, sl_dist = self.strategy.analyze_order_flow(metrics)
                            
                            if signal in ["LONG", "SHORT"]:
                                # --- OPTIMIZATION FILTERS ---
                                valid_signal = True
                                
                                # Filter 1: Kill Zone — Jam-jam volatilitas tinggi yang berbahaya untuk Mean-Reversion
                                dt_utc = datetime.utcfromtimestamp(ts_sec)
                                # NY Kill Zone: 13:00-16:59 UTC (termasuk penutupan London overlap)
                                # Asia Kill Zone: 00:00-01:59 UTC (potensi flash crash & liquidation cascade)
                                is_ny_kill = 13 <= dt_utc.hour <= 16
                                is_asia_kill = 0 <= dt_utc.hour <= 1
                                if is_ny_kill or is_asia_kill:
                                    valid_signal = False
                                
                                # Filter 2: VWAP Distance (> 0.45%)
                                if valid_signal and metrics and 'vwap' in metrics:
                                    vwap = metrics['vwap']
                                    if vwap > 0:
                                        dist_to_vwap = abs(price - vwap) / vwap * 100
                                        if dist_to_vwap < 0.45:
                                            valid_signal = False
                                
                                if valid_signal:
                                    self._enter_position(signal, price, sl_dist, ts_sec, metrics)
                                
                        if row_count % 1000000 == 0:
                            log.info(f"Memproses {row_count} baris... Saldo Sementara: {self.balance:.2f} USDT")
                            
                    except Exception as e:
                        continue # Skip malformed rows
                    
        end_time_real = time.time()
        log.info(f"Backtest Selesai! Waktu proses: {end_time_real - start_time_real:.2f} detik")
        self._print_report()
        self._export_journal()
        
    def _enter_position(self, signal, price, sl_dist, ts, metrics=None):
        risk_amount = self.balance * TRADE_RISK_PCT
        if sl_dist <= 0: return
        
        qty = risk_amount / (price * sl_dist)
        qty = round(qty, 3)
        if qty < 0.001: qty = 0.001
        
        if signal == 'LONG':
            sl = price * (1 - sl_dist)
            tp = price * (1 + (sl_dist * RRR_TP1))
        else:
            sl = price * (1 + sl_dist)
            tp = price * (1 - (sl_dist * RRR_TP1))
            
        self.position = {
            'side': signal,
            'entry_price': price,
            'qty': qty,
            'sl': sl,
            'tp': tp,
            'entry_time': ts,
            'metrics_cvd': metrics.get('cvd', 0) if metrics else 0,
            'metrics_vwap': metrics.get('vwap', 0) if metrics else 0,
            'metrics_val': metrics.get('val', 0) if metrics else 0,
            'metrics_vah': metrics.get('vah', 0) if metrics else 0,
            'metrics_poc': metrics.get('poc', 0) if metrics else 0,
            'metrics_imbalance': metrics.get('imbalance', 0) if metrics else 0
        }
        
    def _manage_position(self, current_price, ts):
        pos = self.position
        closed = False
        pnl = 0.0
        reason = ""
        
        if pos['side'] == 'LONG':
            if current_price <= pos['sl']:
                pnl = (pos['sl'] - pos['entry_price']) * pos['qty']
                closed = True
                reason = "SL"
            elif current_price >= pos['tp']:
                pnl = (pos['tp'] - pos['entry_price']) * pos['qty']
                closed = True
                reason = "TP"
        else:
            if current_price >= pos['sl']:
                pnl = (pos['entry_price'] - pos['sl']) * pos['qty']
                closed = True
                reason = "SL"
            elif current_price <= pos['tp']:
                pnl = (pos['entry_price'] - pos['tp']) * pos['qty']
                closed = True
                reason = "TP"
                
        if closed:
            self.balance += pnl
            self.trades.append({
                'entry_time': pos['entry_time'],
                'exit_time': ts,
                'side': pos['side'],
                'entry_price': pos['entry_price'],
                'exit_price': pos['sl'] if reason == "SL" else pos['tp'],
                'pnl': pnl,
                'reason': reason,
                'balance': self.balance,
                'cvd': pos.get('metrics_cvd', 0),
                'vwap': pos.get('metrics_vwap', 0),
                'val': pos.get('metrics_val', 0),
                'vah': pos.get('metrics_vah', 0),
                'poc': pos.get('metrics_poc', 0),
                'imbalance': pos.get('metrics_imbalance', 0)
            })
            self.position = None

    def _print_report(self):
        total_trades = len(self.trades)
        wins = len([t for t in self.trades if t['pnl'] > 0])
        losses = len([t for t in self.trades if t['pnl'] < 0])
        win_rate = (wins / total_trades * 100) if total_trades > 0 else 0
        pnl_pct = ((self.balance - self.start_balance) / self.start_balance) * 100
        
        log.info("========== HASIL BACKTEST TICK ==========")
        log.info(f"Total Trade : {total_trades}")
        log.info(f"Win Rate    : {win_rate:.2f}% ({wins} W / {losses} L)")
        log.info(f"Saldo Akhir : {self.balance:.2f} USDT")
        log.info(f"Total PnL   : {pnl_pct:+.2f}%")
        log.info("=========================================")

    def _export_journal(self):
        if not self.trades:
            return
            
        csv_path = "data/tick_backtest_journal.csv"
        os.makedirs("data", exist_ok=True)
        
        keys = self.trades[0].keys()
        with open(csv_path, 'w', newline='') as f:
            dict_writer = csv.DictWriter(f, keys)
            dict_writer.writeheader()
            dict_writer.writerows(self.trades)
        log.info(f"Jurnal trade diekspor ke {csv_path}")

if __name__ == "__main__":
    # Test path fallback if you run directly
    tester = TickBacktester(initial_balance=100.0)
    files_to_test = [
        "data/historical_aggtrades/BTCUSDT-aggTrades-2026-01.csv",
        "data/historical_aggtrades/BTCUSDT-aggTrades-2026-02.csv",
        "data/historical_aggtrades/BTCUSDT-aggTrades-2026-03.csv",
        "data/historical_aggtrades/BTCUSDT-aggTrades-2026-04.csv",
        "data/historical_aggtrades/BTCUSDT-aggTrades-2026-05.csv",
        "data/historical_aggtrades/BTCUSDT-aggTrades-2026-06.csv"
    ]
    tester.run_backtest_multi(files_to_test)
