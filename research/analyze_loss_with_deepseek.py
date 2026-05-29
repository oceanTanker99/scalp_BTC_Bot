import os
import json
import asyncio
from openai import AsyncOpenAI
from dotenv import load_dotenv

load_dotenv()

DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")

async def main():
    if not os.path.exists('logs/pure_loss_cases.json'):
        print("File logs/pure_loss_cases.json tidak ditemukan. Jalankan loss_extractor.py dulu.")
        return

    with open('logs/pure_loss_cases.json', 'r') as f:
        loss_cases = json.load(f)

    print(f"Menganalisis {len(loss_cases)} kasus Pure Loss menggunakan DeepSeek AI Engine...")

    client = AsyncOpenAI(
        api_key=DEEPSEEK_API_KEY,
        base_url="https://api.deepseek.com/v1"
    )

    prompt = f"""
I am building a 5-minute timeframe mean-reversion scalping bot for BTCUSDT. 
The bot enters LONG when RSI is oversold and price touches the lower Bollinger Band. 
It enters SHORT when RSI is overbought and price touches the upper Bollinger Band. 
We also have a MACRO filter (price > EMA200 for LONG, price < EMA200 for SHORT).

However, I just ran a 90-day backtest and collected {len(loss_cases)} "Pure Loss" cases. 
A Pure Loss is a trade that hit our Stop Loss and DID NOT subsequently hit our Take Profit within 2 hours. 
This means our core price action analysis was completely wrong, and the market continued to move against us.

Here is the data for the {len(loss_cases)} losing trades. For each trade, you will see the entry signal and the 10 candles leading up to the entry.

{json.dumps(loss_cases, indent=2)}

YOUR TASK:
1. Identify 2 or 3 common technical patterns that appear in the candlesticks, volume, or indicators leading up to these pure losses. What did we miss? Why did price continue to move against our mean-reversion expectation?
2. Based on your findings, formulate a strict, robust python IF-ELSE pseudocode logic that can act as a pre-filter. If this filter triggers, the bot should SKIP the signal.
3. Be specific. Do not give generic advice. Point out exactly which candlesticks or patterns caused these losses based on the JSON data provided.
"""

    try:
        target_model = "deepseek-reasoner"
        print(f"Mencoba memanggil model: {target_model}...")
        
        response = await client.chat.completions.create(
            model=target_model,
            messages=[
                {"role": "system", "content": "You are an elite quantitative trading AI expert."},
                {"role": "user", "content": prompt}
            ]
        )
            
        message = response.choices[0].message
        reasoning_thought = getattr(message, 'reasoning_content', '')
        result = message.content
        
        if not os.path.exists('logs'):
            os.makedirs('logs')
            
        with open('logs/loss_deepseek_analysis.md', 'w', encoding='utf-8') as f:
            if reasoning_thought:
                f.write("### Proses Berpikir (Reasoning):\n" + reasoning_thought + "\n\n")
            f.write("### Jawaban Akhir:\n" + result)
            
        print("\n=== HASIL ANALISIS KERUGIAN (DeepSeek R1) ===")
        if reasoning_thought:
            print("[Reasoning Process]...")
            print(reasoning_thought[:500] + "... (dipotong)")
        print("\n[Final Result]")
        print(result)
        print("===============================\n")
        print("Analisis telah disimpan di logs/loss_deepseek_analysis.md")
        
    except Exception as e:
        print(f"API Error: {e}")

if __name__ == "__main__":
    asyncio.run(main())
