import re
import time
import requests
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    filters,
    ConversationHandler,
    ContextTypes
)

# Conversation states
ANIME, SEASON, CONFIRM = range(3)

# API URLs
FIRST_API_URL = "https://replaceup-production.up.railway.app/up"
SECOND_API_URL = "https://nekofilx.onrender.com/re"

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Hello! Use the /add command to upload anime videos."
    )

async def add(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Enter the anime number:")
    return ANIME

async def anime_number(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['anime'] = update.message.text
    await update.message.reply_text("Enter the season number:")
    return SEASON

async def season_number(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['season'] = update.message.text
    anime = context.user_data['anime']
    season = context.user_data['season']

    response = requests.get(f"https://nekofilx.onrender.com/get?anime={anime}&s={season}")
    if response.status_code == 200:
        data = response.json()
        episodes = sorted(data.get('videos', []), key=lambda x: x['episode'])
        context.user_data['episodes'] = episodes
        
        message = (
            f"Found {len(episodes)} episodes!\n"
            f"Confirm upload with /send\n"
            f"Cancel with /cancel"
        )
        await update.message.reply_text(message)
        return CONFIRM
    else:
        await update.message.reply_text("Failed to fetch data ❌")
        return ConversationHandler.END

async def confirm_upload(update: Update, context: ContextTypes.DEFAULT_TYPE):
    anime = context.user_data['anime']
    season = context.user_data['season']
    episodes = context.user_data['episodes']

    await update.message.reply_text("Starting upload...")

    successful = []
    failed = []

    for episode in episodes:
        try:
            ep_num = episode['episode']
            hd_link = episode['links']['720p']
            sd_link = episode['links']['480p']

            # Process first API
            first_api = requests.get(f"{FIRST_API_URL}?hd={hd_link}&sd={sd_link}")
            if first_api.status_code != 200:
                raise Exception("First API error")

            processed_links = first_api.json()['links']
            new_hd = processed_links['hd'].replace("&raw=1", "@raw=1")
            new_sd = processed_links['sd'].replace("&raw=1", "@raw=1")

            # Process second API
            second_api = requests.get(
                f"{SECOND_API_URL}?a={anime}&s={season}&e={ep_num}&720p={new_hd}&480p={new_sd}"
            )
            if second_api.status_code != 200 or second_api.json().get('status') != 'success':
                raise Exception("Second API error")

            # Format success message
            response_data = second_api.json()
            message = (
                f"_{escape_md(response_data['anime'])}_\n"
                f"**Season:** {escape_md(str(response_data['season']))}\n"
                f"**Episode:** {escape_md(str(response_data['episode']))}\n\n"
                f"[720p Link]({escape_md(response_data['links']['720p'])})\n"
                f"[480p Link]({escape_md(response_data['links']['480p'])})\n\n"
                "> This anime has been uploaded successfully ✅"
            )
            
            await update.message.reply_text(
                message,
                parse_mode=ParseMode.MARKDOWN_V2
            )
            successful.append(ep_num)

        except Exception as e:
            failed.append(ep_num)
            await update.message.reply_text(f"Episode {ep_num} failed: {str(e)}")

        time.sleep(5)

    # Send summary
    summary = (
        f"📊 **Upload Summary**\n\n"
        f"✅ Success: {len(successful)}\n"
        f"❌ Failed: {len(failed)}\n\n"
        f"Successful episodes: {', '.join(map(str, successful)) if successful else 'None'}\n"
        f"Failed episodes: {', '.join(map(str, failed)) if failed else 'None'}"
    )
    await update.message.reply_text(summary, parse_mode=ParseMode.MARKDOWN_V2)
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Process canceled ❌")
    return ConversationHandler.END

def escape_md(text: str) -> str:
    """Escape Markdown V2 special characters"""
    return re.sub(r"([_*\[\]()~`>#+\-=|{}.!])", r"\\\1", text)

def main():
    application = ApplicationBuilder().token("7749823654:AAFnw3PiCgLEDCQqR9Htmhw8AXU2fLEB6vE").build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('add', add)],
        states={
            ANIME: [MessageHandler(filters.TEXT & ~filters.COMMAND, anime_number)],
            SEASON: [MessageHandler(filters.TEXT & ~filters.COMMAND, season_number)],
            CONFIRM: [
                CommandHandler('send', confirm_upload),
                CommandHandler('cancel', cancel)
            ]
        },
        fallbacks=[CommandHandler('cancel', cancel)],
    )

    application.add_handler(CommandHandler("start", start))
    application.add_handler(conv_handler)
    application.run_polling()

if __name__ == '__main__':
    main()
