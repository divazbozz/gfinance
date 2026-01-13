# GFinance Project

## Overview

Asset price monitor that alerts via email when prices drop 2%+ from their 30-day highs. Runs on GitHub Actions.

## Tracked Assets

- **GLD** - Gold ETF
- **SLV** - Silver ETF
- **COPX** - Global X Copper Miners ETF
- **ICOP** - iShares Copper and Metals Mining ETF

## Key Files

- `gld_monitor.py` - Main script: fetches price data, checks threshold, sends email alerts
- `.github/workflows/gld-monitor.yml` - GitHub Actions workflow (scheduled runs)
- `requirements.txt` - Python dependencies

## Architecture

- **Data source**: Yahoo Finance via `yfinance`
- **Alerting**: Email via SMTP (Gmail)
- **Logging**: Persistent logs via GitHub Gist API (not local file, since Actions runners are ephemeral)
- **State**: `gld_monitor_state.json` tracks last alert per ticker to avoid spam

## Required Secrets (GitHub Actions)

- `SENDER_EMAIL`, `SENDER_PASSWORD`, `RECIPIENT_EMAIL` - Email config
- `SMTP_SERVER`, `SMTP_PORT` - SMTP settings
- `GIST_ID`, `GIST_TOKEN` - For persistent logging to a GitHub Gist

## Local Development

Uses `.env` file via `python-dotenv` for local testing.
