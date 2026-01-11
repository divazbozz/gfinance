#!/usr/bin/env python3
"""
GLD Price Monitor - Alerts when price falls 2% from recent high
"""

import yfinance as yf
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta
import json
import os
from dotenv import load_dotenv

load_dotenv()  # Load .env file for local development

# Configuration
TICKER = "GLD"
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

# State file to track alerts
STATE_FILE = "gld_monitor_state.json"
LOG_FILE = "gld_monitor.log"


def log(message: str):
    """Append timestamped message to log file."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(LOG_FILE, "a") as f:
        f.write(f"[{timestamp}] {message}\n")


def get_gld_data(ticker: str, days: int) -> dict:
    """Fetch GLD price data from Yahoo Finance."""
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
        "current_price": round(current_price, 2),
        "recent_high": round(recent_high, 2),
        "high_date": high_date.strftime("%Y-%m-%d"),
        "drop_percent": round((recent_high - current_price) / recent_high * 100, 2),
    }


def send_email_alert(data: dict, config: dict) -> bool:
    """Send email alert about price drop."""
    subject = f"GLD Alert: Price dropped {data['drop_percent']}% from recent high"

    body = f"""
GLD Price Alert

Current Price: ${data['current_price']}
Recent High: ${data['recent_high']} (on {data['high_date']})
Drop from High: {data['drop_percent']}%

This alert was triggered because GLD has fallen more than 2% from its {LOOKBACK_DAYS}-day high.

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
    """Load previous state from file."""
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r") as f:
            return json.load(f)
    return {"last_alert_high": None, "last_alert_time": None}


def save_state(state: dict):
    """Save state to file."""
    with open(STATE_FILE, "w") as f:
        json.dump(state, f)


def should_send_alert(data: dict, state: dict) -> bool:
    """Determine if we should send an alert (avoid spam)."""
    # Only alert if drop exceeds threshold
    if data["drop_percent"] < DROP_THRESHOLD * 100:
        return False

    # Avoid re-alerting for the same high
    if state.get("last_alert_high") == data["recent_high"]:
        print("Already alerted for this recent high, skipping...")
        return False

    return True


def main():
    log("=== GLD Monitor Run Started ===")
    print(f"Fetching {TICKER} data...")

    try:
        data = get_gld_data(TICKER, LOOKBACK_DAYS)
    except Exception as e:
        log(f"ERROR: Failed to fetch data - {e}")
        print(f"Error fetching data: {e}")
        return

    summary = f"Price=${data['current_price']} | High=${data['recent_high']} ({data['high_date']}) | Drop={data['drop_percent']}%"
    log(summary)

    print(f"\n{TICKER} Price Summary:")
    print(f"  Current Price: ${data['current_price']}")
    print(f"  {LOOKBACK_DAYS}-Day High: ${data['recent_high']} ({data['high_date']})")
    print(f"  Drop from High: {data['drop_percent']}%")
    print(f"  Alert Threshold: {DROP_THRESHOLD * 100}%")

    state = load_state()

    if should_send_alert(data, state):
        print(f"\nPrice has dropped {data['drop_percent']}% - sending alert!")
        if send_email_alert(data, EMAIL_CONFIG):
            log(f"ALERT SENT: Drop {data['drop_percent']}% exceeded threshold")
            state["last_alert_high"] = data["recent_high"]
            state["last_alert_time"] = datetime.now().isoformat()
            save_state(state)
        else:
            log("ERROR: Failed to send email alert")
    else:
        log(f"No alert needed (drop {data['drop_percent']}% < threshold {DROP_THRESHOLD * 100}%)")
        print(
            f"\nNo alert needed (drop {data['drop_percent']}% < threshold {DROP_THRESHOLD * 100}%)"
        )


if __name__ == "__main__":
    main()
