# Crypto RSI Alert Bot

A fully automated Python script that analyzes price action and technical indicators (RSI, MA50, price change %, volume) for multiple cryptocurrencies and sends real-time alerts to Telegram. Built for traders who want to catch strong market moves without noise.

---

## Features

- Supports Bitcoin (BTC), Solana (SOL), and Chainlink (LINK)
- Runs every **30 minutes** using GitHub Actions
- Checks:
  - 1h price change % (detect pump/dump)
  - 24h price change % (daily overview)
  - RSI (overbought / oversold)
  - MA50 (trend)
  - Volume spikes (confirmation)
- Sends alerts via **Telegram bot** with Markdown formatting and price charts
- Only triggers on actionable advice (BUY, SELL, STRONG BUY/SELL)
- Sends daily price overview at **10:00 AM**

---

## Requirements

- GitHub account with GitHub Actions enabled
- Telegram bot 
- Secrets configured:
  - `TWELVE_API_KEY`: API key from https://twelvedata.com
  - `BOT_TOKEN`: Your Telegram bot token
  - `CHAT_ID`: Your main Telegram user ID
  - *(Optional)* `EXTRA_CHAT_ID`: For second person to receive alerts

---

## How it works

1. GitHub Actions runs the script every 30 minutes
2. For each coin:
   - Downloads historical price + volume data from Twelve Data
   - Calculates RSI, MA50, price changes, and volume average
   - If strong price movement + volume spike → triggers STRONG BUY/SELL
   - If RSI/MA suggest a setup → triggers BUY/SELL fallback
3. Sends an alert to Telegram including:
   - Indicator values
   - Market sentiment
   - Advice + chart image

4. At 10:00 AM, sends daily change report even if no alerts triggered

---

## Example Alert
```
*Bitcoin*
*RSI:* 72.15
*Change (1h):* +3.57%
*Change (24h):* +6.03%
*Trend:* UP (MA50)
*Volume:* 20500 vs MA: 12300
*Advice:* STRONG SELL
Sentiment: Bearish + Volume Spike
```

---

## Customize
- Change alert thresholds in the `btc_alert.py` logic
- Add more coins to the `COINS` dictionary
- Adjust `MA_PERIOD` or `RSI_PERIOD` for different strategies

---

## Testing
You can manually run the script via GitHub Actions → "Run workflow". If no alerts are triggered, it will remain silent (except 10:00 daily update).

---

## Security
This repo uses GitHub Secrets for all credentials. Never commit your API key or bot token directly.

---

## License
MIT — free to use, modify and share.
Robin A. 2025
