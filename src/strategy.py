import json
import os
import time
import logging

log = logging.getLogger(__name__)

class StrategyEngine:
    def __init__(self):
        self.params_file = "config/ai_params.json"
        self.kronos_cache_file = "config/kronos_cache.json"
        
        # In-memory cache of params to avoid excessive disk I/O
        self.current_params = {
            "cvd_divergence_threshold": 5.0,
            "imbalance_threshold": 0.3,
            "vwap_distance_pct": 0.1
        }
        self.last_load_time = 0
        
        # In-memory cache for Kronos
        self.kronos_prediction = {"trend": "SIDEWAYS"}
        self.last_kronos_load_time = 0
        self._last_check_time = 0

    def _load_params(self):
        # Throttle: hanya cek file maksimal setiap 10 detik untuk menghindari blocking I/O
        now = time.time()
        if now - self._last_check_time < 10:
            return
        self._last_check_time = now
        
        try:
            if os.path.exists(self.params_file):
                mtime = os.path.getmtime(self.params_file)
                if mtime > self.last_load_time:
                    with open(self.params_file, "r") as f:
                        params = json.load(f)
                        self.current_params.update(params)
                    self.last_load_time = mtime
            
            # Load Kronos cache
            if os.path.exists(self.kronos_cache_file):
                k_mtime = os.path.getmtime(self.kronos_cache_file)
                if k_mtime > self.last_kronos_load_time:
                    with open(self.kronos_cache_file, "r") as f:
                        k_data = json.load(f)
                        self.kronos_prediction = k_data
                    self.last_kronos_load_time = k_mtime
        except Exception as e:
            log.error(f"Error loading AI/Kronos params: {e}")

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
        funding_rate = metrics.get('funding_rate', 0.0)
        
        current_price = m_15m.get('current_price', 0)
        cvd = m_15m.get('cvd', 0)
        imbalance = m_15m.get('imbalance', 0)
        vwap = m_15m.get('vwap', 0)
        poc = m_15m.get('poc', 0)
        vah = m_15m.get('vah', 0)
        val = m_15m.get('val', 0)
        vaw = m_15m.get('vaw', 0)
        
        if current_price == 0 or vwap == 0:
            return "NEUTRAL", 0.0, 0.0
            
        # [AUDIT P2] Regime Detection via Value Area Width (VAW)
        # VAW sempit = market squeeze/ranging → JANGAN TRADE (potensi breakout palsu)
        # VAW terlalu lebar = market terlalu liar → KURANGI eksposur
        if vaw > 0 and vwap > 0:
            vaw_pct = vaw / vwap * 100  # VAW sebagai persentase dari VWAP
            if vaw_pct < 0.15:  # Squeeze: VA terlalu sempit (<0.15%)
                log.info(f"🔒 REGIME: Market Squeeze terdeteksi (VAW: {vaw_pct:.3f}%). Sinyal diabaikan.")
                return "NEUTRAL", current_price, 0.0
            if vaw_pct > 2.0:  # Chaos: VA terlalu lebar (>2%)
                log.info(f"🌪️ REGIME: Market terlalu volatile (VAW: {vaw_pct:.3f}%). Sinyal diabaikan.")
                return "NEUTRAL", current_price, 0.0
        
        cvd_thresh = self.current_params.get("cvd_divergence_threshold", 5.0)
        imb_thresh = self.current_params.get("imbalance_threshold", 0.3)
        vwap_pct = self.current_params.get("vwap_distance_pct", 0.1)
        
        kronos_trend = self.kronos_prediction.get("trend", "SIDEWAYS")
        
        # Apply Soft Filter
        # Jika Kronos prediksi berlawanan arah dengan strategi, perketat syarat masuk 2x lipat
        # [AUDIT P3] Funding Rate filter: penalty if against the crowd
        long_penalty = 2.0 if kronos_trend == "DOWN" else 1.0
        short_penalty = 2.0 if kronos_trend == "UP" else 1.0
        
        if funding_rate > 0.0001: # High positive funding (too many longs) -> penalty for LONG
            long_penalty *= 1.5
        elif funding_rate < -0.0001: # High negative funding (too many shorts) -> penalty for SHORT
            short_penalty *= 1.5
        
        cvd_thresh_long = cvd_thresh * long_penalty
        imb_thresh_long = imb_thresh * long_penalty
        vwap_pct_long = vwap_pct * long_penalty
        
        cvd_thresh_short = cvd_thresh * short_penalty
        imb_thresh_short = imb_thresh * short_penalty
        vwap_pct_short = vwap_pct * short_penalty
        
        dist_to_vwap = (current_price - vwap) / vwap * 100
        
        # Volume Profile Golden Setup Checks (0.2% tolerance)
        is_undervalued = (current_price <= val * 1.002) if val > 0 else True
        is_overvalued = (current_price >= vah * 0.998) if vah > 0 else True
        
        # --- LONG LOGIC ---
        # 1. Harga di bawah VWAP sejauh batas over-extension (oversold)
        # 2. Harga di dekat atau di bawah Value Area Low (Undervalued)
        # 3. CVD Positif (Taker Buy dominan)
        # 4. Orderbook Imbalance Positif (Bids > Asks)
        if dist_to_vwap < -vwap_pct_long and cvd > cvd_thresh_long and imbalance > imb_thresh_long and is_undervalued:
            log.info(f"[ORDER FLOW] LONG SIGNAL DETECTED | Price: {current_price} | VAL: {val:.1f} | CVD: {cvd:.1f} | Imb: {imbalance:.2f} | Kronos: {kronos_trend}")
            sl_distance = max(0.01, abs(dist_to_vwap / 100) / 2)  # Min SL 1% (audit: 0.5% terlalu ketat untuk BTC)
            return "LONG", current_price, sl_distance
            
        # --- SHORT LOGIC ---
        # 1. Harga di atas VWAP sejauh batas over-extension (overbought)
        # 2. Harga di dekat atau di atas Value Area High (Overvalued)
        # 3. CVD Negatif (Taker Sell dominan)
        # 4. Orderbook Imbalance Negatif (Asks > Bids)
        if dist_to_vwap > vwap_pct_short and cvd < -cvd_thresh_short and imbalance < -imb_thresh_short and is_overvalued:
            log.info(f"[ORDER FLOW] SHORT SIGNAL DETECTED | Price: {current_price} | VAH: {vah:.1f} | CVD: {cvd:.1f} | Imb: {imbalance:.2f} | Kronos: {kronos_trend}")
            sl_distance = max(0.01, abs(dist_to_vwap / 100) / 2)  # Min SL 1% (audit: 0.5% terlalu ketat untuk BTC)
            return "SHORT", current_price, sl_distance
            
        return "NEUTRAL", current_price, 0.0
