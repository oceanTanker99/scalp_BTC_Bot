import asyncio
from binance import AsyncClient
from config.config import BINANCE_API_KEY, BINANCE_SECRET_KEY, BINANCE_TESTNET

async def main():
    try:
        client = await AsyncClient.create(api_key=BINANCE_API_KEY, api_secret=BINANCE_SECRET_KEY, testnet=BINANCE_TESTNET)
        
        # Check Spot Account
        print("\n--- Pengecekan Dompet SPOT ---")
        try:
            spot_acc = await client.get_account()
            spot_balances = [b for b in spot_acc['balances'] if float(b['free']) > 0 or float(b['locked']) > 0]
            if spot_balances:
                for b in spot_balances:
                    print(f"[{b['asset']}] Free: {b['free']}, Locked: {b['locked']}")
            else:
                print("Dompet Spot kosong.")
        except Exception as e:
            print("Gagal cek Spot:", e)

        # Check Futures Account
        print("\n--- Pengecekan Dompet FUTURES (USD-M) ---")
        try:
            fut_acc = await client.futures_account()
            fut_balances = [b for b in fut_acc['assets'] if float(b['walletBalance']) > 0]
            if fut_balances:
                for b in fut_balances:
                    print(f"[{b['asset']}] Saldo: {b['walletBalance']}")
            else:
                print("Dompet Futures KOSONG (0.00000000)")
        except Exception as e:
            print("Gagal cek Futures:", e)

        await client.close_connection()
    except Exception as e:
        print("Error koneksi API:", e)

if __name__ == "__main__":
    asyncio.run(main())
