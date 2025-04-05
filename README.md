# Crypto RSI Alert Bot

Automated RSI and trend analysis for cryptocurrencies (BTC, SOL, LINK) with Telegram alerts, chart generation, and scheduled GitHub Actions runs.

## Features
- Runs every 2 hours via GitHub Actions
- RSI calculation (14 candles, 1h interval)
- % price change over the last 2 hours
- MA50 trend filter (up/down trend)
- Chart with price, MA, and RSI
- Telegram alert with image

## Required (GitHub Secrets)
- `BOT_TOKEN`: Your Telegram bot token (via BotFather)
- `CHAT_ID`: Your personal Telegram chat ID
- `EXTRA_CHAT_ID`: (optional) ID of additional recipient
- `TWELVE_API_KEY`: Free API key from https://twelvedata.com

## Coins
Default: BTC/USD, SOL/USD, LINK/USD
Easily extendable in the `COINS = {}` section in `btc_alert.py`

## Example Alert
```
[Bitcoin] RSI = 69.41 — OVERBOUGHT
Change (2h): +3.12%
Trend: ↑ UP (MA50)
```

Includes a visual chart with price and RSI.

## Disclaimer
This project contains no API keys or tokens. Everything is securely handled via GitHub Secrets. Use only with your own API credentials.

## Author
Robin A. — 2025
