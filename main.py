import telebot
import feedparser
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import time
import threading
from datetime import datetime, timedelta
from dateutil import parser as dateutil_parser
from dotenv import load_dotenv
import os

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

def fetch_new_articles(language, feeds):
    new_articles = []
    for feed in feeds:
        url = feed["url"]
        source = feed["source"]
        feed_parsed = feedparser.parse(url)
        for entry in feed_parsed.entries:
            # Check if the article is recent (1-2 minutes ago)
            published_time = entry.get('published', None)
            if published_time:
                try:
                    published_datetime = dateutil_parser.parse(published_time)
                    time_difference = datetime.now(published_datetime.tzinfo) - published_datetime

                    if time_difference <= timedelta(minutes=2):
                        if entry.link not in posted_articles[language]:
                            new_articles.append(entry)
                            posted_articles[language].add(entry.link)
                except Exception as e:
                    print(f"Error processing publish date: {e}")
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
    while True:
        for lang, channel_data in CHANNEL_FEEDS.items():
            language = channel_data['language']
            feeds = channel_data['feeds']

            print(f"Fetching news for {language} on channel {lang}...")  # Logs channel info

            try:
                # Fetch new articles for the specified language
                new_articles = fetch_new_articles(language)
                if not new_articles:
                    print(f"No new articles found for {language}. Waiting for {FETCH_INTERVAL} seconds...")
                    time.sleep(FETCH_INTERVAL)  # Wait for the next fetch interval
                    continue  # Skip to the next channel or language

                # If new articles are found, post them
                print(f"Found {len(new_articles)} new articles in {language}")
                for article in new_articles:
                    try:
                        message = format_article_message(article)
                        bot.send_message(lang, message, parse_mode="HTML")  # Send to the appropriate channel
                        print(f"Posted article: {article.title}")
                    except Exception as e:
                        logging.error(f"Failed to send message for article {article.title}: {e}")
                        print(f"Failed to send message for article {article.title}: {e}")
            
            except Exception as e:
                logging.error(f"Error fetching articles for {language}: {e}")
                print(f"Error fetching articles for {language}: {e}")
                
            # Wait before fetching again (fetch interval)
            print(f"Waiting for {FETCH_INTERVAL} seconds before fetching again...")
            time.sleep(FETCH_INTERVAL)
        
if __name__ == "__main__":
    news_thread = threading.Thread(target=monitor_news, daemon=True)
    news_thread.start()