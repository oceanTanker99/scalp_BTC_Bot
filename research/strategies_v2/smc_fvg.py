import pandas as pd
import numpy as np

class SMC_FVG_Engine:
    def __init__(self):
        # Simpan FVG yang belum tersentuh (unmitigated)
        # Format: {"top": float, "bottom": float, "time": int}
        self.active_bullish_fvgs = []
        self.active_bearish_fvgs = []

    def analyze(self, df_5m: pd.DataFrame):
        """
        Analisis per candle untuk mendeteksi FVG baru dan mengecek apakah 
        harga saat ini sedang memantul (mitigation) di FVG lama.
        """
        if len(df_5m) < 3:
            return "NEUTRAL", 0.0, 0.0, {}

        current = df_5m.iloc[-1]
        prev1 = df_5m.iloc[-2]
        prev2 = df_5m.iloc[-3]
        
        price = current['close']
        
        # 1. Deteksi FVG Baru pada susunan 3 candle terakhir
        # Syarat FVG Valid:
        # A. Harus ada GAP (C1 High < C3 Low untuk Bullish)
        # B. Candle C2 (tengah) harus memiliki Volume > Rata-rata 20 candle (Displacement)
        # C. Ukuran GAP minimal 0.05% dari harga
        
        # Hitung rata-rata volume (bisa didekati dengan rata-rata 3 candle terakhir karena ini simple script)
        avg_vol = (current['volume'] + prev1['volume'] + prev2['volume']) / 3
        
        # Bullish FVG: Low dari candle saat ini > High dari candle ke-3 kebelakang
        if current['low'] > prev2['high'] and prev1['volume'] > avg_vol * 1.5:
            fvg_top = current['low']
            fvg_bottom = prev2['high']
            gap_size_pct = (fvg_top - fvg_bottom) / price * 100
            
            if gap_size_pct > 0.05: # Minimal gap 0.05%
                self.active_bullish_fvgs.append({
                    "top": fvg_top, 
                    "bottom": fvg_bottom, 
                    "time": current['timestamp']
                })
            
        # Bearish FVG: High dari candle saat ini < Low dari candle ke-3 kebelakang
        if current['high'] < prev2['low'] and prev1['volume'] > avg_vol * 1.5:
            fvg_top = prev2['low']
            fvg_bottom = current['high']
            gap_size_pct = (fvg_top - fvg_bottom) / price * 100
            
            if gap_size_pct > 0.05:
                self.active_bearish_fvgs.append({
                    "top": fvg_top, 
                    "bottom": fvg_bottom, 
                    "time": current['timestamp']
                })
            
        # Batasi memori hanya 5 FVG terakhir yang aktif
        self.active_bullish_fvgs = self.active_bullish_fvgs[-5:]
        self.active_bearish_fvgs = self.active_bearish_fvgs[-5:]

        # 2. Cek Mitigasi (Harga kembali menyentuh zona FVG)
        signal = "NEUTRAL"
        sl_distance = 0.0
        
        # Cek Bullish Mitigation (Harga turun ke area Bullish FVG)
        # Kondisi: Harga close berada di dalam FVG, atau wick menyentuh FVG
        for fvg in self.active_bullish_fvgs[:]: # copy list untuk iterasi
            if fvg['bottom'] <= current['low'] <= fvg['top'] or fvg['bottom'] <= current['close'] <= fvg['top']:
                # Ini adalah Mitigation! Sinyal LONG
                signal = "LONG"
                sl_distance = (price - fvg['bottom'] * 0.999) / price # SL sedikit di bawah FVG bottom
                self.active_bullish_fvgs.remove(fvg) # Hapus FVG karena sudah termitigasi
                break
                
        # Cek Bearish Mitigation (Harga naik ke area Bearish FVG)
        if signal == "NEUTRAL":
            for fvg in self.active_bearish_fvgs[:]:
                if fvg['bottom'] <= current['high'] <= fvg['top'] or fvg['bottom'] <= current['close'] <= fvg['top']:
                    signal = "SHORT"
                    sl_distance = (fvg['top'] * 1.001 - price) / price # SL sedikit di atas FVG top
                    self.active_bearish_fvgs.remove(fvg)
                    break
                    
        # Pembersihan FVG yang Invalidated (ditembus sepenuhnya)
        self.active_bullish_fvgs = [f for f in self.active_bullish_fvgs if current['close'] > f['bottom']]
        self.active_bearish_fvgs = [f for f in self.active_bearish_fvgs if current['close'] < f['top']]

        context = {
            "price": price,
            "active_bull_fvgs": len(self.active_bullish_fvgs),
            "active_bear_fvgs": len(self.active_bearish_fvgs)
        }

        # Hindari SL distance negatif (jika harga sudah jauh menembus saat close)
        if sl_distance <= 0:
            sl_distance = 0.005 # Default 0.5% SL

        return signal, price, sl_distance, context
