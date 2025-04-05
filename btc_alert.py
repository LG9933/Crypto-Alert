import requests
import pandas as pd
import os
import matplotlib.pyplot as plt
import datetime

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

# 🔁 MAIN LOOP
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

        # RSI berekening
        delta = df["close"].diff()
        gain = delta.where(delta > 0, 0.0)
        loss = -delta.where(delta < 0, 0.0)
        avg_gain = gain.rolling(window=RSI_PERIOD).mean()
        avg_loss = loss.rolling(window=RSI_PERIOD).mean()
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        last_rsi = rsi.iloc[-1]

        # % change 2h en 24h
        change_pct_2h = ((df["close"].iloc[-1] - df["close"].iloc[-2]) / df["close"].iloc[-2]) * 100 if len(df) >= 2 else 0.0
        change_pct_24h = ((df["close"].iloc[-1] - df["close"].iloc[-25]) / df["close"].iloc[-25]) * 100 if len(df) >= 25 else 0.0

        # MA50 berekenen
        df["ma"] = df["close"].rolling(window=MA_PERIOD).mean()
        in_uptrend = df["close"].iloc[-1] > df["ma"].iloc[-1]
        trend = "↑ UP" if in_uptrend else "↓ DOWN"

        # Advies op basis van RSI en MA
        if last_rsi < 30 and in_uptrend:
            advice = "*BUY 🟢*"
        elif last_rsi < 30 and not in_uptrend:
            advice = "*STRONG BUY ✅*"
        elif last_rsi > 70 and not in_uptrend:
            advice = "*SELL 🔴*"
        elif last_rsi > 70 and in_uptrend:
            advice = "*STRONG SELL ❌*"
        else:
            advice = "*WAIT ⚪*"  # Voor testmelding gebruiken

        # Bericht opstellen
        msg = (
            f"*{name}*\n"
            f"*RSI:* {last_rsi:.2f}\n"
            f"*Change (2h):* {change_pct_2h:.2f}%\n"
            f"*Change (24h):* {change_pct_24h:.2f}%\n"
            f"*Trend:* {trend} (MA{MA_PERIOD})\n"
            f"*Advice:* {advice}"
        )

        # Grafiek maken
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

        # Testalert altijd versturen voor testdoeleinden
        if name == "Chainlink":
            test_msg = f"🔍 *Test Alert ({name})*
\n{msg}"
            send_telegram_alert(test_msg)
            send_telegram_chart(image_path)
            extra = os.environ.get('EXTRA_CHAT_ID')
            if extra:
                send_telegram_alert(test_msg, chat_id=extra)
                send_telegram_chart(image_path, chat_id=extra)
        else:
            # Verstuur alerts alleen bij actievere adviezen
            if "WAIT" not in advice:
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
