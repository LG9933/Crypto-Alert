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
COOLDOWN_FILE = "/tmp/alert_cooldowns.json"

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

# 🔁 COOLDOWN LOGIC
def load_cooldowns():
    if os.path.exists(COOLDOWN_FILE):
        with open(COOLDOWN_FILE, 'r') as f:
            return json.load(f)
    return {}

def save_cooldowns(cooldowns):
    with open(COOLDOWN_FILE, 'w') as f:
        json.dump(cooldowns, f)

cooldowns = load_cooldowns()
now = datetime.datetime.now()
timestamp_now = now.timestamp()

# 🔁 MAIN LOOP
change_24h_summary = {}
change_2h_summary = {}
trend_map = {}

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
        change_pct_2h = ((df["close"].iloc[-1] - df["close"].iloc[-3]) / df["close"].iloc[-3]) * 100 if len(df) >= 3 else 0.0
        change_pct_24h = ((df["close"].iloc[-1] - df["close"].iloc[-25]) / df["close"].iloc[-25]) * 100 if len(df) >= 25 else 0.0
        change_24h_summary[name] = change_pct_24h
        change_2h_summary[name] = change_pct_2h

        df["ma"] = df["close"].rolling(window=MA_PERIOD).mean()
        in_uptrend = df["close"].iloc[-1] > df["ma"].iloc[-1]
        trend = "↑ UP" if in_uptrend else "↓ DOWN"
        trend_emoji = "📈" if in_uptrend else "📉"
        trend_map[name] = f"{trend_emoji} {trend}"

        # RSI status emoji
        if last_rsi < 25:
            rsi_label = f"🔻 *RSI:* {last_rsi:.2f} → _Oversold_"
        elif last_rsi > 75:
            rsi_label = f"🔺 *RSI:* {last_rsi:.2f} → _Overbought_"
        else:
            rsi_label = f"⚪ *RSI:* {last_rsi:.2f} → _Neutral_"

        # Price change emojis
        ch1h_emoji = "📈" if change_pct_1h > 0 else "📉"
        ch24h_emoji = "📈" if change_pct_24h > 0 else "📉"

        # Advice logic (minder gevoelig)
        if change_pct_1h > 4:
            advice = "*STRONG BUY*\nSentiment: Price Jump"
        elif change_pct_1h < -4:
            advice = "*STRONG SELL*\nSentiment: Price Dump"
        elif last_rsi < 25 and in_uptrend:
            advice = "*BUY*\nSentiment: Oversold + Uptrend"
        elif last_rsi < 25 and not in_uptrend:
            advice = "*STRONG BUY*\nSentiment: Oversold + Downtrend"
        elif last_rsi > 75 and not in_uptrend:
            advice = "*STRONG SELL*\nSentiment: Overbought + Downtrend"
        elif last_rsi > 75 and in_uptrend:
            advice = "*SELL*\nSentiment: Overbought + Uptrend"
        else:
            advice = "*NEUTRAL*"

        # Cooldown check
        cooldown_key = f"{name}_{advice}"
        cooldown_ok = True
        if advice != "*NEUTRAL*":
            last_alert_time = cooldowns.get(cooldown_key, 0)
            time_since = timestamp_now - last_alert_time
            if time_since < 7200:  # 2 uur cooldown
                # uitzonderingen toestaan bij sterke extra beweging
                if (abs(change_pct_1h) > 6 or last_rsi < 20 or last_rsi > 80):
                    cooldown_ok = True
                else:
                    cooldown_ok = False

        # Bericht opstellen en versturen
        if advice != "*NEUTRAL*" and cooldown_ok:
            msg = (
                f"*{name}*\n"
                f"{rsi_label}\n"
                f"⏱ *1h Change:* {ch1h_emoji} {change_pct_1h:.2f}%\n"
                f"📆 *24h Change:* {ch24h_emoji} {change_pct_24h:.2f}%\n"
                f"{trend_emoji} *Trend:* {trend} (MA{MA_PERIOD})\n"
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

            cooldowns[cooldown_key] = timestamp_now

    except Exception as e:
        print(f"[ERROR] Exception bij {name}: {str(e)}")

# ⏱️ 2-uur Bitcoin update met kleur en trend
if now.hour % 2 == 0:
    try:
        if "Bitcoin" in change_2h_summary and "Bitcoin" in change_24h_summary:
            ch2h = change_2h_summary["Bitcoin"]
            ch24h = change_24h_summary["Bitcoin"]
            emoji_2h = "📈" if ch2h > 0 else "📉"
            emoji_24h = "📈" if ch24h > 0 else "📉"
            trend_str = trend_map.get("Bitcoin", "")
            msg = (
                f"📊 *Bitcoin Overview*\n"
                f"⏱ *2h Change:* {emoji_2h} {ch2h:+.2f}%\n"
                f"📆 *24h Change:* {emoji_24h} {ch24h:+.2f}%\n"
                f"{trend_str}"
            )
            send_telegram_alert(msg)
            extra = os.environ.get('EXTRA_CHAT_ID')
            if extra:
                send_telegram_alert(msg, chat_id=extra)
    except Exception as e:
        print(f"Fout bij verzenden BTC 2h report: {e}")

# 💾 Save cooldowns
save_cooldowns(cooldowns)
