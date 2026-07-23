import os
import requests
import zipfile
import logging
from tqdm import tqdm

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
log = logging.getLogger(__name__)

def download_and_extract_monthly_aggtrades(symbol="BTCUSDT", year=2026, month=6, base_dir="data/historical_aggtrades"):
    """
    Downloads and extracts Binance Data Vision monthly aggTrades zip files.
    """
    os.makedirs(base_dir, exist_ok=True)
    
    file_name = f"{symbol}-aggTrades-{year}-{month:02d}.zip"
    url = f"https://data.binance.vision/data/futures/um/monthly/aggTrades/{symbol}/{file_name}"
    zip_path = os.path.join(base_dir, file_name)
    extract_path = base_dir
    csv_file = os.path.join(base_dir, f"{symbol}-aggTrades-{year}-{month:02d}.csv")
    
    if os.path.exists(csv_file):
        log.info(f"File {csv_file} sudah ada. Melewati proses unduhan.")
        return csv_file
        
    log.info(f"Mengunduh data tick historis dari: {url}")
    
    try:
        response = requests.get(url, stream=True)
        response.raise_for_status()
        
        total_size = int(response.headers.get('content-length', 0))
        
        with open(zip_path, 'wb') as file, tqdm(
            desc=file_name,
            total=total_size,
            unit='iB',
            unit_scale=True,
            unit_divisor=1024,
        ) as bar:
            for data in response.iter_content(chunk_size=1024):
                size = file.write(data)
                bar.update(size)
                
        log.info(f"Berhasil mengunduh ke {zip_path}. Mengekstrak...")
        
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(extract_path)
            
        log.info("Ekstraksi selesai. Menghapus file ZIP...")
        os.remove(zip_path)
        
        return csv_file
        
    except requests.exceptions.HTTPError as e:
        log.error(f"Gagal mengunduh data. File mungkin belum tersedia di Binance Vision: {e}")
        if os.path.exists(zip_path):
            os.remove(zip_path)
        return None
    except Exception as e:
        log.error(f"Terjadi kesalahan: {e}")
        return None

if __name__ == "__main__":
    download_and_extract_monthly_aggtrades("BTCUSDT", 2026, 6)
