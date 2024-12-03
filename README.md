# Telegram RSS Bot

A Python-based Telegram bot for fetching and posting RSS feed updates to specific Telegram channels. The bot automatically monitors and posts articles from specified RSS feeds in multiple languages.

## Features

- Supports multiple RSS feeds for different languages.
- Posts news updates to predefined Telegram channels.
- Filters articles based on publication time to ensure timely updates.
- Logs all operations for easy debugging.
- Includes retry and backoff mechanisms for reliable feed fetching.
- Customizable fetch interval.

## Installation

1. **Clone the Repository**:
    ```bash
    git clone https://github.com/elijaharch/telegram-rss-bot.git
    cd telegram-rss-bot
2. **Install Dependencies**:
    ```bash
    pip install -r requirements.txt
3. **Set Up The Environment Variable**: Create a .env file in the project directory with the following content:
    ```env
    TELEGRAM_BOT_TOKEN=your_telegram_bot_token
4. **Run the Bot**:
    ```bash
    python main.py

## Configuration
Map Telegram channels to feeds using the ```CHANNEL_FEEDS``` dictionary:
    ```python
    CHANNEL_FEEDS = {
        "@your_channel_en": {"language": "EN", "feeds": RSS_FEEDS["EN"]},
        "@your_channel_ru": {"language": "RU", "feeds": RSS_FEEDS["RU"]},
    }
Fetching interval can be adjusted using the `FETCH_INTERVAL` variable

## Logging
Logs are saved to a file named bot.log and printed to the console:

Info logs track bot activity.
Error logs capture issues for debugging.

## Dependencies
Telebot
Feedparser
Dotenv
Requests
Backoff
Python-dateutil
Install all dependencies using `bash pip install -r requirements.txt.`

## Usage
Add your Telegram bot token to the .env file.
Configure RSS feeds and Telegram channels in the script.
Run the bot to start monitoring and posting updates.

## Contributing
Contributions are welcome! Fork the repository, create a branch, and submit a pull request with your improvements.