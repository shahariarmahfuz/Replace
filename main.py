import time
import requests
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ConversationHandler

# Conversation States
ANIME, SEASON, CONFIRM = range(3)

# API URLs
FIRST_API_URL = "https://replaceup-production.up.railway.app/up"
SECOND_API_URL = "https://nekofilx.onrender.com/re"

async def start(update: Update, context):
    await update.message.reply_text("Hello! Use /add to upload anime episodes.")

async def add(update: Update, context):
    await update.message.reply_text("📌 *Enter the anime number:*", parse_mode="MarkdownV2")
    return ANIME

async def anime_number(update: Update, context):
    context.user_data['anime'] = update.message.text
    await update.message.reply_text("📌 *Enter the season number:*", parse_mode="MarkdownV2")
    return SEASON

async def season_number(update: Update, context):
    context.user_data['season'] = update.message.text
    anime = context.user_data['anime']
    season = context.user_data['season']

    # Ask for confirmation
    await update.message.reply_text(
        f"✅ *Are you sure you want to upload this anime?*\n\n"
        f"🎭 *Anime:* `{anime}`\n"
        f"📆 *Season:* `{season}`\n\n"
        f"⚡ *To start uploading, send /send*\n"
        f"❌ *To cancel, send /cancel*",
        parse_mode="MarkdownV2"
    )

    return CONFIRM

async def send(update: Update, context):
    anime = context.user_data.get('anime')
    season = context.user_data.get('season')

    if not anime or not season:
        await update.message.reply_text("⚠️ *No active request found, please try again using /add.*", parse_mode="MarkdownV2")
        return ConversationHandler.END

    # Fetch data from API
    response = requests.get(f"https://nekofilx.onrender.com/get?anime={anime}&s={season}")
    if response.status_code == 200:
        data = response.json()
        episodes = data.get('videos', [])
        episodes.sort(key=lambda x: x['episode'])

        await update.message.reply_text(f"🔄 Found `{len(episodes)}` episodes. Uploading started...", parse_mode="MarkdownV2")

        successful_episodes = []
        failed_episodes = []

        for episode in episodes:
            episode_number = episode['episode']
            hd_link = episode['links']['720p']
            sd_link = episode['links']['480p']

            # Request to first API
            first_api_response = requests.get(f"{FIRST_API_URL}?hd={hd_link}&sd={sd_link}")
            if first_api_response.status_code == 200:
                first_api_data = first_api_response.json()
                new_hd_link = first_api_data['links']['hd'].replace("&raw=1", "@raw=1")
                new_sd_link = first_api_data['links']['sd'].replace("&raw=1", "@raw=1")

                # Request to second API
                second_api_response = requests.get(f"{SECOND_API_URL}?a={anime}&s={season}&e={episode_number}&720p={new_hd_link}&480p={new_sd_link}")
                if second_api_response.status_code == 200:
                    second_api_data = second_api_response.json()
                    if second_api_data['status'] == "success":
                        successful_episodes.append(episode_number)
                        await update.message.reply_text(
                            f"🎭 *Anime:* `{second_api_data['anime']}`\n"
                            f"📆 *Season:* `{second_api_data['season']}`\n"
                            f"🎬 *Episode:* `{second_api_data['episode']}`\n\n"
                            f"🔹 *720p:* [Download Link]({second_api_data['links']['720p']})\n"
                            f"🔹 *480p:* [Download Link]({second_api_data['links']['480p']})\n\n"
                            f"> ✅ *This episode has been successfully uploaded!*",
                            parse_mode="MarkdownV2"
                        )
                    else:
                        failed_episodes.append(episode_number)
                        await update.message.reply_text(f"❌ *Failed to upload episode {episode_number}!*", parse_mode="MarkdownV2")
                else:
                    failed_episodes.append(episode_number)
                    await update.message.reply_text(f"⚠️ *Error occurred in the second API!*", parse_mode="MarkdownV2")
            else:
                failed_episodes.append(episode_number)
                await update.message.reply_text(f"⚠️ *Error occurred in the first API!*", parse_mode="MarkdownV2")

            # Wait for 5 seconds before the next request
            time.sleep(5)

        # Send summary
        summary_message = "✅ *All episodes have been uploaded successfully!*\n\n"
        if successful_episodes:
            summary_message += f"✔️ *Success:* `{', '.join(map(str, successful_episodes))}`\n"
        if failed_episodes:
            summary_message += f"❌ *Failed:* `{', '.join(map(str, failed_episodes))}`\n"

        await update.message.reply_text(summary_message, parse_mode="MarkdownV2")

    else:
        await update.message.reply_text("❌ *No data found!*", parse_mode="MarkdownV2")

    return ConversationHandler.END

async def cancel(update: Update, context):
    await update.message.reply_text("❌ *Your request has been canceled!*", parse_mode="MarkdownV2")
    return ConversationHandler.END

def main():
    # Create bot application using Telegram Token
    application = ApplicationBuilder().token("7749823654:AAFnw3PiCgLEDCQqR9Htmhw8AXU2fLEB6vE").build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('add', add)],
        states={
            ANIME: [MessageHandler(filters.TEXT & ~filters.COMMAND, anime_number)],
            SEASON: [MessageHandler(filters.TEXT & ~filters.COMMAND, season_number)],
            CONFIRM: [
                CommandHandler('send', send),
                CommandHandler('cancel', cancel),
            ],
        },
        fallbacks=[CommandHandler('cancel', cancel)],
    )

    application.add_handler(CommandHandler("start", start))
    application.add_handler(conv_handler)

    application.run_polling()

if __name__ == '__main__':
    main()
