# btc_alert.py

import requests
import pandas as pd
import os

# 🧠 CONFIG
API_KEY = os.environ['TWELVE_API_KEY']
COINS = {
    "BTC/USD": "Bitcoin",
    "SOL/USD": "Solana",
    "LINK/USD": "Chainlink"
}
INTERVAL = "1h"
RSI_PERIOD = 14

# ✅ TELEGRAM
def send_telegram_alert(message, chat_id=None):
    token = os.environ['BOT_TOKEN']
    default_chat_id = os.environ['CHAT_ID']
    final_chat_id = chat_id if chat_id else default_chat_id
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {"chat_id": final_chat_id, "text": message}
    requests.post(url, data=payload)

# 🔁 MAIN LOOP
for symbol, name in COINS.items():
    try:
        # Haal candle data op (voor RSI + % change)
        outputsize = max(RSI_PERIOD, 2)  # minimaal 2 candles nodig voor % change
        url = f"https://api.twelvedata.com/time_series?symbol={symbol}&interval={INTERVAL}&outputsize={outputsize}&apikey={API_KEY}"
        r = requests.get(url)
        data = r.json()

        if "values" not in data:
            msg = f"[ERROR] Geen data voor {name}: {data.get('message', 'Onbekende fout')}"
            send_telegram_alert(msg)
            extra = os.environ.get('EXTRA_CHAT_ID')
            if extra:
                send_telegram_alert(msg, chat_id=extra)
            continue

        df = pd.DataFrame(data["values"])
        df["close"] = df["close"].astype(float)
        df = df[::-1]  # draai om naar chronologische volgorde

        # RSI berekenen over 14 candles
        delta = df["close"].diff()
        gain = delta.where(delta > 0, 0.0)
        loss = -delta.where(delta < 0, 0.0)
        avg_gain = gain.rolling(window=RSI_PERIOD).mean()
        avg_loss = loss.rolling(window=RSI_PERIOD).mean()
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        last_rsi = rsi.iloc[-1]

        # % change over laatste 2 candles (2 uur)
        if len(df) >= 2:
            change_pct = ((df["close"].iloc[-1] - df["close"].iloc[-2]) / df["close"].iloc[-2]) * 100
        else:
            change_pct = 0.0

        # Bericht opstellen
        emoji = "📉" if last_rsi < 30 else "📈" if last_rsi > 70 else "🔄"
        status = (
            "OVERSOLD" if last_rsi < 30 else
            "OVERBOUGHT" if last_rsi > 70 else
            "NEUTRAAL (test alert)"
        )
        msg = (
            f"[{name}] RSI = {last_rsi:.2f} — {status} {emoji}\n"
            f"Change (2h): {change_pct:.2f}%"
        )

        # Telegram versturen
        send_telegram_alert(msg)
        extra = os.environ.get('EXTRA_CHAT_ID')
        if extra:
            send_telegram_alert(msg, chat_id=extra)

    except Exception as e:
        msg = f"[ERROR] Exception bij {name}: {str(e)}"
        send_telegram_alert(msg)
        extra = os.environ.get('EXTRA_CHAT_ID')
        if extra:
            send_telegram_alert(msg, chat_id=extra)
