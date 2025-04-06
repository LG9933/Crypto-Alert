import requests
import pandas as pd
import os
import matplotlib.pyplot as plt
import datetime
import json

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
COOLDOWN_DIR = ".cooldowns"
COOLDOWN_MINUTES = 60

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

def in_cooldown(symbol):
    if not os.path.exists(COOLDOWN_DIR):
        os.makedirs(COOLDOWN_DIR)
    path = os.path.join(COOLDOWN_DIR, f"{symbol.replace('/', '_')}.json")
    if not os.path.exists(path):
        return False
    with open(path, 'r') as f:
        last_alert = json.load(f).get("timestamp")
        if not last_alert:
            return False
        last_time = datetime.datetime.fromisoformat(last_alert)
        return (datetime.datetime.now() - last_time).total_seconds() < COOLDOWN_MINUTES * 60

def update_cooldown(symbol):
    path = os.path.join(COOLDOWN_DIR, f"{symbol.replace('/', '_')}.json")
    with open(path, 'w') as f:
        json.dump({"timestamp": datetime.datetime.now().isoformat()}, f)

# MAIN
for symbol, name in COINS.items():
    try:
        if in_cooldown(symbol):
            continue

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

        change_1h = ((df["close"].iloc[-1] - df["close"].iloc[-2]) / df["close"].iloc[-2]) * 100 if len(df) >= 2 else 0.0
        change_2h = ((df["close"].iloc[-1] - df["close"].iloc[-3]) / df["close"].iloc[-3]) * 100 if len(df) >= 3 else 0.0
        change_24h = ((df["close"].iloc[-1] - df["close"].iloc[-25]) / df["close"].iloc[-25]) * 100 if len(df) >= 25 else 0.0

        df["ma"] = df["close"].rolling(window=MA_PERIOD).mean()
        in_uptrend = df["close"].iloc[-1] > df["ma"].iloc[-1]
        trend = "🟢 UP" if in_uptrend else "🔴 DOWN"

        if change_1h > 3:
            advice = "*STRONG BUY*\nSentiment: Pump + Momentum"
        elif change_1h < -3:
            advice = "*STRONG SELL*\nSentiment: Dump + Momentum"
        elif last_rsi < 30 and not in_uptrend:
            advice = "*STRONG BUY*\nSentiment: Oversold + Downtrend"
        elif last_rsi > 70 and not in_uptrend:
            advice = "*STRONG SELL*\nSentiment: Overbought + Downtrend"
        else:
            continue  # skip alerts that are not strong

        msg = (
            f"📊 *{name}*\n"
            f"🔻 *RSI:* {last_rsi:.2f} → _{'Oversold' if last_rsi < 30 else 'Overbought'}_\n"
            f"🕒 *1h Change:* {'📈' if change_1h > 0 else '📉'} {change_1h:.2f}%\n"
            f"📅 *24h Change:* {'📈' if change_24h > 0 else '📉'} {change_24h:.2f}%\n"
            f"📉 *Trend:* {trend} (MA{MA_PERIOD})\n"
            f"{advice}"
        )

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

        update_cooldown(symbol)

    except Exception as e:
        msg = f"[ERROR] Exception bij {name}: {str(e)}"
        send_telegram_alert(msg)
        extra = os.environ.get('EXTRA_CHAT_ID')
        if extra:
            send_telegram_alert(msg, chat_id=extra)
