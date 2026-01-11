# GFinance Project

## Overview

GLD (Gold ETF) price monitor that alerts via email when price drops 2%+ from its 30-day high. Runs on GitHub Actions.
We will monitor other key assets as we keep expanding

## Key Files

- `gld_monitor.py` - Main script: fetches price data, checks threshold, sends email alerts
- `.github/workflows/gld-monitor.yml` - GitHub Actions workflow (scheduled runs)
- `requirements.txt` - Python dependencies

## Architecture

- **Data source**: Yahoo Finance via `yfinance`
- **Alerting**: Email via SMTP (Gmail)
- **Logging**: Persistent logs via GitHub Gist API (not local file, since Actions runners are ephemeral)
- **State**: `gld_monitor_state.json` tracks last alert to avoid spam

## Required Secrets (GitHub Actions)

- `SENDER_EMAIL`, `SENDER_PASSWORD`, `RECIPIENT_EMAIL` - Email config
- `SMTP_SERVER`, `SMTP_PORT` - SMTP settings
- `GIST_ID`, `GIST_TOKEN` - For persistent logging to a GitHub Gist

## Local Development

Uses `.env` file via `python-dotenv` for local testing.
