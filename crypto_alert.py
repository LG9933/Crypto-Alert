# ============================================
#   Crypto-Alert Bot v2
#   Crafted with ❤️ by Robin A
# ============================================

import requests
import pandas as pd
import os
from datetime import datetime
import sys

# ── Detect manual run via GitHub Actions ──
manual_run = os.environ.get('GITHUB_EVENT_NAME') == 'workflow_dispatch'

# 🧠 CONFIG
API_KEY = os.environ['TWELVE_API_KEY']
COINS = {
    "BTC/USD": {"name": "Bitcoin",   "threshold": 0.8},
    "SOL/USD": {"name": "Solana",    "threshold": 1.6},
    "LINK/USD": {"name": "Chainlink","threshold": 1.6}
}
INTERVAL    = "15min"
OUTPUTSIZE  = 5   # last 5 candles for price change
BB_PERIOD   = 20  # Bollinger Bands period
NBDEVUP     = 2   # upper band deviation
NBDEVDN     = 2   # lower band deviation

# ✅ TELEGRAM HELPERS
def send_telegram_alert(message, chat_id=None):
    token = os.environ['BOT_TOKEN']
    cid   = chat_id or os.environ['CHAT_ID']
    url   = f"https://api.telegram.org/bot{token}/sendMessage"
    requests.post(url, data={
        "chat_id": cid,
        "text": message,
        "parse_mode": "Markdown"
    })

# ── HELPERS ──
def fetch_time_series(symbol):
    return requests.get(
        "https://api.twelvedata.com/time_series",
        params={
            "symbol": symbol,
            "interval": INTERVAL,
            "outputsize": OUTPUTSIZE,
            "apikey": API_KEY
        }
    ).json()

def fetch_bbands(symbol):
    return requests.get(
        "https://api.twelvedata.com/bbands",
        params={
            "symbol": symbol,
            "interval": INTERVAL,
            "time_period": BB_PERIOD,
            "series_type": "close",
            "nbdevup": NBDEVUP,
            "nbdevdn": NBDEVDN,
            "apikey": API_KEY
        }
    ).json()

# ── TEST‑RUN MODE ──
if manual_run:
    ts = datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')
    lines = [f"🧪 *Test Run* {ts}"]

    for symbol, info in COINS.items():
        name = info['name']
        # Fetch price data
        data = fetch_time_series(symbol)
        if "values" not in data:
            lines.append(f"*{name}* – ❌ no data")
            continue
        df = pd.DataFrame(data["values"]).astype({"close": float})
        df = df.iloc[::-1].reset_index(drop=True)
        curr, prev = df["close"].iloc[-1], df["close"].iloc[-2]
        pct = (curr - prev) / prev * 100
        price_arrow = "🚀" if pct > 0 else "🚨"
        verb = "rocketed" if pct > 0 else "plunged"
        price_line = f"{price_arrow} {name} just {verb} {pct:+.2f}% in 15 min!"

        # Fetch BBANDS data
        bb = fetch_bbands(symbol)
        bb_line = f"⚪ {name} within BB range"
        if "values" in bb and bb["values"]:
            last = bb["values"][-1]
            upper = float(last.get("upperband", last.get("uband", 0)))
            lower = float(last.get("lowerband", last.get("lband", 0)))
            if curr > upper:
                bb_line = f"📈 {name} broke above upper BB (Bullish upper band)"
            elif curr < lower:
                bb_line = f"📉 {name} fell below lower BB (Bearish lower band)"

        lines.append(price_line)
        lines.append(bb_line)

    send_telegram_alert("\n".join(lines))
    sys.exit()

# ── NORMAL ALERT MODE (cron) ──
for symbol, info in COINS.items():
    try:
        name = info['name']
        # Price data
        data = fetch_time_series(symbol)
        if "values" not in data:
            continue
        df = pd.DataFrame(data["values"]).astype({"close": float})
        df = df.iloc[::-1].reset_index(drop=True)
        curr, prev = df["close"].iloc[-1], df["close"].iloc[-2]
        pct = (curr - prev) / prev * 100

        alerts = []
        # Price trigger
        if abs(pct) >= info["threshold"]:
            price_arrow = "🚀" if pct > 0 else "🚨"
            verb = "rocketed" if pct > 0 else "plunged"
            alerts.append(f"{price_arrow} {name} just {verb} {pct:+.2f}% in 15 min!")

        # BBANDS trigger
        bb = fetch_bbands(symbol)
        if "values" in bb and bb["values"]:
            last = bb["values"][-1]
            upper = float(last.get("upperband", last.get("uband", 0)))
            lower = float(last.get("lowerband", last.get("lband", 0)))
            if curr > upper:
                alerts.append(f"📈 {name} broke above upper BB (Bullish upper band)")
            elif curr < lower:
                alerts.append(f"📉 {name} fell below lower BB (Bearish lower band)")

        # Send alerts
        if alerts:
            ts = datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')
            send_telegram_alert(f"🕒 *{ts}*\n" + "\n".join(alerts))

    except Exception as e:
        send_telegram_alert(f"[ERROR] {symbol}: {e}")
