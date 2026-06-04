import os
import requests
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")

SPONSORED_KEYWORDS = [
    "#ad",
    "#sponsored",
    "paid partnership",
    "gifted",
    "affiliate",
    "sponsored by",
    "in collaboration",
    "collab",
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
        "key": YOUTUBE_API_KEY,
    }
    response = requests.get(url, params=params, timeout=20)
    data = response.json()
    return data.get("items", [])

def filter_results(results, organic_only=False):
    if not organic_only:
        return results
    filtered = []
    for item in results:
        desc = item["snippet"].get("description", "")
        if not is_sponsored(desc):
            filtered.append(item)
    return filtered

def trust_score(results):
    if not results:
        return 0
    organic = 0
    for item in results:
        desc = item["snippet"].get("description", "")
        if not is_sponsored(desc):
            organic += 1
    return round((organic / len(results)) * 100)

def organic_count(results):
    count = 0
    for item in results:
        desc = item["snippet"].get("description", "")
        if not is_sponsored(desc):
            count += 1
    return count

def format_results(query: str, results, organic_only=False):
    shown_results = filter_results(results, organic_only=organic_only)

    if not shown_results:
        return f"🔎 Top results for: {query}\n\nNo organic results found."

    score = trust_score(results)
    verdict = "High Trust" if score >= 70 else "Mixed Trust" if score >= 40 else "Low Trust"
    mode = "Organic Only" if organic_only else "All Results"

    lines = [
        f"🔎 Top results for: {query}",
        f"📊 Trust Score: {score}/100 ({verdict})",
        f"🧪 View: {mode}",
    ]

    for i, item in enumerate(shown_results, start=1):
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

def format_compare(product1: str, product2: str, results1, results2):
    score1 = trust_score(results1)
    score2 = trust_score(results2)
    organic1 = organic_count(results1)
    organic2 = organic_count(results2)

    if score1 > score2:
        winner = product1
    elif score2 > score1:
        winner = product2
    else:
        winner = "Tie"

    lines = [
        "⚖️ Product Comparison",
        f"",
        f"1️⃣ {product1}",
        f"📊 Trust Score: {score1}/100",
        f"✅ Organic Reviews: {organic1}/{len(results1) if results1 else 0}",
        f"",
        f"2️⃣ {product2}",
        f"📊 Trust Score: {score2}/100",
        f"✅ Organic Reviews: {organic2}/{len(results2) if results2 else 0}",
        f"",
        f"🏆 Better trust signal: {winner}",
    ]

    return "\n".join(lines)

def results_keyboard(query: str):
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Show Organic Only", callback_data=f"organic::{query}"),
            InlineKeyboardButton("📋 Show All", callback_data=f"all::{query}"),
        ]
    ])

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Send a product name like 'whey protein'\n"
        "Or compare two products like:\n"
        "'compare muscleblaze vs avvatar'"
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.message.text.strip()

    lower_query = query.lower()
    if lower_query.startswith("compare ") and " vs " in lower_query:
        compare_text = query[8:]
        parts = compare_text.split(" vs ", 1)

        if len(parts) == 2:
            product1 = parts[0].strip()
            product2 = parts[1].strip()

            results1 = search_youtube(product1)
            results2 = search_youtube(product2)

            if not results1 or not results2:
                await update.message.reply_text("Could not compare those products. Try again.")
                return

            compare_message = format_compare(product1, product2, results1, results2)
            await update.message.reply_text(compare_message)
            return

    results = search_youtube(query)

    if not results:
        await update.message.reply_text("No results found.")
        return

    message = format_results(query, results, organic_only=False)
    await update.message.reply_text(
        message,
        reply_markup=results_keyboard(query)
    )

async def handle_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query_obj = update.callback_query
    await query_obj.answer()

    data = query_obj.data

    if "::" not in data:
        return

    action, query = data.split("::", 1)
    results = search_youtube(query)

    if not results:
        await query_obj.edit_message_text("No results found.")
        return

    organic_only = action == "organic"
    message = format_results(query, results, organic_only=organic_only)

    await query_obj.edit_message_text(
        text=message,
        reply_markup=results_keyboard(query)
    )

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
app.add_handler(CallbackQueryHandler(handle_buttons))

print("Bot is running...")
app.run_polling(close_loop=False)
