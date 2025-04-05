# btc_alert.py

import requests
import pandas as pd
import os
import matplotlib.pyplot as plt
import datetime

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

# MAIN LOOP
for symbol, name in COINS.items():
    try:
        outputsize = max(RSI_PERIOD, MA_PERIOD, 25)
        url = f"https://api.twelvedata.com/time_series?symbol={symbol}&interval={INTERVAL}&outputsize={outputsize}&apikey={API_KEY}"
        r = requests.get(url)
        data = r.json()

        if "values" not in data:
            msg = f"[ERROR] No data for {name}: {data.get('message', 'Unknown error')}"
            send_telegram_alert(msg)
            extra = os.environ.get('EXTRA_CHAT_ID')
            if extra:
                send_telegram_alert(msg, chat_id=extra)
            continue

        df = pd.DataFrame(data["values"])
        df["datetime"] = pd.to_datetime(df["datetime"])
        df["close"] = df["close"].astype(float)
        df = df[::-1].reset_index(drop=True)

        # RSI calculation
        delta = df["close"].diff()
        gain = delta.where(delta > 0, 0.0)
        loss = -delta.where(delta < 0, 0.0)
        avg_gain = gain.rolling(window=RSI_PERIOD).mean()
        avg_loss = loss.rolling(window=RSI_PERIOD).mean()
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        last_rsi = rsi.iloc[-1]

        # 2h & 24h % change
        change_pct_2h = ((df["close"].iloc[-1] - df["close"].iloc[-2]) / df["close"].iloc[-2]) * 100 if len(df) >= 2 else 0.0
        change_pct_24h = ((df["close"].iloc[-1] - df["close"].iloc[-25]) / df["close"].iloc[-25]) * 100 if len(df) >= 25 else 0.0

        # MA50 and trend
        df["ma"] = df["close"].rolling(window=MA_PERIOD).mean()
        in_uptrend = df["close"].iloc[-1] > df["ma"].iloc[-1]
        trend = "↑ UP" if in_uptrend else "↓ DOWN"

        # MACD with validation
        macd_url = f"https://api.twelvedata.com/macd?symbol={symbol}&interval=1h&apikey={API_KEY}"
        macd_resp = requests.get(macd_url).json()
        if "values" not in macd_resp or len(macd_resp["values"]) == 0:
            raise Exception(f"No MACD values: {macd_resp}")
        macd_data = macd_resp['values'][0]
        macd_val = float(macd_data['macd'])
        signal_val = float(macd_data['macdsignal'])

        # Bollinger Bands
        bb_url = f"https://api.twelvedata.com/bbands?symbol={symbol}&interval=1h&time_period=20&apikey={API_KEY}"
        bb_resp = requests.get(bb_url).json()
        if "values" not in bb_resp:
            raise Exception(f"BBANDS API error: {bb_resp}")
        lower_band = float(bb_resp['values'][0]['lower_band'])
        upper_band = float(bb_resp['values'][0]['upper_band'])
        current_price = df["close"].iloc[-1]

        # Indicator triggers
        rsi_trigger = last_rsi < 30 or last_rsi > 70
        macd_trigger = macd_val > signal_val or macd_val < signal_val
        bb_trigger = current_price < lower_band or current_price > upper_band

        if not (rsi_trigger or macd_trigger or bb_trigger):
            continue

        # Labels
        rsi_sentiment = "Bullish 🟢" if last_rsi < 30 else "Bearish 🔴" if last_rsi > 70 else "Neutral ⚪"
        macd_sentiment = "Bullish 🟢" if macd_val > signal_val else "Bearish 🔴"
        bb_sentiment = "Bullish 🟢" if current_price < lower_band else "Bearish 🔴" if current_price > upper_band else "Neutral ⚪"

        rsi_label = f"{last_rsi:.2f} → _{rsi_sentiment}_"
        macd_label = f"{macd_val:.4f} vs {signal_val:.4f} → _{macd_sentiment}_"
        bb_label = f"{current_price:.2f} {'< lower' if current_price < lower_band else '> upper' if current_price > upper_band else 'inside bands'} → _{bb_sentiment}_"

        advice = "*STRONG BUY ✅*" if (last_rsi < 30 or macd_val > signal_val or current_price < lower_band) else \
                 "*STRONG SELL ❌*" if (last_rsi > 70 or macd_val < signal_val or current_price > upper_band) else "*WAIT ⚪*"

        # Message
        msg = (
            f"*{name}*\n"
            f"*RSI:* {rsi_label}\n"
            f"*MACD:* {macd_label}\n"
            f"*BBANDS:* {bb_label}\n"
            f"*Advice:* {advice}\n"
            f"*Change (2h):* {change_pct_2h:.2f}%\n"
            f"*Change (24h):* {change_pct_24h:.2f}%\n"
            f"*Trend:* {trend} (MA{MA_PERIOD})"
        )

        # Chart
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(8, 6), sharex=True, gridspec_kw={'height_ratios': [2, 1]})
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

    except Exception as e:
        msg = f"[ERROR] Exception for {name}: {str(e)}"
        send_telegram_alert(msg)
        extra = os.environ.get('EXTRA_CHAT_ID')
        if extra:
            send_telegram_alert(msg, chat_id=extra)
