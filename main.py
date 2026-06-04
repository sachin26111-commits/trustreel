import os
import requests
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")

SPONSORED_KEYWORDS = [
    "#ad", "#sponsored", "paid partnership", "gifted", "affiliate", "sponsored by", "in collaboration", "collab"
]

def is_sponsored(text: str) -> bool:
    text = (text or "").lower()
    return any(word in text for word in SPONSORED_KEYWORDS)

def search_youtube(query: str):
    url = "https://www.googleapis.com/youtube/v3/search"
    params = {
        "part": "snippet",
        "q": f"{query} review",
        "type": "video",
        "maxResults": 5,
        "key": YOUTUBE_API_KEY
    }
    response = requests.get(url, params=params, timeout=20)
    data = response.json()
    return data.get("items", [])

def trust_score(results):
    if not results:
        return 0
    organic = 0
    for item in results:
        desc = item["snippet"].get("description", "")
        if not is_sponsored(desc):
            organic += 1
    return round((organic / len(results)) * 100)

def format_results(query: str, results):
    score = trust_score(results)
    verdict = "High Trust" if score >= 70 else "Mixed Trust" if score >= 40 else "Low Trust"
    lines = [
        f"🔎 Top results for: {query}",
        f"📊 Trust Score: {score}/100 ({verdict})"
    ]

    for i, item in enumerate(results, start=1):
        title = item["snippet"]["title"]
        channel = item["snippet"]["channelTitle"]
        desc = item["snippet"].get("description", "")
        video_id = item["id"]["videoId"]
        label = "Sponsored" if is_sponsored(desc) else "Organic"
        emoji = "🚨" if label == "Sponsored" else "✅"
        lines.append(
            f"{i}. {emoji} {label}\n"
            f"{title}\n"
            f"{channel}\n"
            f"https://youtu.be/{video_id}"
        )

    return "\n\n".join(lines)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Send me a product name like 'whey protein' and I’ll find YouTube reviews."
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.message.text.strip()
    results = search_youtube(query)

    if not results:
        await update.message.reply_text("No results found.")
        return

    await update.message.reply_text(format_results(query, results))

app = (
    ApplicationBuilder()
    .token(TELEGRAM_BOT_TOKEN)
    .connect_timeout(30)
    .read_timeout(30)
    .write_timeout(30)
    .pool_timeout(30)
    .build()
)

app.add_handler(CommandHandler("start", start))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

print("Bot is running...")
app.run_polling(close_loop=False)