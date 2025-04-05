import requests
import pandas as pd
import ta
import os

# Telegram alert functie
def send_telegram_alert(message):
    token = os.environ['BOT_TOKEN']
    chat_id = os.environ['CHAT_ID']
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": message
    }
    requests.post(url, data=payload)

# Coins die je wil checken
coins = ["BTCUSDT", "SOLUSDT", "LINKUSDT"]

for coin in coins:
    url = f"https://api.binance.com/api/v3/klines?symbol={coin}&interval=1h&limit=100"
    resp = requests.get(url)
    data = resp.json()

    closes = [float(candle[4]) for candle in data]
    df = pd.DataFrame(closes, columns=["close"])

    rsi = ta.momentum.RSIIndicator(close=df["close"], window=14).rsi().iloc[-1]

    if rsi < 30:
        message = f"[{coin}] RSI = {rsi:.2f} — OVERSOLD! 📉"
        send_telegram_alert(message)
    elif rsi > 70:
        message = f"[{coin}] RSI = {rsi:.2f} — OVERBOUGHT! 📈"
        send_telegram_alert(message)
    else:
        print(f"{coin}: RSI = {rsi:.2f}, geen alert nodig.")
