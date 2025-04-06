import requests
import pandas as pd
import os
import matplotlib.pyplot as plt
import datetime
import json

# 🧠 CONFIG
API_KEY = os.environ['TWELVE_API_KEY']
COINS = {
    "BTC/USD": "Bitcoin",
    "SOL/USD": "Solana",
    "LINK/USD": "Chainlink"
}
INTERVAL = "1h"
RSI_PERIOD = 14
MA_PERIOD = 50
COOLDOWN_FILE = ".cooldowns/alert_cooldowns.json"
COOLDOWN_MINUTES = 120  # 2 uur

# ✅ TELEGRAM
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

# ⏱️ Cooldown opslag en check
def load_cooldowns():
    if os.path.exists(COOLDOWN_FILE):
        with open(COOLDOWN_FILE, 'r') as f:
            return json.load(f)
    return {}

def save_cooldowns(cooldowns):
    with open(COOLDOWN_FILE, 'w') as f:
        json.dump(cooldowns, f)

def is_on_cooldown(coin, signal_type, cooldowns):
    key = f"{coin}_{signal_type}"
    if key in cooldowns:
        last_trigger = datetime.datetime.fromisoformat(cooldowns[key])
        return (datetime.datetime.now() - last_trigger).total_seconds() < COOLDOWN_MINUTES * 60
    return False

def update_cooldown(coin, signal_type, cooldowns):
    key = f"{coin}_{signal_type}"
    cooldowns[key] = datetime.datetime.now().isoformat()

# 🔁 MAIN LOOP
any_trigger_sent = False
change_24h_summary = {}
cooldowns = load_cooldowns()

for symbol, name in COINS.items():
    try:
        outputsize = max(RSI_PERIOD, MA_PERIOD, 25)
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

        if last_rsi < 30 and not is_on_cooldown(name, "strong_buy", cooldowns):
            advice = "*STRONG BUY*\nSentiment: Oversold + Downtrend"
            update_cooldown(name, "strong_buy", cooldowns)
        elif last_rsi > 70 and not is_on_cooldown(name, "strong_sell", cooldowns):
            advice = "*STRONG SELL*\nSentiment: Overbought + Uptrend"
            update_cooldown(name, "strong_sell", cooldowns)
        else:
            advice = "*NEUTRAL*"

        msg = (
            f"*{name}*\n"
            f"*RSI:* {last_rsi:.2f}\n"
            f"*Change (1h):* {change_pct_1h:.2f}%\n"
            f"*Change (24h):* {change_pct_24h:.2f}%\n"
            f"*Trend:* {trend} (MA{MA_PERIOD})\n"
            f"*Advice:* {advice}"
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

        if "NEUTRAL" not in advice:
            any_trigger_sent = True
            send_telegram_alert(msg)
            send_telegram_chart(image_path)
            extra = os.environ.get('EXTRA_CHAT_ID')
            if extra:
                send_telegram_alert(msg, chat_id=extra)
                send_telegram_chart(image_path, chat_id=extra)

    except Exception as e:
        msg = f"[ERROR] Exception bij {name}: {str(e)}"
        send_telegram_alert(msg)
        extra = os.environ.get('EXTRA_CHAT_ID')
        if extra:
            send_telegram_alert(msg, chat_id=extra)

save_cooldowns(cooldowns)

# ⏱️ 24h Change Report for BTC Only (Every 2 Hours)
now = datetime.datetime.now()
if now.hour % 2 == 0:
    try:
        if "Bitcoin" in change_24h_summary:
            pct = change_24h_summary["Bitcoin"]
            color = "🟢" if pct >= 0 else "🔴"
            message = f"24h BTC Change: {pct:+.2f}% {color}"
            send_telegram_alert(message)
            extra = os.environ.get('EXTRA_CHAT_ID')
            if extra:
                send_telegram_alert(message, chat_id=extra)
    except Exception as e:
        print(f"Fout bij verzenden BTC 24h report: {e}")
