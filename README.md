# Crypto RSI Alert Bot

Automated RSI, MACD, and Bollinger Bands analysis for cryptocurrencies (BTC, SOL, LINK) with Telegram alerts, chart generation, and scheduled GitHub Actions runs.

## Features
- Runs every hour via GitHub Actions
- RSI calculation (14 periods, 1h interval)
- MACD and Signal line comparison
- Bollinger Bands analysis (Upper / Lower band triggers)
- % price change over the last 2h and 24h
- MA50 trend detection
- Alerts only sent when at least one indicator is in a strong zone (RSI/MACD/BB)
- Markdown-styled alerts with sentiment labels and emoji
- Chart with price and RSI sent as Telegram image

## Example Alert (via Telegram)
```
*Bitcoin*
*RSI:* 28.31 → _Bullish 🟢_
*MACD:* 0.0154 vs -0.0021 → _Bullish 🟢_
*BBANDS:* 66400.32 < lower → _Bullish 🟢_
*Advice:* *STRONG BUY ✅*
*Change (2h):* -3.91%
*Change (24h):* -7.32%
*Trend:* ↓ DOWN (MA50)
```

## Required (GitHub Secrets)
- `BOT_TOKEN`: Telegram bot token
- `CHAT_ID`: Personal chat ID
- `EXTRA_CHAT_ID`: (optional) ID of additional recipient
- `TWELVE_API_KEY`: API calls for prices

## Coins
Default: BTC/USD, SOL/USD, LINK/USD
Easily extendable in the `COINS = {}` section in `btc_alert.py`

## Example Alert (via Telegram)
```
*Bitcoin*
*RSI:* 28.31 → _Bullish 🟢_
*MACD:* 0.0154 vs -0.0021 → _Bullish 🟢_
*BBANDS:* 66400.32 < lower → _Bullish 🟢_
*Advice:* *STRONG BUY ✅*
*Change (2h):* -3.91%
*Change (24h):* -7.32%
*Trend:* ↓ DOWN (MA50)
```

Includes a visual chart with price and RSI.

## Disclaimer
This project contains no API keys or tokens. Everything is securely handled via GitHub Secrets. Use only with your own API credentials.

## Author
Robin A. — 2025
