import asyncio
from binance import AsyncClient
from config.config import BINANCE_API_KEY, BINANCE_SECRET_KEY

async def test_env(testnet):
    try:
        client = await AsyncClient.create(api_key=BINANCE_API_KEY, api_secret=BINANCE_SECRET_KEY, testnet=testnet)
        try:
            acc = await client.futures_account()
            balances = [b for b in acc.get('assets', []) if float(b['walletBalance']) > 0]
            print(f"[{'TESTNET' if testnet else 'MAINNET'}] BERHASIL CONNECT! Saldo Futures:")
            if balances:
                for b in balances:
                    print(f"  - {b['asset']}: {b['walletBalance']}")
            else:
                print("  - KOSONG (0.00)")
            return True
        except Exception as e:
            print(f"[{'TESTNET' if testnet else 'MAINNET'}] Gagal Futures: {e}")
            return False
        finally:
            await client.close_connection()
    except Exception as e:
        print(f"[{'TESTNET' if testnet else 'MAINNET'}] Error init: {e}")
        return False

async def main():
    print("Mencoba di MAINNET...")
    res_main = await test_env(False)
    
    print("\nMencoba di TESTNET...")
    res_test = await test_env(True)

if __name__ == "__main__":
    asyncio.run(main())
