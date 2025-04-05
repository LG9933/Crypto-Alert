import requests
 import pandas as pd
 import os
 import matplotlib.pyplot as plt
 import datetime
 
 # 🧠 CONFIG
 API_KEY = os.environ['TWELVE_API_KEY']
 @@ -13,6 +15,7 @@
 }
 INTERVAL = "1h"
 RSI_PERIOD = 14
 MA_PERIOD = 50
 
 # ✅ TELEGRAM
 def send_telegram_alert(message, chat_id=None):
 @@ -23,11 +26,20 @@ def send_telegram_alert(message, chat_id=None):
     payload = {"chat_id": final_chat_id, "text": message}
     requests.post(url, data=payload)
 
 def send_telegram_chart(image_path, chat_id=None):
     token = os.environ['BOT_TOKEN']
     default_chat_id = os.environ['CHAT_ID']
     final_chat_id = chat_id if chat_id else default_chat_id
     url = f"https://api.telegram.org/bot{token}/sendPhoto"
     with open(image_path, 'rb') as photo:
         files = {"photo": photo}
         data = {"chat_id": final_chat_id}
         requests.post(url, files=files, data=data)
 
 # 🔁 MAIN LOOP
 for symbol, name in COINS.items():
     try:
         # Haal candle data op (voor RSI + % change)
         outputsize = max(RSI_PERIOD, 2)  # minimaal 2 candles nodig voor % change
         outputsize = max(RSI_PERIOD, MA_PERIOD, 2)
         url = f"https://api.twelvedata.com/time_series?symbol={symbol}&interval={INTERVAL}&outputsize={outputsize}&apikey={API_KEY}"
         r = requests.get(url)
         data = r.json()
 @@ -41,10 +53,11 @@ def send_telegram_alert(message, chat_id=None):
             continue
 
         df = pd.DataFrame(data["values"])
         df["datetime"] = pd.to_datetime(df["datetime"])
         df["close"] = df["close"].astype(float)
         df = df[::-1]  # draai om naar chronologische volgorde
         df = df[::-1].reset_index(drop=True)
 
         # RSI berekenen over 14 candles
         # RSI berekening
         delta = df["close"].diff()
         gain = delta.where(delta > 0, 0.0)
         loss = -delta.where(delta < 0, 0.0)
 @@ -54,29 +67,58 @@ def send_telegram_alert(message, chat_id=None):
         rsi = 100 - (100 / (1 + rs))
         last_rsi = rsi.iloc[-1]
 
         # % change over laatste 2 candles (2 uur)
         # % change laatste 2 candles
         if len(df) >= 2:
             change_pct = ((df["close"].iloc[-1] - df["close"].iloc[-2]) / df["close"].iloc[-2]) * 100
         else:
             change_pct = 0.0
 
         # MA50 berekenen
         df["ma"] = df["close"].rolling(window=MA_PERIOD).mean()
         in_uptrend = df["close"].iloc[-1] > df["ma"].iloc[-1]
 
         # Bericht opstellen
         emoji = "📉" if last_rsi < 30 else "📈" if last_rsi > 70 else "🔄"
         status = (
             "OVERSOLD" if last_rsi < 30 else
             "OVERBOUGHT" if last_rsi > 70 else
             "NEUTRAAL (test alert)"
         )
         trend = "↑ UP" if in_uptrend else "↓ DOWN"
 
         msg = (
             f"[{name}] RSI = {last_rsi:.2f} — {status} {emoji}\n"
             f"Change (2h): {change_pct:.2f}%"
             f"Change (2h): {change_pct:.2f}%\n"
             f"Trend: {trend} (MA{MA_PERIOD})"
         )
 
         # Telegram versturen
         # Grafiek maken
         fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(8,6), sharex=True, gridspec_kw={'height_ratios': [2, 1]})
         ax1.plot(df["datetime"], df["close"], label="Close", linewidth=1.5)
         ax1.plot(df["datetime"], df["ma"], label=f"MA{MA_PERIOD}", linestyle="--")
         ax1.set_title(f"{name} Price + MA{MA_PERIOD}")
         ax1.legend()
 
         ax2.plot(df["datetime"], rsi, label="RSI", color="purple")
         ax2.axhline(70, color="red", linestyle="--", linewidth=0.8)
         ax2.axhline(30, color="green", linestyle="--", linewidth=0.8)
         ax2.set_title("RSI")
         ax2.set_ylim(0, 100)
         ax2.legend()
 
         plt.tight_layout()
         image_path = f"/tmp/chart_{symbol.replace('/', '_')}.png"
         plt.savefig(image_path)
         plt.close()
 
         # Verstuur alerts en grafiek
         send_telegram_alert(msg)
         send_telegram_chart(image_path)
 
         extra = os.environ.get('EXTRA_CHAT_ID')
         if extra:
             send_telegram_alert(msg, chat_id=extra)
             send_telegram_chart(image_path, chat_id=extra)
 
     except Exception as e:
         msg = f"[ERROR] Exception bij {name}: {str(e)}"
