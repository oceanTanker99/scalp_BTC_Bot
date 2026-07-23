import json
import os
import logging

log = logging.getLogger(__name__)

class StrategyEngine:
    def __init__(self):
        self.params_file = "config/ai_params.json"
        
        # In-memory cache of params to avoid excessive disk I/O
        self.current_params = {
            "cvd_divergence_threshold": 5.0,
            "imbalance_threshold": 0.3,
            "vwap_distance_pct": 0.1
        }
        self.last_load_time = 0

    def _load_params(self):
        # Only reload if file has actually been modified since last read
        try:
            if os.path.exists(self.params_file):
                mtime = os.path.getmtime(self.params_file)
                if mtime > self.last_load_time:
                    with open(self.params_file, "r") as f:
                        params = json.load(f)
                        self.current_params.update(params)
                    self.last_load_time = mtime
        except Exception as e:
            log.error(f"Error loading AI params: {e}")

    def analyze_order_flow(self, metrics: dict):
        """
        Mengevaluasi sinyal trading murni menggunakan matematika (milidetik).
        Menerima dict 'metrics' yang berisi data 15m, 1h, dan 4h.
        
        Returns:
            signal (str): 'LONG', 'SHORT', or 'NEUTRAL'
            price (float): current price
            sl_distance (float): dynamic stop loss distance (as fraction of price)
        """
        self._load_params()
        
        m_15m = metrics.get('15m', {})
        
        current_price = m_15m.get('current_price', 0)
        cvd = m_15m.get('cvd', 0)
        imbalance = m_15m.get('imbalance', 0)
        vwap = m_15m.get('vwap', 0)
        poc = m_15m.get('poc', 0)
        vah = m_15m.get('vah', 0)
        val = m_15m.get('val', 0)
        
        if current_price == 0 or vwap == 0:
            return "NEUTRAL", 0.0, 0.0
            
        cvd_thresh = self.current_params.get("cvd_divergence_threshold", 5.0)
        imb_thresh = self.current_params.get("imbalance_threshold", 0.3)
        vwap_pct = self.current_params.get("vwap_distance_pct", 0.1)
        
        dist_to_vwap = (current_price - vwap) / vwap * 100
        
        # Volume Profile Golden Setup Checks (0.2% tolerance)
        is_undervalued = (current_price <= val * 1.002) if val > 0 else True
        is_overvalued = (current_price >= vah * 0.998) if vah > 0 else True
        
        # --- LONG LOGIC ---
        # 1. Harga di bawah VWAP sejauh batas over-extension (oversold)
        # 2. Harga di dekat atau di bawah Value Area Low (Undervalued)
        # 3. CVD Positif (Taker Buy dominan)
        # 4. Orderbook Imbalance Positif (Bids > Asks)
        if dist_to_vwap < -vwap_pct and cvd > cvd_thresh and imbalance > imb_thresh and is_undervalued:
            log.info(f"[ORDER FLOW] LONG SIGNAL DETECTED | Price: {current_price} | VAL: {val:.1f} | CVD: {cvd:.1f} | Imbalance: {imbalance:.2f}")
            sl_distance = max(0.005, abs(dist_to_vwap / 100) / 2) # SL at half the VWAP distance
            return "LONG", current_price, sl_distance
            
        # --- SHORT LOGIC ---
        # 1. Harga di atas VWAP sejauh batas over-extension (overbought)
        # 2. Harga di dekat atau di atas Value Area High (Overvalued)
        # 3. CVD Negatif (Taker Sell dominan)
        # 4. Orderbook Imbalance Negatif (Asks > Bids)
        if dist_to_vwap > vwap_pct and cvd < -cvd_thresh and imbalance < -imb_thresh and is_overvalued:
            log.info(f"[ORDER FLOW] SHORT SIGNAL DETECTED | Price: {current_price} | VAH: {vah:.1f} | CVD: {cvd:.1f} | Imbalance: {imbalance:.2f}")
            sl_distance = max(0.005, abs(dist_to_vwap / 100) / 2)
            return "SHORT", current_price, sl_distance
            
        return "NEUTRAL", current_price, 0.0
