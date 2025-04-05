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
    try:
        response = requests.post(url, data=payload, timeout=10) # Added timeout
        response.raise_for_status() # Raise an exception for bad status codes
    except requests.exceptions.RequestException as e:
        print(f"Error sending Telegram message: {e}")


def send_telegram_chart(image_path, chat_id=None):
    token = os.environ['BOT_TOKEN']
    default_chat_id = os.environ['CHAT_ID']
    final_chat_id = chat_id if chat_id else default_chat_id
    url = f"https://api.telegram.org/bot{token}/sendPhoto"
    try:
        with open(image_path, 'rb') as photo:
            files = {"photo": photo}
            data = {"chat_id": final_chat_id}
            response = requests.post(url, files=files, data=data, timeout=20) # Added timeout
            response.raise_for_status() # Raise an exception for bad status codes
    except FileNotFoundError:
        print(f"Error sending Telegram chart: File not found at {image_path}")
    except requests.exceptions.RequestException as e:
        print(f"Error sending Telegram chart: {e}")
    except Exception as e:
        print(f"An unexpected error occurred in send_telegram_chart: {e}")


# MAIN LOOP
for symbol, name in COINS.items():
    try:
        outputsize = max(RSI_PERIOD, MA_PERIOD, 26) # Increased slightly for 24h change safety
        url = f"https://api.twelvedata.com/time_series?symbol={symbol}&interval={INTERVAL}&outputsize={outputsize}&apikey={API_KEY}"
        r = requests.get(url, timeout=15) # Added timeout
        r.raise_for_status() # Check for HTTP errors
        data = r.json()

        if data.get("status") == "error" or "values" not in data:
            error_message = data.get('message', 'Unknown API error')
            msg = f"[API ERROR] No valid data for {name}: {error_message}"
            print(msg) # Print error locally as well
            send_telegram_alert(msg)
            extra = os.environ.get('EXTRA_CHAT_ID')
            if extra:
                send_telegram_alert(msg, chat_id=extra)
            continue

        if not data["values"]:
            msg = f"[WARNING] Empty 'values' list received for {name}."
            print(msg)
            # Optionally send a warning, or just continue
            # send_telegram_alert(msg)
            continue

        df = pd.DataFrame(data["values"])
        df["datetime"] = pd.to_datetime(df["datetime"])
        df["close"] = df["close"].astype(float)
        df = df[::-1].reset_index(drop=True) # Reverse to chronological order

        # Ensure enough data points for calculations
        if len(df) < outputsize:
             msg = f"[WARNING] Not enough data points for {name} (Got {len(df)}, need {outputsize}). Skipping calculations."
             print(msg)
             # Optionally send warning
             continue

        # RSI calculation
        delta = df["close"].diff()
        gain = delta.clip(lower=0) # More efficient way for gain
        loss = -delta.clip(upper=0) # More efficient way for loss

        # Use Exponential Moving Average (EMA) for RSI calculation (more standard)
        avg_gain = gain.ewm(com=RSI_PERIOD - 1, min_periods=RSI_PERIOD).mean()
        avg_loss = loss.ewm(com=RSI_PERIOD - 1, min_periods=RSI_PERIOD).mean()

        # Handle division by zero for avg_loss
        rs = avg_gain / avg_loss.replace(0, 1e-10) # Avoid division by zero

        rsi = 100 - (100 / (1 + rs))
        if rsi.empty or pd.isna(rsi.iloc[-1]):
            msg = f"[WARNING] Could not calculate RSI for {name}. Skipping."
            print(msg)
            continue # Skip if RSI calculation failed
        last_rsi = rsi.iloc[-1]

        # 2h & 24h % change (ensure enough data)
        change_pct_2h = ((df["close"].iloc[-1] - df["close"].iloc[-2]) / df["close"].iloc[-2]) * 100 if len(df) >= 2 else 0.0
        change_pct_24h = ((df["close"].iloc[-1] - df["close"].iloc[-25]) / df["close"].iloc[-25]) * 100 if len(df) >= 25 else 0.0

        # MA50 and trend
        df["ma"] = df["close"].rolling(window=MA_PERIOD).mean()
        if df["ma"].isna().all() or pd.isna(df["ma"].iloc[-1]):
             msg = f"[WARNING] Could not calculate MA{MA_PERIOD} for {name}. Skipping."
             print(msg)
             continue # Skip if MA calculation failed
        in_uptrend = df["close"].iloc[-1] > df["ma"].iloc[-1]
        trend = "↑ UP" if in_uptrend else "↓ DOWN"

        # --- MACD Section with Fix ---
        macd_url = f"https://api.twelvedata.com/macd?symbol={symbol}&interval={INTERVAL}&outputsize=1&apikey={API_KEY}" # Get only latest MACD
        try:
            macd_resp_req = requests.get(macd_url, timeout=15) # Added timeout
            macd_resp_req.raise_for_status() # Check for HTTP errors
            macd_resp = macd_resp_req.json()

            if macd_resp.get("status") == "error" or "values" not in macd_resp or not macd_resp["values"]:
                 raise ValueError(f"Invalid or empty MACD response: {macd_resp.get('message', macd_resp)}")

            macd_data = macd_resp['values'][0] # Get the latest MACD data point

            # Use .get() to safely access keys and check for None
            macd_val_str = macd_data.get('macd')
            # *** IMPORTANT: Double-check if the API uses 'macdsignal' or 'macd_signal' ***
            # Based on your error, it seems 'macdsignal' was expected. Using that here.
            signal_val_str = macd_data.get('macdsignal')

            # Check if the values were found
            if macd_val_str is None or signal_val_str is None:
                missing_keys = []
                if macd_val_str is None: missing_keys.append("'macd'")
                if signal_val_str is None: missing_keys.append("'macdsignal' (or maybe 'macd_signal'?)")
                raise KeyError(f"Missing keys {', '.join(missing_keys)} in MACD data: {macd_data}")

            # Try converting to float
            macd_val = float(macd_val_str)
            signal_val = float(signal_val_str)

        except (requests.exceptions.RequestException, ValueError, KeyError, TypeError, IndexError) as e:
             # Catch API errors, JSON errors, missing keys, conversion errors, or empty 'values' list
             msg = f"[ERROR] Failed to get/process MACD for {name}: {str(e)}"
             print(msg)
             send_telegram_alert(msg)
             # Optionally add chat_id=extra here too
             continue # Skip this coin if MACD fails

        # --- End of MACD Section ---

        # Bollinger Bands
        bb_url = f"https://api.twelvedata.com/bbands?symbol={symbol}&interval={INTERVAL}&time_period=20&outputsize=1&apikey={API_KEY}" # Get only latest BBands
        try:
            bb_resp_req = requests.get(bb_url, timeout=15) # Added timeout
            bb_resp_req.raise_for_status() # Check for HTTP errors
            bb_resp = bb_resp_req.json()

            if bb_resp.get("status") == "error" or "values" not in bb_resp or not bb_resp["values"]:
                 raise ValueError(f"Invalid or empty BBANDS response: {bb_resp.get('message', bb_resp)}")

            bb_data = bb_resp['values'][0]
            lower_band = float(bb_data['lower_band'])
            upper_band = float(bb_data['upper_band'])
            current_price = df["close"].iloc[-1] # Use the latest close price from the main dataframe

        except (requests.exceptions.RequestException, ValueError, KeyError, TypeError, IndexError) as e:
            msg = f"[ERROR] Failed to get/process Bollinger Bands for {name}: {str(e)}"
            print(msg)
            send_telegram_alert(msg)
            # Optionally add chat_id=extra here too
            continue # Skip this coin if BBands fail


        # Indicator triggers
        rsi_trigger = last_rsi < 30 or last_rsi > 70
        macd_trigger = (macd_val > signal_val) != (macd_val < signal_val) # True if they are not equal
        bb_trigger = current_price < lower_band or current_price > upper_band

        # Only send alert if at least one indicator is triggered
        if not (rsi_trigger or macd_trigger or bb_trigger):
            print(f"No trigger for {name}. RSI:{last_rsi:.2f}, MACD>Signal:{macd_val > signal_val}, Price:{current_price:.2f}, BB:{lower_band:.2f}-{upper_band:.2f}")
            continue

        # Labels & Sentiment
        rsi_sentiment = "Oversold🟢" if last_rsi < 30 else "Overbought🔴" if last_rsi > 70 else "Neutral⚪"
        macd_sentiment = "Bullish🟢" if macd_val > signal_val else "Bearish🔴" if macd_val < signal_val else "Neutral⚪" # Added Neutral if equal
        bb_sentiment = "BelowLower🟢" if current_price < lower_band else "AboveUpper🔴" if current_price > upper_band else "InsideBands⚪"

        rsi_label = f"{last_rsi:.2f} → _{rsi_sentiment}_"
        macd_label = f"{macd_val:.4f} vs {signal_val:.4f} → _{macd_sentiment}_"
        bb_label = f"{current_price:.2f} ({bb_sentiment})" # Simpler BB label

        # Simple Advice Logic (can be refined)
        buy_signals = (last_rsi < 30) + (macd_val > signal_val) + (current_price < lower_band)
        sell_signals = (last_rsi > 70) + (macd_val < signal_val) + (current_price > upper_band)

        if buy_signals > sell_signals and buy_signals > 0:
            advice = "*Consider BUY ✅*"
        elif sell_signals > buy_signals and sell_signals > 0:
            advice = "*Consider SELL ❌*"
        else: # Equal signals or no strong signals
             advice = "*Neutral / WAIT ⚪*"


        # Message
        msg = (
            f"*{name} Alert ({INTERVAL})*\n\n"
            f"*Price:* ${current_price:.2f}\n"
            f"*Trend (MA{MA_PERIOD}):* {trend}\n\n"
            f"*RSI ({RSI_PERIOD}):* {rsi_label}\n"
            f"*MACD:* {macd_label}\n"
            f"*BBANDS (20):* {bb_label}\n\n"
            f"*Advice:* {advice}\n\n"
            f"*Change (2h):* {change_pct_2h:.2f}%\n"
            f"*Change (24h):* {change_pct_24h:.2f}%"
        )

        # Chart
        try:
            fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 6), sharex=True, gridspec_kw={'height_ratios': [3, 1]}) # Adjusted size/ratio

            # Price chart with BBands
            ax1.plot(df["datetime"].iloc[-outputsize:], df["close"].iloc[-outputsize:], label="Close", linewidth=1.5, color='blue')
            ax1.plot(df["datetime"].iloc[-outputsize:], df["ma"].iloc[-outputsize:], label=f"MA{MA_PERIOD}", linestyle="--", color='orange', alpha=0.7)

            # If BBands data is available and matches the time series length (it won't directly, need to fetch more points or plot separately)
            # For simplicity, just plotting latest price vs bands in text. Plotting full bands requires fetching BBands time series.
            # ax1.plot(bb_datetime, bb_upper, label='Upper Band', linestyle=':', color='gray', alpha=0.5)
            # ax1.plot(bb_datetime, bb_lower, label='Lower Band', linestyle=':', color='gray', alpha=0.5)
            # ax1.fill_between(bb_datetime, bb_lower, bb_upper, alpha=0.1, color='gray')

            ax1.set_title(f"{name} Price | MA{MA_PERIOD} | Trend: {trend}")
            ax1.legend()
            ax1.grid(True, linestyle='--', alpha=0.5)

            # RSI chart
            ax2.plot(df["datetime"].iloc[-outputsize:], rsi.iloc[-outputsize:], label=f"RSI({RSI_PERIOD})", color="purple")
            ax2.axhline(70, color="red", linestyle="--", linewidth=0.8, label='Overbought (70)')
            ax2.axhline(30, color="green", linestyle="--", linewidth=0.8, label='Oversold (30)')
            ax2.set_title("Relative Strength Index (RSI)")
            ax2.set_ylim(0, 100)
            ax2.legend()
            ax2.grid(True, linestyle='--', alpha=0.5)

            plt.xticks(rotation=45) # Rotate x-axis labels
            plt.tight_layout()
            # Ensure /tmp directory exists or use a different path
            chart_dir = "/tmp"
            if not os.path.exists(chart_dir):
                 os.makedirs(chart_dir) # Create tmp if it doesn't exist
            image_path = os.path.join(chart_dir, f"chart_{symbol.replace('/', '_')}_{datetime.datetime.now().strftime('%Y%m%d%H%M')}.png") # Unique filename
            plt.savefig(image_path)
            plt.close(fig) # Close the figure to free memory

            # Send Alert and Chart
            print(f"Sending alert for {name}...")
            send_telegram_alert(msg)
            send_telegram_chart(image_path)

            extra = os.environ.get('EXTRA_CHAT_ID')
            if extra:
                print(f"Sending alert for {name} to extra chat ID...")
                send_telegram_alert(msg, chat_id=extra)
                send_telegram_chart(image_path, chat_id=extra)

            # Optional: Clean up the generated chart image
            # try:
            #    os.remove(image_path)
            # except OSError as e:
            #    print(f"Error removing chart file {image_path}: {e}")

        except Exception as plot_err:
            msg = f"[ERROR] Failed to generate/send chart for {name}: {plot_err}"
            print(msg)
            send_telegram_alert(msg) # Send text alert even if chart fails
             # Optionally send to extra chat_id as well

    except requests.exceptions.RequestException as req_err:
         msg = f"[ERROR] Network/API Request failed for {name}: {str(req_err)}"
         print(msg)
         send_telegram_alert(msg)
         # Optionally send to extra chat_id
    except Exception as e:
        # General exception handler for the main loop of each coin
        msg = f"[CRITICAL ERROR] Unexpected exception for {name}: {str(e)}"
        import traceback
        print(msg)
        print(traceback.format_exc()) # Print full traceback for debugging
        send_telegram_alert(msg)
        extra = os.environ.get('EXTRA_CHAT_ID')
        if extra:
            send_telegram_alert(msg, chat_id=extra)

print("Script finished.")
