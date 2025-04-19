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
API_KEY        = os.environ['TWELVE_API_KEY']
COINS = {
    "BTC/USD": {"name": "Bitcoin",   "threshold": 1.5},
    "SOL/USD": {"name": "Solana",    "threshold": 2.5},
    "LINK/USD":{"name": "Chainlink","threshold": 2.5}
}
INTERVAL       = "30min"
OUTPUTSIZE     = 6    # 5 + 1 for chart
ATR_PERIOD     = 14   # candles for ATR
ATR_MULTIPLIER = 1.2  # TR ≥ 1.2×ATR → volatility spike

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

def send_telegram_chart(image_path, chat_id=None):
    token = os.environ['BOT_TOKEN']
    cid   = chat_id or os.environ['CHAT_ID']
    url   = f"https://api.telegram.org/bot{token}/sendPhoto"
    with open(image_path, 'rb') as photo:
        requests.post(url, files={"photo": photo}, data={"chat_id": cid})

# ensure /tmp exists
Path("/tmp").mkdir(parents=True, exist_ok=True)

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
            "outputsize": ATR_PERIOD+1,  # get last + previous
            "apikey": API_KEY
        }
    ).json()

# ── TEST‑RUN MODE ──
if manual_run:
    ts = datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')
    lines = [f"🧪 *Test Run* {ts}"]
    for symbol, info in COINS.items():
        # 1) Prices
        ts_data = fetch_time_series(symbol)
        if "values" not in ts_data:
            lines.append(f"*{info['name']}* – ❌ no data")
            continue

        df = pd.DataFrame(ts_data["values"])
        df = df.astype({"close": float, "high": float, "low": float})
        df = df.iloc[::-1].reset_index(drop=True)
        curr, prev = df["close"].iloc[-1], df["close"].iloc[-2]
        pct = (curr - prev) / prev * 100
        arrow = "📈" if pct>0 else "📉"
        word  = "Pump" if pct>0 else "Dump"

        # 2) ATR + direction
        atr_data = fetch_atr(symbol)
        atr_val = atr_prev = None
        if atr_data.get("values"):
            vals = atr_data["values"]
            # parse last and prev ATR
            for v in (vals[-2], vals[-1]):
                # entries may come as { "ATR": "..."}
                setattr(locals(), "atr_prev" if v is vals[-2] else "atr_val",
                        float(v.get("ATR") or v.get("atr") or 0))
        if atr_val and atr_prev:
            delta_atr = atr_val - atr_prev
            dir_arrow = "🔼" if delta_atr>0 else "🔽"
            delta_pct = delta_atr/atr_prev*100
            atr_line = f"⚡ ATR{dir_arrow} {atr_val:.2f} ({delta_pct:+.2f}%)"
        else:
            atr_line = "⚡ ATR unavailable"

        lines.append(f"{arrow} *{info['name']} {word}* {pct:+.2f}%\n{atr_line}")

    send_telegram_alert("\n\n".join(lines))
    sys.exit()

# ── NORMAL ALERT MODE (cron) ──
for symbol, info in COINS.items():
    try:
        # price data
        ts_data = fetch_time_series(symbol)
        if "values" not in ts_data:
            continue

        df = pd.DataFrame(ts_data["values"])
        df = df.astype({"close": float, "high": float, "low": float})
        df["datetime"] = pd.to_datetime(df["datetime"])
        df = df.iloc[::-1].reset_index(drop=True)
        curr, prev = df["close"].iloc[-1], df["close"].iloc[-2]
        pct = (curr - prev) / prev * 100

        alerts = []
        # 1) Price-trigger
        if abs(pct) >= info["threshold"]:
            arrow = "📈" if pct>0 else "📉"
            word  = "Pump" if pct>0 else "Dump"
            alerts.append(f"{arrow} *{info['name']} {word}!* {pct:+.2f}%")

        # 2) ATR-trigger
        atr_data = fetch_atr(symbol)
        atr_val = atr_prev = None
        if atr_data.get("values"):
            vals = atr_data["values"]
            for v in (vals[-2], vals[-1]):
                setattr(locals(),
                        "atr_prev" if v is vals[-2] else "atr_val",
                        float(v.get("ATR") or v.get("atr") or 0))
        if atr_val and atr_prev:
            true_range = df["high"].iloc[-1] - df["low"].iloc[-1]
            if true_range >= atr_val * ATR_MULTIPLIER:
                dir_arrow = "🔼" if atr_val>atr_prev else "🔽"
                alerts.append(
                    f"⚡ *{info['name']} Volatility{dir_arrow}!* "
                    f"TR {true_range:.2f} ≥ {ATR_MULTIPLIER}×ATR({atr_val:.2f})"
                )

        # 3) Dispatch
        if alerts:
            ts = datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')
            send_telegram_alert(f"🕒 *{ts}*\n" + "\n".join(alerts))
            # mini chart
            chart = df.iloc[-OUTPUTSIZE:].copy()
            path  = Path(f"/tmp/chart_{symbol.replace('/','_')}.png")
            plt.figure(figsize=(4,2))
            plt.plot(chart["datetime"], chart["close"], linewidth=1.5)
            plt.title(f"{info['name']} Price")
            plt.tight_layout()
            plt.savefig(path)
            plt.close()
            send_telegram_chart(str(path))

    except Exception as e:
        send_telegram_alert(f"[ERROR] {symbol}: {e}")
