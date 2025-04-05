# btc_alert.py

import requests
import pandas as pd
import ta
import os

# Telegram alert functie
def send_telegram_alert(message, custom_chat_id=None):
    token = os.environ['BOT_TOKEN']
    chat_id = custom_chat_id if custom_chat_id else os.environ['CHAT_ID']
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": message
    }
    requests.post(url, data=payload)

# Coins die je wil checken
coins = ["BTCUSDT", "SOLUSDT", "LINKUSDT"]

# Extra ontvanger toevoegen (optioneel)
extra_chat_id = os.environ.get('EXTRA_CHAT_ID')

for coin in coins:
    url = f"https://api.binance.com/api/v3/klines?symbol={coin}&interval=1h&limit=100"
    try:
        resp = requests.get(url)
        data = resp.json()

        # Check of de data geldig is (lijst met candles)
        if not isinstance(data, list):
            msg = f"[ERROR] Geen geldige data voor {coin}: {data}"
            send_telegram_alert(msg)
            if extra_chat_id:
                send_telegram_alert(msg, custom_chat_id=extra_chat_id)
            continue

        closes = [float(candle[4]) for candle in data]
        df = pd.DataFrame(closes, columns=["close"])

        rsi = ta.momentum.RSIIndicator(close=df["close"], window=14).rsi().iloc[-1]

        pct_change = ((df["close"].iloc[-1] - df["close"].iloc[0]) / df["close"].iloc[0]) * 100

        if rsi < 30:
            message = f"[{coin}] RSI = {rsi:.2f} — OVERSOLD! 📉\nChange (100h): {pct_change:.2f}%"
        elif rsi > 70:
            message = f"[{coin}] RSI = {rsi:.2f} — OVERBOUGHT! 📈\nChange (100h): {pct_change:.2f}%"
        else:
            message = f"[{coin}] RSI = {rsi:.2f} — NEUTRAAL\nChange (100h): {pct_change:.2f}% (test alert)"

        send_telegram_alert(message)
        if extra_chat_id:
            send_telegram_alert(message, custom_chat_id=extra_chat_id)

    except Exception as e:
        msg = f"[ERROR] Exception bij {coin}: {str(e)}"
        send_telegram_alert(msg)
        if extra_chat_id:
            send_telegram_alert(msg, custom_chat_id=extra_chat_id)
