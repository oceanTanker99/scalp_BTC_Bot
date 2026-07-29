use rust_engine::EngineState;
use std::fs::File;
use std::io::{BufRead, BufReader};
use std::path::PathBuf;

struct StrategyState {
    name: String,
    position: f64, // 0 = flat, 1 = long, -1 = short
    entry_price: f64,
    qty: f64,
    pnl: f64,
    wins: u32,
    losses: u32,
    be: u32,
    sl_price: f64,
    tp_price: f64,
}

impl StrategyState {
    fn new(name: &str) -> Self {
        Self {
            name: name.to_string(),
            position: 0.0,
            entry_price: 0.0,
            qty: 0.0,
            pnl: 0.0,
            wins: 0,
            losses: 0,
            be: 0,
            sl_price: 0.0,
            tp_price: 0.0,
        }
    }

    fn check_exit(&mut self, current_price: f64) {
        if self.position > 0.0 {
            if current_price <= self.sl_price {
                let trade_pnl = (current_price - self.entry_price) * self.qty;
                self.pnl += trade_pnl;
                self.losses += 1;
                self.position = 0.0;
            } else if current_price >= self.tp_price {
                let trade_pnl = (current_price - self.entry_price) * self.qty;
                self.pnl += trade_pnl;
                self.wins += 1;
                self.position = 0.0;
            }
        } else if self.position < 0.0 {
            if current_price >= self.sl_price {
                let trade_pnl = (self.entry_price - current_price) * self.qty;
                self.pnl += trade_pnl;
                self.losses += 1;
                self.position = 0.0;
            } else if current_price <= self.tp_price {
                let trade_pnl = (self.entry_price - current_price) * self.qty;
                self.pnl += trade_pnl;
                self.wins += 1;
                self.position = 0.0;
            }
        }
    }

    fn enter_trade(&mut self, signal: f64, price: f64, sl: f64, tp: f64, equity: f64) {
        self.position = signal;
        self.entry_price = price;
        self.sl_price = sl;
        self.tp_price = tp;
        
        // Risk 2%
        let risk_amt = equity * 0.02;
        let sl_pct = (price - sl).abs() / price;
        self.qty = risk_amt / (price * sl_pct);
    }
}

fn main() {
    let mut engine = EngineState::new();
    
    let mut strats = vec![
        StrategyState::new("Baseline (No Filter)"),
        StrategyState::new("VAW Filter Only"),
        StrategyState::new("Hurst (CHOP) Filter Only"),
        StrategyState::new("Combined (VAW + CHOP)"),
    ];
    
    let mut initial_equity = vec![1000.0, 1000.0, 1000.0, 1000.0];
    
    let months = ["01", "02", "03", "04", "05", "06"];
    
    let mut total_ticks = 0;
    
    let mut cached_vaw = 0.0;
    let mut cached_chop = 50.0;
    let mut last_htf_ts: u64 = 0;
    
    for month in months {
        let file_path = format!("../data/historical_aggtrades/BTCUSDT-aggTrades-2026-{}.csv", month);
        let path = PathBuf::from(&file_path);
        
        if !path.exists() {
            println!("File not found: {}", file_path);
            continue;
        }
        
        println!("Processing {}...", file_path);
        
        let file = File::open(&path).unwrap();
        let reader = BufReader::new(file);
        
        for line_res in reader.lines() {
            let line = line_res.unwrap();
            let parts: Vec<&str> = line.split(',').collect();
            if parts.len() < 7 || parts[1] == "price" { continue; }
            
            let price: f64 = parts[1].parse().unwrap_or(0.0);
            let qty: f64 = parts[2].parse().unwrap_or(0.0);
            let ts: u64 = parts[5].parse().unwrap_or(0);
            let is_buyer_maker: bool = parts[6] == "true" || parts[6] == "True";
            
            if price == 0.0 || qty == 0.0 || ts == 0 { continue; }
            
            engine.add_tick(price, qty, is_buyer_maker, ts);
            total_ticks += 1;
            
            // Recompute HTF filters only once per minute (60,000 ms) to avoid O(N) histogram scans on every tick
            if ts > last_htf_ts + 60_000 {
                cached_vaw = engine.tf_4h.get_vaw();
                cached_chop = engine.tf_4h.get_chop();
                last_htf_ts = ts;
            }
            
            if total_ticks % 1_000_000 == 0 {
                println!("Ticks: {}M | Price: {} | VWAP: {:.1} | VAW: {:.2}% | CHOP: {:.1}", total_ticks / 1_000_000, price, if engine.tf_4h.vol_sum > 0.0 { engine.tf_4h.vol_price_sum / engine.tf_4h.vol_sum } else { 0.0 }, cached_vaw, cached_chop);
            }
            
            // Check Exits for all strats
            for strat in &mut strats {
                strat.check_exit(price);
            }
            
            // Evaluate Entry if position == 0
            if engine.tf_4h.vol_sum > 0.0 {
                let vwap = engine.tf_4h.vol_price_sum / engine.tf_4h.vol_sum;
                let distance = (price - vwap).abs() / vwap;
                
                if distance > 0.0045 { // 0.45% VWAP Distance threshold
                    
                    // Time filter: NY Kill Zone (13:00 - 16:59 UTC)
                    let sec_of_day = (ts / 1000) % 86400;
                    let hour = sec_of_day / 3600;
                    let in_kill_zone = hour >= 13 && hour < 17;
                    
                    if !in_kill_zone {
                        let signal = if price < vwap { 1.0 } else { -1.0 };
                        
                        let sl_pct = 0.01;
                        let tp_pct = 0.015; // RRR 1:1.5
                        
                        let sl = if signal > 0.0 { price * (1.0 - sl_pct) } else { price * (1.0 + sl_pct) };
                        let tp = if signal > 0.0 { price * (1.0 + tp_pct) } else { price * (1.0 - tp_pct) };
                        
                        let vaw = cached_vaw;
                        let chop = cached_chop;
                        
                        // Strat 0: Baseline
                        if strats[0].position == 0.0 {
                            let eq = initial_equity[0] + strats[0].pnl;
                            strats[0].enter_trade(signal, price, sl, tp, eq);
                        }
                        
                        // Strat 1: VAW Filter (must be < 1.0)
                        if strats[1].position == 0.0 && vaw < 1.0 {
                            let eq = initial_equity[1] + strats[1].pnl;
                            strats[1].enter_trade(signal, price, sl, tp, eq);
                        }
                        
                        // Strat 2: CHOP Filter (must be > 61.8)
                        if strats[2].position == 0.0 && chop > 61.8 {
                            let eq = initial_equity[2] + strats[2].pnl;
                            strats[2].enter_trade(signal, price, sl, tp, eq);
                        }
                        
                        // Strat 3: Combined
                        if strats[3].position == 0.0 && vaw < 1.0 && chop > 61.8 {
                            let eq = initial_equity[3] + strats[3].pnl;
                            strats[3].enter_trade(signal, price, sl, tp, eq);
                        }
                    }
                }
            }
        }
    }
    
    println!("\\n========================================");
    println!("🏁 6-MONTH HTF FILTER BACKTEST RESULTS");
    println!("========================================");
    
    for (i, strat) in strats.iter().enumerate() {
        let total = strat.wins + strat.losses + strat.be;
        let wr = if total > 0 { (strat.wins as f64 / total as f64) * 100.0 } else { 0.0 };
        let final_eq = initial_equity[i] + strat.pnl;
        let roi = (final_eq - initial_equity[i]) / initial_equity[i] * 100.0;
        
        println!("Strategy: {}", strat.name);
        println!("Trades  : {} (W: {}, L: {})", total, strat.wins, strat.losses);
        println!("Win Rate: {:.2}%", wr);
        println!("Net PnL : ${:.2} ({:+.2}%)", strat.pnl, roi);
        println!("----------------------------------------");
    }
}
