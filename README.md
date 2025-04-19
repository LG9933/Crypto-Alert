**Crypto Alert Bot
**
A fully automated Python script that monitors Bitcoin (BTC), Solana (SOL), and Chainlink (LINK) every 30 minutes to catch rapid pumps, dumps, and volatility spikes, and sends real-time alerts to Telegram.

Features

Supports Bitcoin (BTC), Solana (SOL), and Chainlink (LINK)

Runs every 30 minutes via GitHub Actions (cron & manual dispatch)

Price-action alerts (BTC ≥1.5%, SOL/LINK ≥2.5% per 30 min candle)

ATR-based volatility spikes (True Range ≥1.2×ATR(14))

Test-run mode reports all coins with current % change and ATR

Mini price charts for quick visual context

**Requirements
**
Python 3.10+ with:

requests

pandas

matplotlib

Telegram bot token & chat ID

TwelveData API key

GitHub Actions for scheduling

How It Works

Schedule: GitHub Actions triggers every 30 minutes (and supports manual workflow_dispatch).

Data: Fetches last 6 candles (30 min interval) for each coin via TwelveData.

Price Alerts: Compares current vs. previous close; triggers Pump/Dump alerts when thresholds are met.

Volatility Alerts: Fetches ATR(14) and flags True Range spikes ≥1.2×ATR.

Notifications: Sends Telegram messages with emoji, text, and mini price charts.

Test Mode: On manual runs, reports all current changes and ATR without filtering.

Example Alert

🕒 2025-04-19 12:00 UTC
📈 Bitcoin Pump! +2.30%
⚡ Bitcoin Volatility! TR 450.00 ≥ 1.2×ATR(380.00)

Customize

Adjust thresholds in the COINS dictionary in crypto_alert.py

Modify ATR_PERIOD and ATR_MULTIPLIER for volatility sensitivity

Add or remove coins in COINS

Testing

Use the Run workflow button in GitHub Actions to trigger a test run.

In test mode, you’ll get a summary of all coins regardless of thresholds.

Security

Store TWELVE_API_KEY, BOT_TOKEN, and CHAT_ID as GitHub Secrets.

Do not commit credentials to the repository.

License

MIT © Robin A. 2025
