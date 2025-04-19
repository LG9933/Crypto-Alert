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
import sys

# ── Detect manual run via GitHub Actions ──
manual_run = os.environ.get('GITHUB_EVENT_NAME') == 'workflow_dispatch'

# 🧠 CONFIG
API_KEY = os.environ['TWELVE_API_KEY']
COINS = {
    "BTC/USD": {"name": "Bitcoin",  "threshold": 1.5},
    "SOL/USD": {"name": "Solana",   "threshold": 2.5},
    "LINK/USD":{"name": "Chainlink","threshold": 2.5}
}
INTERVAL = "30min"
OUTPUTSIZE = 6
VOLUME_SPIKE_MULTIPLIER = 1.5

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

# ── Manual/Test Mode ──
if manual_run:
    summaries = []
    for symbol, info in COINS.items():
        # Haal data
        resp = requests.get(
            "https://api.twelvedata.com/time_series",
            params={
                "symbol": symbol,
                "interval": INTERVAL,
                "outputsize": OUTPUTSIZE,
                "apikey": API_KEY
            }
        ).json()
        if "values" not in resp:
            summaries.append(f"*{info['name']}* – ❌ geen data")
            continue

        df = pd.DataFrame(resp["values"])
        df["close"] = df["close"].astype(float)
        df = df.iloc[::-1].reset_index(drop=True)

        # Prijs en change
        current_close  = df["close"].iloc[-1]
        previous_close = df["close"].iloc[-2]
        pct_change     = (current_close - previous_close) / previous_close * 100

        # Volume (optioneel)
        if "volume" in df.columns:
            df["volume"] = df["volume"].astype(float)
            vols        = df["volume"].iloc[-6:-1]
            avg_vol     = vols.mean()
            current_vol = df["volume"].iloc[-1]
            vol_str     = f"AvgVol {avg_vol:,.0f}, CurVol {current_vol:,.0f}"
        else:
            vol_str     = "Volumedata niet beschikbaar"

        summaries.append(
            f"*{info['name']}*\n"
            f"Price: {current_close:.2f}, Δ {pct_change:+.2f}%\n"
            f"{vol_str}"
        )

    text = "🧪 *Test Run*\n" + "\n\n".join(summaries)
    send_telegram_alert(text)
    sys.exit()


# ── Normal Alert Mode (cron) ──
for symbol, info in COINS.items():
    try:
        # 1) Data ophalen
        resp = requests.get(
            "https://api.twelvedata.com/time_series",
            params={
                "symbol": symbol,
                "interval": INTERVAL,
                "outputsize": OUTPUTSIZE,
                "apikey": API_KEY
            }
        ).json()
        if "values" not in resp:
            continue

        df = pd.DataFrame(resp["values"])
        df["datetime"] = pd.to_datetime(df["datetime"])
        df["close"]    = df["close"].astype(float)
        df = df.iloc[::-1].reset_index(drop=True)

        # 2) Prijsverandering
        current_close  = df["close"].iloc[-1]
        previous_close = df["close"].iloc[-2]
        pct_change     = (current_close - previous_close) / previous_close * 100

        # 3) Volume-spike?
        spike_alert = False
        vol_msg     = ""
        if "volume" in df.columns:
            df["volume"] = df["volume"].astype(float)
            vols         = df["volume"].iloc[-6:-1]
            avg_vol      = vols.mean()
            current_vol  = df["volume"].iloc[-1]
            if current_vol > avg_vol * VOLUME_SPIKE_MULTIPLIER:
                spike_alert = True
                vol_msg     = f"🔊 *{info['name']} Volume Spike!* {int(current_vol):,}"

        # 4) Bouw alerts
        alerts = []
        if abs(pct_change) >= info["threshold"]:
            arrow = "📈" if pct_change > 0 else "📉"
            word  = "Pump" if pct_change > 0 else "Dump"
            alerts.append(f"{arrow} *{info['name']} {word}!* {pct_change:+.2f}%")
        if spike_alert:
            alerts.append(vol_msg)

        # 5) Verstuur
        if alerts:
            ts = datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')
            send_telegram_alert(f"🕒 *{ts}*\n" + "\n".join(alerts))

            # Mini-grafiek
            df_chart   = df.iloc[-6:].copy()
            chart_file = Path(f"/tmp/chart_{symbol.replace('/','_')}.png")
            plt.figure(figsize=(4,2))
            plt.plot(df_chart["datetime"], df_chart["close"], linewidth=1.5)
            plt.title(f"{info['name']} Price")
            plt.tight_layout()
            plt.savefig(chart_file)
            plt.close()

            send_telegram_chart(str(chart_file))

    except Exception as e:
        send_telegram_alert(f"[ERROR] {symbol}: {e}")
