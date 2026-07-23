import os
import requests
import zipfile
import time

def download_and_extract(year, month):
    base_url = f"https://data.binance.vision/data/futures/um/monthly/aggTrades/BTCUSDT/BTCUSDT-aggTrades-{year}-{month}.zip"
    zip_path = f"data/historical_aggtrades/BTCUSDT-aggTrades-{year}-{month}.zip"
    csv_path = f"data/historical_aggtrades/BTCUSDT-aggTrades-{year}-{month}.csv"
    
    if os.path.exists(csv_path):
        print(f"File {csv_path} sudah ada. Melewati unduhan.")
        return
        
    os.makedirs(os.path.dirname(zip_path), exist_ok=True)
    
    print(f"Mengunduh {base_url}...")
    try:
        response = requests.get(base_url, stream=True)
        response.raise_for_status()
        
        with open(zip_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
                
        print(f"Berhasil mengunduh ke {zip_path}")
        
        print(f"Mengekstrak {zip_path}...")
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(os.path.dirname(zip_path))
            
        print(f"Menghapus file zip untuk menghemat ruang...")
        os.remove(zip_path)
        print(f"Selesai memproses {year}-{month}")
        
    except Exception as e:
        print(f"Error memproses {year}-{month}: {e}")

if __name__ == "__main__":
    months = ["01", "02", "03"]
    for m in months:
        download_and_extract("2026", m)
    print("Seluruh unduhan selesai!")
