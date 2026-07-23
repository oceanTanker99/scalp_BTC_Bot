import os
import sys
import ctypes
import logging

log = logging.getLogger(__name__)

# Detect OS and load the appropriate shared library
if sys.platform == "win32":
    lib_name = "rust_engine.dll"
elif sys.platform == "darwin":
    lib_name = "librust_engine.dylib"
else:
    lib_name = "librust_engine.so"

# Locate the library (assuming it's built in rust_engine/target/release/)
base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
lib_path = os.path.join(base_dir, "rust_engine", "target", "release", lib_name)

class RustEngineDLL:
    _instance = None
    
    @classmethod
    def get_lib(cls):
        if cls._instance is None:
            if not os.path.exists(lib_path):
                raise FileNotFoundError(f"Rust DLL not found at {lib_path}. Please run 'cargo build --release' in the rust_engine directory.")
            
            log.info(f"⚡ Memuat Rust HFT Engine dari: {lib_name}")
            cls._instance = ctypes.CDLL(lib_path)
            
            # Define argtypes and restypes for C-ABI functions
            # init_engine() -> *mut EngineState
            cls._instance.init_engine.restype = ctypes.c_void_p
            
            # add_tick(engine, price, qty, is_buyer_maker, ts)
            cls._instance.add_tick.argtypes = [ctypes.c_void_p, ctypes.c_double, ctypes.c_double, ctypes.c_bool, ctypes.c_uint64]
            
            # get_metrics(engine, out_metrics)
            cls._instance.get_metrics.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_double)]
            
            # free_engine(engine)
            cls._instance.free_engine.argtypes = [ctypes.c_void_p]
            
        return cls._instance

class OrderFlowEngine:
    def __init__(self, max_seconds_history=14400): 
        # Kompatibilitas dengan main.py, max_seconds_history (4-jam) dikelola natif oleh Rust (14400s)
        self.lib = RustEngineDLL.get_lib()
        self.engine_ptr = self.lib.init_engine()
        self.orderbook = {"bids": [], "asks": []}
        
    def __del__(self):
        if hasattr(self, 'engine_ptr') and self.engine_ptr:
            self.lib.free_engine(self.engine_ptr)
            
    def process_agg_trade(self, msg):
        """
        Processes Binance aggTrade WebSocket message.
        """
        try:
            ts = int(msg['T']) # Rust uses ms directly, Python backend passed ms
            price = float(msg['p'])
            qty = float(msg['q'])
            is_buyer_maker = msg['m']
            
            # O(1) Push to Rust Memory
            self.lib.add_tick(self.engine_ptr, price, qty, is_buyer_maker, ts)
            
        except Exception as e:
            log.error(f"Error processing aggTrade in Rust Engine: {e}")

    def process_depth(self, msg):
        """
        Processes Binance depth WebSocket message.
        """
        try:
            if 'bids' in msg and 'asks' in msg:
                self.orderbook['bids'] = [[float(x[0]), float(x[1])] for x in msg['bids']]
                self.orderbook['asks'] = [[float(x[0]), float(x[1])] for x in msg['asks']]
        except Exception as e:
            log.error(f"Error processing depth: {e}")

    def get_metrics(self, lookback_seconds=14400):
        """
        Mengekstrak metrik Volume Profile & VWAP dari Rust memory dalam mikrodetik.
        """
        metrics = {
            "cvd": 0.0,
            "vwap": 0.0,
            "imbalance": 0.0,
            "current_price": 0.0,
            "buy_vol": 0.0,
            "sell_vol": 0.0,
            "poc": 0.0,
            "vah": 0.0,
            "val": 0.0
        }
        
        # 1. Fetch data from Rust O(1) Array
        out_array = (ctypes.c_double * 8)()
        self.lib.get_metrics(self.engine_ptr, out_array)
        
        metrics['vwap'] = out_array[0]
        metrics['cvd'] = out_array[1]
        metrics['poc'] = out_array[2]
        metrics['val'] = out_array[3]
        metrics['vah'] = out_array[4]
        metrics['vaw'] = out_array[5]
        metrics['chop'] = out_array[6]
        metrics['current_price'] = out_array[7]
            
        # 2. Calculate Order Book Imbalance (Top 5 levels)
        if self.orderbook['bids'] and self.orderbook['asks']:
            bid_vol = sum(vol for _, vol in self.orderbook['bids'][:5])
            ask_vol = sum(vol for _, vol in self.orderbook['asks'][:5])
            total_depth_vol = bid_vol + ask_vol
            if total_depth_vol > 0:
                metrics['imbalance'] = (bid_vol - ask_vol) / total_depth_vol
                
        return metrics
