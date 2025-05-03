# ============================================
#   Crypto-Alert Bot v2
#   Crafted with ❤️ by Robin A
# ============================================

import os
import sys
import requests
from datetime import datetime

# ── Detect manual run via GitHub Actions ──
manual_run = os.environ.get('GITHUB_EVENT_NAME') == 'workflow_dispatch'

# 🧠 CONFIG
API_KEY = os.environ['TWELVE_API_KEY']
COINS = {
    "BTC/USD": {"name": "Bitcoin",   "threshold": 0.8},
    "SOL/USD": {"name": "Solana",    "threshold": 0.8},
    "LINK/USD": {"name": "Chainlink","threshold": 0.8}
}
INTERVAL   = "30min"
BB_PERIOD  = 20  # Bollinger Bands period
NBDEVUP    = 2   # upper band deviation
NBDEVDN    = 2   # lower band deviation

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

# ── DATA FETCH HELPERS ──
def fetch_time_series(symbol):
    return requests.get(
        "https://api.twelvedata.com/time_series",
        params={
            "symbol": symbol,
            "interval": INTERVAL,
            "outputsize": 2,
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
            "outputsize": 2,
            "apikey": API_KEY
        }
    ).json()

# ── TEST-RUN MODE ──
if manual_run:
    ts = datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')
    lines = [f"🧪 *Test Run* {ts}"]

    for symbol, info in COINS.items():
        name = info['name']
        # Fetch last 2 bars price
        ts_data = fetch_time_series(symbol)
        vals = ts_data.get('values', [])
        if len(vals) < 2:
            lines.append(f"*{name}* – ❌ no data")
            continue
        prev_close = float(vals[1]['close'])
        curr_close = float(vals[0]['close'])
        pct = (curr_close - prev_close) / prev_close * 100
        price_arrow = "🚀" if pct > 0 else "🚨"
        verb = "rocketed" if pct > 0 else "plunged"
        lines.append(f"{price_arrow} {name} just {verb} {pct:+.2f}% in 30 min!")

        # Fetch BBANDS for same two bars
        bb = fetch_bbands(symbol)
        bb_vals = bb.get('values', [])
        if len(bb_vals) >= 2:
            prev_bb = bb_vals[1]
            curr_bb = bb_vals[0]
            prev_upper = float(prev_bb.get('upperband', prev_bb.get('uband', 0)))
            prev_lower = float(prev_bb.get('lowerband', prev_bb.get('lband', 0)))
            curr_upper = float(curr_bb.get('upperband', curr_bb.get('uband', 0)))
            curr_lower = float(curr_bb.get('lowerband', curr_bb.get('lband', 0)))
            # Edge detection
            if prev_close <= prev_upper and curr_close > curr_upper:
                lines.append(f"📈 {name} broke above upper BB (Bullish upper band)")
            elif prev_close >= prev_lower and curr_close < curr_lower:
                lines.append(f"📉 {name} fell below lower BB (Bearish lower band)")
            else:
                lines.append(f"⚪ {name} within BB range")
        else:
            lines.append(f"⚪ {name} BB data unavailable")

    send_telegram_alert("\n".join(lines))
    sys.exit()

# ── NORMAL ALERT MODE (cron) ──
for symbol, info in COINS.items():
    try:
        name = info['name']
        # Fetch last 2 bars price
        ts_data = fetch_time_series(symbol)
        vals = ts_data.get('values', [])
        if len(vals) < 2:
            continue
        prev_close = float(vals[1]['close'])
        curr_close = float(vals[0]['close'])
        pct = (curr_close - prev_close) / prev_close * 100

        alerts = []
        # Price edge detection
        if abs(pct) >= info['threshold']:
            price_arrow = "🚀" if pct > 0 else "🚨"
            verb = "rocketed" if pct > 0 else "plunged"
            alerts.append(f"{price_arrow} {name} just {verb} {pct:+.2f}% in 30 min!")

        # Fetch BBANDS and edge detection
        bb = fetch_bbands(symbol)
        bb_vals = bb.get('values', [])
        if len(bb_vals) >= 2:
            prev_bb = bb_vals[1]
            curr_bb = bb_vals[0]
            prev_upper = float(prev_bb.get('upperband', prev_bb.get('uband', 0)))
            prev_lower = float(prev_bb.get('lowerband', prev_bb.get('lband', 0)))
            curr_upper = float(curr_bb.get('upperband', curr_bb.get('uband', 0)))
            curr_lower = float(curr_bb.get('lowerband', curr_bb.get('lband', 0)))
            if prev_close <= prev_upper and curr_close > curr_upper:
                alerts.append(f"📈 {name} broke above upper BB (Bullish upper band)")
            elif prev_close >= prev_lower and curr_close < curr_lower:
                alerts.append(f"📉 {name} fell below lower BB (Bearish lower band)")

        if alerts:
            ts = datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')
            send_telegram_alert(f"🕒 *{ts}*\n" + "\n".join(alerts))

    except Exception as e:
        send_telegram_alert(f"[ERROR] {symbol}: {e}")
