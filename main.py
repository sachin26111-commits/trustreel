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
    "sponsored by",
    "promotion by",
    "brand partner",
    "brand ambassador",
]

AFFILIATE_KEYWORDS = [
    "affiliate",
    "affiliate link",
    "commission",
    "commissionable",
    "coupon code",
    "discount code",
    "buy now",
    "shop now",
    "link in description",
    "use my code",
]

TRUST_POSITIVE_KEYWORDS = [
    "honest review",
    "lab test",
    "lab tested",
    "pros and cons",
    "real review",
    "not sponsored",
    "independent review",
    "tested",
    "review after use",
]

def text_blob(item):
    snippet = item.get("snippet", {})
    title = snippet.get("title", "")
    desc = snippet.get("description", "")
    channel = snippet.get("channelTitle", "")
    return f"{title} {desc} {channel}".lower()

def has_any(text: str, keywords):
    return any(keyword in text for keyword in keywords)

def is_sponsored(text: str) -> bool:
    text = (text or "").lower()
    return has_any(text, SPONSORED_KEYWORDS)

def has_affiliate_signal(text: str) -> bool:
    text = (text or "").lower()
    return has_any(text, AFFILIATE_KEYWORDS)

def has_trust_positive_signal(text: str) -> bool:
    text = (text or "").lower()
    return has_any(text, TRUST_POSITIVE_KEYWORDS)

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
        blob = text_blob(item)
        if not is_sponsored(blob):
            filtered.append(item)
    return filtered

def organic_count(results):
    count = 0
    for item in results:
        blob = text_blob(item)
        if not is_sponsored(blob):
            count += 1
    return count

def trust_score(results):
    if not results:
        return 0

    total = 0
    channels = set()

    for item in results:
        blob = text_blob(item)
        channel = item.get("snippet", {}).get("channelTitle", "").strip().lower()
        if channel:
            channels.add(channel)

        score = 50

        if is_sponsored(blob):
            score -= 25

        if has_affiliate_signal(blob):
            score -= 15

        if has_trust_positive_signal(blob):
            score += 15

        total += max(0, min(score, 100))

    avg_score = total / len(results)
    diversity_bonus = min(len(channels) * 5, 15)
    final_score = round(min(avg_score + diversity_bonus, 100))

    return final_score

def trust_verdict(score: int):
    if score >= 75:
        return "High Trust"
    if score >= 45:
        return "Mixed Trust"
    return "Low Trust"

def save_user_search(context: ContextTypes.DEFAULT_TYPE, search_text: str):
    history = context.user_data.get("history", [])
    history.insert(0, search_text)
    history = history[:5]
    context.user_data["history"] = history

def get_user_history(context: ContextTypes.DEFAULT_TYPE):
    return context.user_data.get("history", [])

def format_results(query: str, results, organic_only=False):
    shown_results = filter_results(results, organic_only=organic_only)

    if not shown_results:
        return f"🔎 Top results for: {query}\n\nNo organic results found."

    score = trust_score(results)
    verdict = trust_verdict(score)
    mode = "Organic Only" if organic_only else "All Results"

    lines = [
        f"🔎 Top results for: {query}",
        f"📊 Trust Score: {score}/100 ({verdict})",
        f"🧪 View: {mode}",
    ]

    for i, item in enumerate(shown_results, start=1):
        title = item["snippet"]["title"]
        channel = item["snippet"]["channelTitle"]
        blob = text_blob(item)
        video_id = item["id"]["videoId"]

        label = "Sponsored" if is_sponsored(blob) else "Organic"
        emoji = "🚨" if label == "Sponsored" else "✅"

        signal_bits = []
        if has_trust_positive_signal(blob):
            signal_bits.append("trust+")
        if has_affiliate_signal(blob):
            signal_bits.append("affiliate")
        if is_sponsored(blob):
            signal_bits.append("sponsored")

        signal_text = f" [{', '.join(signal_bits)}]" if signal_bits else ""

        lines.append(
            f"{i}. {emoji} {label}{signal_text}\n"
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
        "",
        f"1️⃣ {product1}",
        f"📊 Trust Score: {score1}/100 ({trust_verdict(score1)})",
        f"✅ Organic Reviews: {organic1}/{len(results1) if results1 else 0}",
        "",
        f"2️⃣ {product2}",
        f"📊 Trust Score: {score2}/100 ({trust_verdict(score2)})",
        f"✅ Organic Reviews: {organic2}/{len(results2) if results2 else 0}",
        "",
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
        "'compare muscleblaze vs avvatar'\n\n"
        "Use /history to see your recent searches."
    )

async def history_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    history = get_user_history(context)

    if not history:
        await update.message.reply_text("No search history yet.")
        return

    lines = ["🕘 Your recent searches:"]
    for i, item in enumerate(history, start=1):
        lines.append(f"{i}. {item}")

    await update.message.reply_text("\n".join(lines))

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.message.text.strip()

    lower_query = query.lower()
    if lower_query.startswith("compare ") and " vs " in lower_query:
        compare_text = query[8:]
        parts = compare_text.split(" vs ", 1)

        if len(parts) == 2:
            product1 = parts[0].strip()
            product2 = parts[1].strip()

            save_user_search(context, f"compare {product1} vs {product2}")

            results1 = search_youtube(product1)
            results2 = search_youtube(product2)

            if not results1 or not results2:
                await update.message.reply_text("Could not compare those products. Try again.")
                return

            compare_message = format_compare(product1, product2, results1, results2)
            await update.message.reply_text(compare_message)
            return

    save_user_search(context, query)

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
app.add_handler(CommandHandler("history", history_command))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
app.add_handler(CallbackQueryHandler(handle_buttons))

print("Bot is running...")
app.run_polling(close_loop=False)
