#!/usr/bin/env python3
"""
Asset Price Monitor - Alerts when prices fall 2% from recent highs
Tracks: Gold (GLD), Silver (SLV), Copper (COPX, ICOP)
"""

import yfinance as yf
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta
import json
import os
import requests
from dotenv import load_dotenv

load_dotenv()  # Load .env file for local development

# Configuration
TICKERS = {
    "GLD": "Gold",
    "SLV": "Silver",
    "COPX": "Copper (Global X)",
    "ICOP": "Copper (iShares)",
}
DROP_THRESHOLD = 0.02  # 2% drop threshold
LOOKBACK_DAYS = 30  # Days to look back for recent high

# Email configuration - uses environment variables for CI/CD
EMAIL_CONFIG = {
    "smtp_server": os.getenv("SMTP_SERVER", "smtp.gmail.com"),
    "smtp_port": int(os.getenv("SMTP_PORT", "587")),
    "sender_email": os.getenv("SENDER_EMAIL", ""),
    "sender_password": os.getenv("SENDER_PASSWORD", ""),  # Use Gmail App Password
    "recipient_email": os.getenv("RECIPIENT_EMAIL", ""),
}

# Gist configuration for persistent logging and state
GIST_ID = os.getenv("GIST_ID", "")
GIST_TOKEN = os.getenv("GIST_TOKEN", "")
GIST_LOG_FILE = "gld_monitor.log"
GIST_STATE_FILE = "gld_monitor_state.json"


def log(message: str):
    """Append timestamped message to GitHub Gist."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_entry = f"[{timestamp}] {message}\n"

    # Always print to stdout for GitHub Actions logs
    print(f"LOG: {log_entry.strip()}")

    if not GIST_ID or not GIST_TOKEN:
        print("Warning: GIST_ID or GIST_TOKEN not set, skipping gist logging")
        return

    headers = {"Authorization": f"token {GIST_TOKEN}"}

    try:
        # Get current gist content
        resp = requests.get(f"https://api.github.com/gists/{GIST_ID}", headers=headers)
        resp.raise_for_status()
        current_content = resp.json()["files"][GIST_LOG_FILE]["content"]

        # Append new entry
        new_content = current_content + log_entry

        # Update gist
        update_resp = requests.patch(
            f"https://api.github.com/gists/{GIST_ID}",
            headers=headers,
            json={"files": {GIST_LOG_FILE: {"content": new_content}}}
        )
        update_resp.raise_for_status()
    except Exception as e:
        print(f"Warning: Failed to log to gist: {e}")


def get_ticker_data(ticker: str, name: str, days: int) -> dict:
    """Fetch price data from Yahoo Finance."""
    stock = yf.Ticker(ticker)

    # Get historical data
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days)
    hist = stock.history(start=start_date, end=end_date)

    if hist.empty:
        raise ValueError(f"No data found for {ticker}")

    current_price = hist["Close"].iloc[-1]
    recent_high = hist["High"].max()
    high_date = hist["High"].idxmax()

    return {
        "ticker": ticker,
        "name": name,
        "current_price": round(current_price, 2),
        "recent_high": round(recent_high, 2),
        "high_date": high_date.strftime("%Y-%m-%d"),
        "drop_percent": round((recent_high - current_price) / recent_high * 100, 2),
    }


def send_email_alert(alerts: list, config: dict) -> bool:
    """Send email alert about price drops."""
    if len(alerts) == 1:
        subject = f"{alerts[0]['name']} Alert: {alerts[0]['ticker']} dropped {alerts[0]['drop_percent']}%"
    else:
        tickers = ", ".join(a["ticker"] for a in alerts)
        subject = f"Price Alert: {tickers} dropped from recent highs"

    body = "Price Alert\n\n"
    for data in alerts:
        body += f"""
{data['name']} ({data['ticker']})
  Current Price: ${data['current_price']}
  Recent High: ${data['recent_high']} (on {data['high_date']})
  Drop from High: {data['drop_percent']}%
"""
    body += f"""
Alert threshold: {DROP_THRESHOLD * 100}% drop from {LOOKBACK_DAYS}-day high
Time: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
"""

    msg = MIMEMultipart()
    msg["From"] = config["sender_email"]
    msg["To"] = config["recipient_email"]
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain"))

    try:
        server = smtplib.SMTP(config["smtp_server"], config["smtp_port"])
        server.starttls()
        server.login(config["sender_email"], config["sender_password"])
        server.sendmail(
            config["sender_email"], config["recipient_email"], msg.as_string()
        )
        server.quit()
        print(f"Alert email sent to {config['recipient_email']}")
        return True
    except Exception as e:
        print(f"Failed to send email: {e}")
        return False


def load_state() -> dict:
    """Load previous state from GitHub Gist."""
    if not GIST_ID or not GIST_TOKEN:
        print("Warning: GIST_ID or GIST_TOKEN not set, state won't persist")
        return {}

    headers = {"Authorization": f"token {GIST_TOKEN}"}

    try:
        resp = requests.get(f"https://api.github.com/gists/{GIST_ID}", headers=headers)
        resp.raise_for_status()
        files = resp.json()["files"]

        if GIST_STATE_FILE in files:
            return json.loads(files[GIST_STATE_FILE]["content"])
        return {}
    except Exception as e:
        print(f"Warning: Failed to load state from gist: {e}")
        return {}


def save_state(state: dict):
    """Save state to GitHub Gist."""
    if not GIST_ID or not GIST_TOKEN:
        return

    headers = {"Authorization": f"token {GIST_TOKEN}"}

    try:
        update_resp = requests.patch(
            f"https://api.github.com/gists/{GIST_ID}",
            headers=headers,
            json={"files": {GIST_STATE_FILE: {"content": json.dumps(state, indent=2)}}}
        )
        update_resp.raise_for_status()
    except Exception as e:
        print(f"Warning: Failed to save state to gist: {e}")


def should_send_alert(data: dict, state: dict) -> bool:
    """Determine if we should send an alert (avoid spam)."""
    ticker = data["ticker"]

    # Only alert if drop exceeds threshold
    if data["drop_percent"] < DROP_THRESHOLD * 100:
        return False

    # Avoid re-alerting for the same high (per ticker)
    ticker_state = state.get(ticker, {})
    if ticker_state.get("last_alert_high") == data["recent_high"]:
        print(f"Already alerted for {ticker} at this recent high, skipping...")
        return False

    return True


def main():
    log("=== Asset Monitor Run Started ===")
    state = load_state()
    alerts_to_send = []

    for ticker, name in TICKERS.items():
        print(f"\nFetching {ticker} ({name}) data...")

        try:
            data = get_ticker_data(ticker, name, LOOKBACK_DAYS)
        except Exception as e:
            log(f"ERROR: Failed to fetch {ticker} - {e}")
            print(f"Error fetching {ticker}: {e}")
            continue

        summary = f"{ticker}: ${data['current_price']} | High=${data['recent_high']} ({data['high_date']}) | Drop={data['drop_percent']}%"
        log(summary)

        print(f"  Current Price: ${data['current_price']}")
        print(f"  {LOOKBACK_DAYS}-Day High: ${data['recent_high']} ({data['high_date']})")
        print(f"  Drop from High: {data['drop_percent']}%")

        if should_send_alert(data, state):
            alerts_to_send.append(data)

    print(f"\nAlert Threshold: {DROP_THRESHOLD * 100}%")

    if alerts_to_send:
        tickers_alerting = ", ".join(a["ticker"] for a in alerts_to_send)
        print(f"\nSending alert for: {tickers_alerting}")
        if send_email_alert(alerts_to_send, EMAIL_CONFIG):
            for data in alerts_to_send:
                log(f"ALERT SENT: {data['ticker']} dropped {data['drop_percent']}%")
                state[data["ticker"]] = {
                    "last_alert_high": data["recent_high"],
                    "last_alert_time": datetime.now().isoformat(),
                }
            save_state(state)
        else:
            log("ERROR: Failed to send email alert")
    else:
        print("\nNo alerts needed - all assets within threshold")


if __name__ == "__main__":
    main()
