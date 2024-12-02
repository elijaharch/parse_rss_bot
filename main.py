import telebot
import feedparser
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import time
import threading
from datetime import datetime, timedelta
from dateutil import parser as dateutil_parser
from dotenv import load_dotenv
import os
import logging
import requests
import pytz

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
if not TELEGRAM_BOT_TOKEN:
    raise ValueError("Bot token not found. Please set TELEGRAM_BOT_TOKEN in the .env file.")
    
# Initialize bot
bot = telebot.TeleBot(TELEGRAM_BOT_TOKEN)

# RSS Feeds Dictionary
RSS_FEEDS = {
    "EN": [
        {"url": "https://rss.cnn.com/rss/edition.rss", "source": "CNN"},
        {"url": "https://feeds.bbci.co.uk/news/rss.xml", "source": "BBC News"},
        {"url": "https://www.reuters.com/tools/rss", "source": "Reuters"}
    ],
    "RU": [
        {"url": "https://lenta.ru/rss", "source": "Lenta.ru"},
        {"url": "http://static.feed.rbc.ru/rbc/logical/footer/news.rss", "source": "RBC News"},
    ]
}

CHANNEL_FEEDS = {
    "@promotesten": {"language": "EN", "feeds": RSS_FEEDS["EN"]},
    "@promotestru": {"language": "RU", "feeds": RSS_FEEDS["RU"]},
}

user_channels = {}

posted_articles = {lang: set() for lang in RSS_FEEDS}
user_states = {}

FETCH_INTERVAL = 15

# Logging Configuration
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("bot.log"),
        logging.StreamHandler()
    ]
)

from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry

def fetch_feed_with_timeout(url, timeout=10):
    session = requests.Session()
    retries = Retry(total=5, backoff_factor=1, status_forcelist=[500, 502, 503, 504])
    session.mount("https://", HTTPAdapter(max_retries=retries))

    try:
        response = session.get(url, timeout=timeout)
        response.raise_for_status()
        return feedparser.parse(response.content)
    except requests.exceptions.RequestException as e:
        logging.error(f"Failed to fetch feed {url}: {e}")
        return {"entries": []}

def fetch_new_articles(lang, feeds):
    """Fetch new articles from given feeds."""
    new_articles = []
    for feed in feeds:
        feed_url = feed["url"]
        logging.info(f"Fetching feed: {feed_url}")
        try:
            feed_parsed = fetch_feed_with_timeout(feed_url)
            logging.info(f"Feed parsed successfully for {feed_url}. Found {len(feed_parsed.entries)} entries.")
        except Exception as e:
            logging.error(f"Failed to parse feed {feed_url}: {e}")
            continue

        for entry in feed_parsed.entries:
            published_time = entry.get("published", None)
            if published_time:
                try:
                    # Ensure time is parsed with timezone info
                    published_datetime = dateutil_parser.parse(published_time)
                    
                    # Convert to UTC for consistent comparison
                    published_datetime = published_datetime.astimezone(pytz.UTC)
                    now_utc = datetime.now(pytz.UTC)
                    
                    # Calculate time difference
                    time_difference = now_utc - published_datetime
                    
                    # Compare with a timedelta threshold (e.g., 2 minutes)
                    if time_difference <= timedelta(minutes=2):
                        if entry.link not in posted_articles[lang]:
                            new_articles.append(entry)
                            posted_articles[lang].add(entry.link)
                except Exception as e:
                    logging.error(f"Error processing publish date for {entry.title}: {e}")
    return new_articles

def format_article_message(article):
    return f"📰 {article.title}\n<a href='{article.link}'>Читать дальше</a>"

def post_new_articles(language, channel):
    feeds = CHANNEL_FEEDS[channel]["feeds"]
    
    for feed in feeds:
        feed_url = feed["url"]
        
        feed_parsed = feedparser.parse(feed_url)
        for article in feed_parsed.entries:
            message = format_article_message(article)
            
            try:
                bot.send_message(channel, message, parse_mode="HTML")
                print(f"Message posted to {channel}: {message[:25]}")
            except Exception as e:
                print(f"Failed to send message to {channel}: {e}")
                
@bot.message_handler(commands=['start', 'language'])
def send_language_choice(message):
    markup = InlineKeyboardMarkup()
    markup.row_width = 2
    markup.add(
        InlineKeyboardButton("English", callback_data="lang_EN"),
        InlineKeyboardButton("Русский", callback_data="lang_RU")
    )
    bot.send_message(
        message.chat.id, 
        "Choose the language for the news feed:", 
        reply_markup=markup
    )

@bot.callback_query_handler(func=lambda call: call.data.startswith("lang_"))
def handle_language_choice(call):
    language = call.data.split("_")[1]
    chat_id = call.message.chat.id

    for channel, config in CHANNEL_FEEDS.items():
        if config["language"] == language:
            user_channels[chat_id] = channel 

    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("Cancel", callback_data="cancel"))
    bot.send_message(
        chat_id,
        f"You chose {language}. Fetching news in {language} shortly.",
        reply_markup=markup
    )

    # Start posting news after a delay
    def delayed_post():
        time.sleep(5)
        if chat_id in user_states and not user_states[chat_id]["cancel"]:
            bot.send_message(chat_id, f"Fetching and posting the latest news in {language}!")
            post_new_articles(language)
        if chat_id in user_states:
            del user_states[chat_id]

    threading.Thread(target=delayed_post).start()

# Callback for cancel button
@bot.callback_query_handler(func=lambda call: call.data == "cancel")
def handle_cancel(call):
    chat_id = call.message.chat.id
    
    if chat_id in user_states:  # Only proceed if the user has a state
        user_states[chat_id]["cancel"] = True  # Mark the request as canceled
        bot.answer_callback_query(call.id, "Posting canceled!")
        bot.send_message(chat_id, "Выбор отменён.")
        del user_states[chat_id]  # Remove the state
    else:
        print(f"No user state found for chat_id {chat_id}")
        
def monitor_news():
    """Continuously fetch and post news for all channels."""
    while True:
        for channel, config in CHANNEL_FEEDS.items():
            language = config["language"]
            feeds = config["feeds"]
            logging.info(f"Fetching news for {language} on channel {channel}...")

            try:
                new_articles = fetch_new_articles(language, feeds)
                if new_articles:
                    for article in new_articles:
                        message = format_article_message(article)
                        try:
                            bot.send_message(channel, message, parse_mode="HTML")
                            logging.info(f"Message sent to {channel}: {article.title}")
                        except Exception as e:
                            logging.error(f"Failed to send message for article {article.title}: {e}")
                else:
                    logging.info(f"No new articles found for {language} on channel {channel}.")
            except Exception as e:
                logging.error(f"Error fetching articles for {language}: {e}")

        logging.info(f"Waiting {FETCH_INTERVAL} seconds before the next fetch...")
        time.sleep(FETCH_INTERVAL)

def safe_monitor_news():
    """Wrapper to restart monitor_news in case of crashes."""
    while True:
        try:
            monitor_news()
        except Exception as e:
            logging.error(f"Monitor news loop crashed: {e}")
            time.sleep(5)  # Wait before restarting
        
if __name__ == "__main__":
    news_thread = threading.Thread(target=safe_monitor_news, daemon=True)
    news_thread.start()

    logging.info("Bot started. Listening for updates...")
    while True:
        try:
            bot.infinity_polling()
        except Exception as e:
            logging.error(f"Bot polling crashed: {e}")
            time.sleep(5)    