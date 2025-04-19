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
INTERVAL       = "15min"
OUTPUTSIZE     = 5   # last 5 candles for ATR comparison
ATR_PERIOD     = 14  # candles for ATR
ATR_MULTIPLIER = 1.2 # True Range ≥1.2×ATR → volatility spike

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

def fetch_atr(symbol):
    return requests.get(
        "https://api.twelvedata.com/atr",
        params={
            "symbol": symbol,
            "interval": INTERVAL,
            "time_period": ATR_PERIOD,
            "outputsize": 2,
            "apikey": API_KEY
        }
    ).json()

# ── TEST‑RUN MODE ──
if manual_run:
    ts = datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')
    lines = [f"🧪 *Test Run* {ts}"]
    for symbol, info in COINS.items():
        # Price data
        data = fetch_time_series(symbol)
        if "values" not in data:
            lines.append(f"*{info['name']}* – ❌ no data")
            continue
        df = pd.DataFrame(data["values"])  
        df = df.astype({"close": float, "high": float, "low": float})
        df = df.iloc[::-1].reset_index(drop=True)
        curr, prev = df["close"].iloc[-1], df["close"].iloc[-2]
        pct = (curr - prev) / prev * 100
        price_arrow = "🚀" if pct > 0 else "🚨"
        verb = "rocketed" if pct > 0 else "plunged"
        price_line = f"{price_arrow} {info['name']} just {verb} {pct:+.2f}% in 15 min!"

        # ATR data
        atr_data = fetch_atr(symbol)
        atr_val = atr_prev = None
        if atr_data.get("values"):
            vals = atr_data["values"]
            try:
                atr_prev = float(vals[-2].get("ATR") or vals[-2].get("atr"))
                atr_val  = float(vals[-1].get("ATR") or vals[-1].get("atr"))
            except:
                pass
        if atr_val and atr_prev:
            delta = atr_val - atr_prev
            dir_arrow = "📈" if delta > 0 else "📉"
            delta_pct = delta / atr_prev * 100
            atr_line = f"{dir_arrow} Volatility {'up' if delta>0 else 'down'} (ATR {dir_arrow} {delta_pct:+.2f}%)"
        else:
            atr_line = "📈 Volatility data unavailable"

        lines.append(price_line)
        lines.append(atr_line)

    send_telegram_alert("\n".join(lines))
    sys.exit()

# ── NORMAL ALERT MODE (cron) ──
for symbol, info in COINS.items():
    try:
        # Price data
        data = fetch_time_series(symbol)
        if "values" not in data:
            continue
        df = pd.DataFrame(data["values"])
        df = df.astype({"close": float, "high": float, "low": float})
        df = df.iloc[::-1].reset_index(drop=True)
        curr, prev = df["close"].iloc[-1], df["close"].iloc[-2]
        pct = (curr - prev) / prev * 100

        alerts = []
        # Price trigger
        if abs(pct) >= info["threshold"]:
            price_arrow = "🚀" if pct > 0 else "🚨"
            verb = "rocketed" if pct > 0 else "plunged"
            alerts.append(
                f"{price_arrow} {info['name']} just {verb} {pct:+.2f}% in 15 min!"
            )

        # ATR trigger
        atr_data = fetch_atr(symbol)
        atr_val = atr_prev = None
        if atr_data.get("values"):
            vals = atr_data["values"]
            try:
                atr_prev = float(vals[-2].get("ATR") or vals[-2].get("atr"))
                atr_val  = float(vals[-1].get("ATR") or vals[-1].get("atr"))
            except:
                pass
        if atr_val and atr_prev:
            true_range = df["high"].iloc[-1] - df["low"].iloc[-1]
            if true_range >= atr_val * ATR_MULTIPLIER:
                dir_arrow = "📈" if atr_val > atr_prev else "📉"
                alerts.append(
                    f"{dir_arrow} Volatility {'up' if atr_val>atr_prev else 'down'} "
                    f"(ATR {dir_arrow} {((atr_val-atr_prev)/atr_prev)*100:+.2f}%)"
                )

        # Send alerts
        if alerts:
            ts = datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')
            send_telegram_alert(f"🕒 *{ts}*\n" + "\n".join(alerts))

    except Exception as e:
        send_telegram_alert(f"[ERROR] {symbol}: {e}")
