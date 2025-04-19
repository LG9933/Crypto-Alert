# ============================================
#   Crypto-Alert Bot v2
#   Crafted with ❤️ by Robin A
# ============================================

import requests
import pandas as pd
import os
import matplotlib.pyplot as plt
from pathlib import Path
from datetime import datetime

# 🧠 CONFIG
API_KEY = os.environ['TWELVE_API_KEY']
COINS = {
    "BTC/USD": {"name": "Bitcoin",  "threshold": 1.5},
    "SOL/USD": {"name": "Solana",   "threshold": 2.5},
    "LINK/USD":{"name": "Chainlink","threshold": 2.5}
}
INTERVAL = "30min"
OUTPUTSIZE = 6  # 5 + 1 voor prijsverandering & (optioneel) volume
VOLUME_SPIKE_MULTIPLIER = 1.5  # merk volume alleen als veld bestaat

# ✅ TELEGRAM HELPERS
def send_telegram_alert(message, chat_id=None):
    token = os.environ['BOT_TOKEN']
    cid   = chat_id or os.environ['CHAT_ID']
    url   = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {"chat_id": cid, "text": message, "parse_mode": "Markdown"}
    requests.post(url, data=payload)

def send_telegram_chart(image_path, chat_id=None):
    token = os.environ['BOT_TOKEN']
    cid   = chat_id or os.environ['CHAT_ID']
    url   = f"https://api.telegram.org/bot{token}/sendPhoto"
    with open(image_path, 'rb') as photo:
        files = {"photo": photo}
        data  = {"chat_id": cid}
        requests.post(url, files=files, data=data)

# Zorg dat /tmp bestaat
Path("/tmp").mkdir(parents=True, exist_ok=True)

# 🔁 MAIN LOOP (run via cron elke 30m)
for symbol, info in COINS.items():
    try:
        # 1) Data ophalen
        url = (
            f"https://api.twelvedata.com/time_series"
            f"?symbol={symbol}&interval={INTERVAL}"
            f"&outputsize={OUTPUTSIZE}&apikey={API_KEY}"
        )
        resp = requests.get(url).json()
        if "values" not in resp:
            continue

        df = pd.DataFrame(resp["values"])
        df["datetime"] = pd.to_datetime(df["datetime"])
        df["close"]    = df["close"].astype(float)
        df = df.iloc[::-1].reset_index(drop=True)  # chronologisch

        # 2) Prijsverandering laatste candle
        current_close  = df["close"].iloc[-1]
        previous_close = df["close"].iloc[-2]
        pct_change     = (current_close - previous_close) / previous_close * 100

        # 3) Optioneel volume-spike (slechts als kolom aanwezig)
        spike_alert = False
        vol_info = ""
        if "volume" in df.columns:
            df["volume"] = df["volume"].astype(float)
            vols         = df["volume"].iloc[-6:-1]  # 5 candles vóór de huidige
            avg_vol      = vols.mean()
            current_vol  = df["volume"].iloc[-1]
            if current_vol > avg_vol * VOLUME_SPIKE_MULTIPLIER:
                spike_alert = True
                vol_info    = f"🔊 *{info['name']} Volume Spike!* {int(current_vol):,}"

        # 4) Verzamel alerts
        alerts = []
        # 4a) Prijs
        if abs(pct_change) >= info["threshold"]:
            arrow = "📈" if pct_change > 0 else "📉"
            word  = "Pump" if pct_change > 0 else "Dump"
            alerts.append(f"{arrow} *{info['name']} {word}!* {pct_change:+.2f}%")

        # 4b) Volume
        if spike_alert:
            alerts.append(vol_info)

        # 5) Verstuur als er iets is
        if alerts:
            ts = datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')
            text = f"🕒 *{ts}*\n" + "\n".join(alerts)
            send_telegram_alert(text)

            # 📊 Mini-grafiek (5 candles + huidige)
            df_chart    = df.iloc[-6:].copy()
            chart_file  = Path(f"/tmp/chart_{symbol.replace('/','_')}.png")
            plt.figure(figsize=(4,2))
            plt.plot(df_chart["datetime"], df_chart["close"], linewidth=1.5)
            plt.title(f"{info['name']} Price")
            plt.tight_layout()
            plt.savefig(chart_file)
            plt.close()

            send_telegram_chart(str(chart_file))

    except Exception as e:
        # Foutmelding sturen zonder te crashen
        err = f"[ERROR] {symbol}: {e}"
        send_telegram_alert(err)
