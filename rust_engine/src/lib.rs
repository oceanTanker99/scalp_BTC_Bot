use std::collections::VecDeque;

pub struct TimeframeState {
    pub profile_ticks: VecDeque<(f64, f64, u64, f64)>, // price, qty, ts, abs_price_change
    pub cvd_ticks: VecDeque<(f64, f64, u64, bool)>,    // price, qty, ts, is_buyer_maker
    pub histogram: Vec<f64>,                           // Price * 10 as index
    pub profile_vol_sum: f64,
    pub cvd: f64,
    pub vol_price_sum: f64, // For VWAP
    pub vol_sum: f64,       // For VWAP
    
    pub global_min_idx: usize,
    pub global_max_idx: usize,
    
    pub cumulative_path: f64,
    
    // Caching HTF metrics to prevent O(N) blocking
    pub cached_poc: f64,
    pub cached_val: f64,
    pub cached_vah: f64,
    pub cached_vaw: f64,
    pub cached_chop: f64,
    pub last_htf_ts: u64,
    
    pub lookback_ms: u64,
}

impl TimeframeState {
    fn new(lookback_ms: u64) -> Self {
        Self {
            // Smaller capacity for smaller timeframes to save memory
            profile_ticks: VecDeque::with_capacity(if lookback_ms < 3600_000 { 50_000 } else { 500_000 }),
            cvd_ticks: VecDeque::with_capacity(if lookback_ms < 3600_000 { 50_000 } else { 500_000 }),
            histogram: vec![0.0; 2_000_000],
            profile_vol_sum: 0.0,
            cvd: 0.0,
            vol_price_sum: 0.0,
            vol_sum: 0.0,
            
            global_min_idx: 2_000_000,
            global_max_idx: 0,
            
            cumulative_path: 0.0,
            
            cached_poc: 0.0,
            cached_val: 0.0,
            cached_vah: 0.0,
            cached_vaw: 0.0,
            cached_chop: 50.0,
            last_htf_ts: 0,
            
            lookback_ms,
        }
    }

    fn price_to_index(price: f64) -> usize {
        (price * 10.0).round() as usize
    }
    
    fn index_to_price(idx: usize) -> f64 {
        idx as f64 / 10.0
    }

    pub fn add_tick(&mut self, price: f64, qty: f64, is_buyer_maker: bool, ts: u64, abs_change: f64) {
        self.cumulative_path += abs_change;

        // 1. Add to Volume Profile
        self.profile_ticks.push_back((price, qty, ts, abs_change));
        self.profile_vol_sum += qty;
        
        let idx = Self::price_to_index(price);
        if idx < self.histogram.len() {
            self.histogram[idx] += qty;
            if idx < self.global_min_idx { self.global_min_idx = idx; }
            if idx > self.global_max_idx { self.global_max_idx = idx; }
        }

        // 2. Add to CVD/VWAP
        self.cvd_ticks.push_back((price, qty, ts, is_buyer_maker));
        let tick_cvd = if is_buyer_maker { -qty } else { qty };
        self.cvd += tick_cvd;
        self.vol_price_sum += price * qty;
        self.vol_sum += qty;
        
        // 3. Remove old ticks (Volume Profile)
        while let Some(&(f_price, f_qty, f_ts, f_abs_change)) = self.profile_ticks.front() {
            if ts.saturating_sub(f_ts) > self.lookback_ms {
                let f_idx = Self::price_to_index(f_price);
                if f_idx < self.histogram.len() {
                    self.histogram[f_idx] -= f_qty;
                    if self.histogram[f_idx] < 0.0 { self.histogram[f_idx] = 0.0; }
                }
                self.profile_vol_sum -= f_qty;
                if self.profile_vol_sum < 0.0 { self.profile_vol_sum = 0.0; }
                self.cumulative_path -= f_abs_change;
                if self.cumulative_path < 0.0 { self.cumulative_path = 0.0; }
                self.profile_ticks.pop_front();
            } else {
                break;
            }
        }
        
        // 4. Remove old ticks (CVD/VWAP)
        while let Some(&(f_price, f_qty, f_ts, f_maker)) = self.cvd_ticks.front() {
            if ts.saturating_sub(f_ts) > self.lookback_ms {
                let f_cvd = if f_maker { -f_qty } else { f_qty };
                self.cvd -= f_cvd;
                self.vol_price_sum -= f_price * f_qty;
                self.vol_sum -= f_qty;
                self.cvd_ticks.pop_front();
            } else {
                break;
            }
        }
    }
    
    pub fn get_val_vah(&self) -> (f64, f64, f64) {
        if self.profile_vol_sum == 0.0 { return (0.0, 0.0, 0.0); }
        let total_vol: f64 = self.profile_vol_sum;
        if total_vol == 0.0 { return (0.0, 0.0, 0.0); }
        
        let mut poc_idx = 0;
        let mut max_vol = 0.0;
        
        let min_idx = self.global_min_idx;
        let max_idx = self.global_max_idx;
        
        if min_idx >= 2_000_000 { return (0.0, 0.0, 0.0); }
        
        for i in min_idx..=max_idx {
            if self.histogram[i] > max_vol {
                max_vol = self.histogram[i];
                poc_idx = i;
            }
        }
        
        let poc_price = Self::index_to_price(poc_idx);
        let target_vol = total_vol * 0.70;
        let mut current_vol = self.histogram[poc_idx];
        
        let mut up_idx = poc_idx + 1;
        let mut down_idx = if poc_idx > 0 { poc_idx - 1 } else { 0 };
        
        let mut vah_idx = poc_idx;
        let mut val_idx = poc_idx;
        let hist_len = self.histogram.len();
        
        while current_vol < target_vol {
            let up_vol = if up_idx < hist_len { self.histogram[up_idx] } else { -1.0 };
            let down_vol = if down_idx > 0 { self.histogram[down_idx] } else { -1.0 };
            
            if up_vol < 0.0 && down_vol < 0.0 { break; }
            
            if up_vol == 0.0 && down_vol == 0.0 {
                vah_idx = up_idx;
                val_idx = down_idx;
                up_idx += 1;
                down_idx -= 1;
            } else if up_vol >= down_vol {
                current_vol += up_vol;
                vah_idx = up_idx;
                up_idx += 1;
            } else {
                current_vol += down_vol;
                val_idx = down_idx;
                if down_idx > 0 { down_idx -= 1; } else { break; }
            }
        }
        
        (poc_price, Self::index_to_price(val_idx.min(vah_idx)), Self::index_to_price(val_idx.max(vah_idx)))
    }
    
    pub fn get_vaw(&self) -> f64 {
        let (poc, val, vah) = self.get_val_vah();
        if poc > 0.0 { ((vah - val) / poc) * 100.0 } else { 0.0 }
    }

    pub fn get_chop(&self) -> f64 {
        let n = self.profile_ticks.len() as f64;
        if n < 10.0 { return 50.0; }
        
        let mut true_min_idx = self.global_min_idx;
        while true_min_idx <= self.global_max_idx && self.histogram[true_min_idx] == 0.0 {
            true_min_idx += 1;
        }
        let mut true_max_idx = self.global_max_idx;
        while true_max_idx >= self.global_min_idx && self.histogram[true_max_idx] == 0.0 {
            if true_max_idx == 0 { break; }
            true_max_idx -= 1;
        }
        
        let min_price = Self::index_to_price(true_min_idx);
        let max_price = Self::index_to_price(true_max_idx);
        let range = max_price - min_price;
        
        if range > 0.0 && self.cumulative_path > 0.0 {
            let chop = 100.0 * (self.cumulative_path / range).log10() / n.log10();
            chop.clamp(0.0, 100.0)
        } else {
            50.0
        }
    }

    pub fn update_htf_cache(&mut self, current_ts: u64) {
        if current_ts > self.last_htf_ts + 60_000 || self.last_htf_ts == 0 {
            let (poc, val, vah) = self.get_val_vah();
            self.cached_poc = poc;
            self.cached_val = val;
            self.cached_vah = vah;
            self.cached_vaw = if poc > 0.0 { ((vah - val) / poc) * 100.0 } else { 0.0 };
            self.cached_chop = self.get_chop();
            
            while self.global_min_idx < self.global_max_idx && self.histogram[self.global_min_idx] == 0.0 {
                self.global_min_idx += 1;
            }
            while self.global_max_idx > self.global_min_idx && self.histogram[self.global_max_idx] == 0.0 {
                if self.global_max_idx == 0 { break; }
                self.global_max_idx -= 1;
            }
            
            self.last_htf_ts = current_ts;
        }
    }
}

pub struct EngineState {
    pub tf_15m: TimeframeState,
    pub tf_1h: TimeframeState,
    pub tf_4h: TimeframeState,
    pub last_price: f64,
}

impl EngineState {
    pub fn new() -> Self {
        Self {
            tf_15m: TimeframeState::new(900_000),   // 15 minutes
            tf_1h: TimeframeState::new(3600_000),   // 1 hour
            tf_4h: TimeframeState::new(14400_000),  // 4 hours
            last_price: 0.0,
        }
    }

    pub fn add_tick(&mut self, price: f64, qty: f64, is_buyer_maker: bool, ts: u64) {
        let abs_change = if self.last_price > 0.0 { (price - self.last_price).abs() } else { 0.0 };
        self.last_price = price;

        self.tf_15m.add_tick(price, qty, is_buyer_maker, ts, abs_change);
        self.tf_1h.add_tick(price, qty, is_buyer_maker, ts, abs_change);
        self.tf_4h.add_tick(price, qty, is_buyer_maker, ts, abs_change);
    }
}

// ============================================
// C-ABI FFI Endpoints (Callable from Python)
// ============================================

#[no_mangle]
pub extern "C" fn init_engine() -> *mut EngineState {
    Box::into_raw(Box::new(EngineState::new()))
}

#[no_mangle]
pub extern "C" fn add_tick(
    engine: *mut EngineState,
    price: f64,
    qty: f64,
    is_buyer_maker: bool,
    ts: u64
) {
    if engine.is_null() { return; }
    let engine = unsafe { &mut *engine };
    engine.add_tick(price, qty, is_buyer_maker, ts);
}

#[no_mangle]
pub extern "C" fn get_metrics(
    engine: *mut EngineState,
    out_metrics: *mut f64 // Expects array of 24 f64: 3 x [vwap, cvd, poc, val, vah, vaw, chop, last_price]
) {
    if engine.is_null() || out_metrics.is_null() { return; }
    let engine = unsafe { &mut *engine };
    
    let current_ts = if let Some(last_tick) = engine.tf_4h.profile_ticks.back() {
        last_tick.2
    } else {
        0
    };

    engine.tf_15m.update_htf_cache(current_ts);
    engine.tf_1h.update_htf_cache(current_ts);
    engine.tf_4h.update_htf_cache(current_ts);
    
    let out = unsafe { std::slice::from_raw_parts_mut(out_metrics, 24) };
    
    let tfs = [&engine.tf_15m, &engine.tf_1h, &engine.tf_4h];
    for (i, tf) in tfs.iter().enumerate() {
        let offset = i * 8;
        out[offset] = if tf.vol_sum > 0.0 { tf.vol_price_sum / tf.vol_sum } else { 0.0 };
        out[offset + 1] = tf.cvd;
        out[offset + 2] = tf.cached_poc;
        out[offset + 3] = tf.cached_val;
        out[offset + 4] = tf.cached_vah;
        out[offset + 5] = tf.cached_vaw;
        out[offset + 6] = tf.cached_chop;
        out[offset + 7] = engine.last_price;
    }
}

#[no_mangle]
pub extern "C" fn free_engine(engine: *mut EngineState) {
    if !engine.is_null() {
        unsafe { let _ = Box::from_raw(engine); }
    }
}
