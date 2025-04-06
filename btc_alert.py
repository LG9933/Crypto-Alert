import requests
import pandas as pd
import os
import matplotlib.pyplot as plt
import datetime
from pathlib import Path

# CONFIG
API_KEY = os.environ['TWELVE_API_KEY']
COINS = {
    "BTC/USD": "Bitcoin",
    "SOL/USD": "Solana",
    "LINK/USD": "Chainlink"
}
INTERVAL = "1h"
RSI_PERIOD = 14
MA_PERIOD = 50
COOLDOWN_DIR = Path(".cooldowns")
COOLDOWN_DIR.mkdir(exist_ok=True)
COOLDOWN_HOURS = 2

# TELEGRAM

def send_telegram_alert(message, chat_id=None):
    token = os.environ['BOT_TOKEN']
    default_chat_id = os.environ['CHAT_ID']
    final_chat_id = chat_id if chat_id else default_chat_id
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {"chat_id": final_chat_id, "text": message, "parse_mode": "Markdown"}
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

def cooldown_path(symbol):
    return COOLDOWN_DIR / f"{symbol.replace('/', '_')}.txt"

def is_on_cooldown(symbol):
    path = cooldown_path(symbol)
    if not path.exists():
        return False
    last_sent = datetime.datetime.fromisoformat(path.read_text())
    return (datetime.datetime.now() - last_sent).total_seconds() < COOLDOWN_HOURS * 3600

def set_cooldown(symbol):
    path = cooldown_path(symbol)
    path.write_text(datetime.datetime.now().isoformat())

any_trigger_sent = False
change_24h_summary = {}

for symbol, name in COINS.items():
    try:
        outputsize = max(RSI_PERIOD, MA_PERIOD, 25)
        url = f"https://api.twelvedata.com/time_series?symbol={symbol}&interval={INTERVAL}&outputsize={outputsize}&apikey={API_KEY}"
        r = requests.get(url)
        data = r.json()

        if "values" not in data:
            continue

        df = pd.DataFrame(data["values"])
        df["datetime"] = pd.to_datetime(df["datetime"])
        df["close"] = df["close"].astype(float)
        df = df[::-1].reset_index(drop=True)

        delta = df["close"].diff()
        gain = delta.where(delta > 0, 0.0)
        loss = -delta.where(delta < 0, 0.0)
        avg_gain = gain.rolling(window=RSI_PERIOD).mean()
        avg_loss = loss.rolling(window=RSI_PERIOD).mean()
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        last_rsi = rsi.iloc[-1]

        change_pct_1h = ((df["close"].iloc[-1] - df["close"].iloc[-2]) / df["close"].iloc[-2]) * 100 if len(df) >= 2 else 0.0
        change_pct_24h = ((df["close"].iloc[-1] - df["close"].iloc[-25]) / df["close"].iloc[-25]) * 100 if len(df) >= 25 else 0.0
        change_24h_summary[name] = change_pct_24h

        df["ma"] = df["close"].rolling(window=MA_PERIOD).mean()
        in_uptrend = df["close"].iloc[-1] > df["ma"].iloc[-1]
        trend = "UP" if in_uptrend else "DOWN"

        advice = "*NEUTRAL*"
        sentiment = ""
        show_alert = False

        if change_pct_1h < -3:
            advice = "*STRONG SELL*"
            sentiment = "Bearish Price Drop"
            show_alert = True
        elif change_pct_1h > 3:
            advice = "*STRONG BUY*"
            sentiment = "Bullish Price Pump"
            show_alert = True
        elif last_rsi < 25:
            advice = "*STRONG BUY*"
            sentiment = "Oversold + Downtrend"
            show_alert = True
        elif last_rsi > 75:
            advice = "*STRONG SELL*"
            sentiment = "Overbought + Uptrend"
            show_alert = True

        # Emoji's
        rsi_icon = "🔻" if last_rsi < 30 else "🔺" if last_rsi > 70 else "" 
        trend_icon = "🔽" if not in_uptrend else "🔼"
        change_1h_icon = "📈" if change_pct_1h > 0 else "📉"
        change_24h_icon = "📈" if change_pct_24h > 0 else "📉"

        msg = (
            f"{rsi_icon} *{name}*
"
            f"*RSI:* {last_rsi:.2f} → _{'Oversold' if last_rsi < 30 else 'Overbought' if last_rsi > 70 else 'Neutral'}_
"
            f"🕒 *1h Change:* {change_1h_icon} {change_pct_1h:+.2f}%
"
            f"📅 *24h Change:* {change_24h_icon} {change_pct_24h:+.2f}%
"
            f"*Trend:* {trend_icon} {trend} (MA{MA_PERIOD})
"
            f"*{advice}*
"
            f"Sentiment: {sentiment}"
        )

        if show_alert and not is_on_cooldown(symbol):
            any_trigger_sent = True

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

            send_telegram_alert(msg)
            send_telegram_chart(image_path)

            extra = os.environ.get('EXTRA_CHAT_ID')
            if extra:
                send_telegram_alert(msg, chat_id=extra)
                send_telegram_chart(image_path, chat_id=extra)

            set_cooldown(symbol)

    except Exception as e:
        msg = f"[ERROR] Exception bij {name}: {str(e)}"
        send_telegram_alert(msg)
        extra = os.environ.get('EXTRA_CHAT_ID')
        if extra:
            send_telegram_alert(msg, chat_id=extra)

# Periodiek BTC-only 24h & 2h overzicht (2-uur interval)
now = datetime.datetime.now()
if now.hour % 2 == 0:
    try:
        symbol = "BTC/USD"
        name = "Bitcoin"
        if name in change_24h_summary:
            pct_24h = change_24h_summary[name]
            url = f"https://api.twelvedata.com/time_series?symbol={symbol}&interval=1h&outputsize=3&apikey={API_KEY}"
            r = requests.get(url)
            df = pd.DataFrame(r.json()["values"])
            df["close"] = df["close"].astype(float)
            pct_2h = ((df["close"].iloc[0] - df["close"].iloc[2]) / df["close"].iloc[2]) * 100

            icon_2h = "📈" if pct_2h > 0 else "📉"
            icon_24h = "📈" if pct_24h > 0 else "📉"
            trend_icon = "🔼" if pct_24h > 0 else "🔽"

            overview = (
                f"📊 *Bitcoin Overview*
"
                f"🕑 2h Change: {icon_2h} {pct_2h:+.2f}%
"
                f"📆 24h Change: {icon_24h} {pct_24h:+.2f}%
"
                f"{trend_icon} {'UP' if pct_24h > 0 else 'DOWN'}"
            )
            send_telegram_alert(overview)
            extra = os.environ.get('EXTRA_CHAT_ID')
            if extra:
                send_telegram_alert(overview, chat_id=extra)
    except Exception as e:
        print(f"Fout bij verzenden BTC overview: {e}")
