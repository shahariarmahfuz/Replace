import time
import requests
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ConversationHandler, CallbackContext
from telegram.constants import ParseMode

# কনভারসেশন স্টেটস
ANIME, SEASON, CONFIRMATION = range(3)

# API URLs
FIRST_API_URL = "https://replaceup-production.up.railway.app/up"
SECOND_API_URL = "https://nekofilx.onrender.com/re"

async def start(update: Update, context: CallbackContext):
    """Handles the /start command."""
    await update.message.reply_text("হ্যালো! এনিমি ভিডিও আপলোড করতে /add কমান্ড ব্যবহার করুন।")

async def add(update: Update, context: CallbackContext):
    """Handles the /add command to start the anime upload process."""
    await update.message.reply_text("এনিমি নাম্বারটি দিন:")
    return ANIME

async def anime_number(update: Update, context: CallbackContext):
    """Handles the anime number input from the user."""
    context.user_data['anime'] = update.message.text
    await update.message.reply_text("সিজন নাম্বারটি দিন:")
    return SEASON

async def season_number(update: Update, context: CallbackContext):
    """Handles the season number input and fetches episode data."""
    context.user_data['season'] = update.message.text
    anime_name = context.user_data['anime']
    season_number_input = context.user_data['season']

    try:
        # ডেটা fetch করার জন্য দ্বিতীয় API ব্যবহার করা হচ্ছে (কারণ এটি get endpoint সাপোর্ট করে)
        response = requests.get(f"{SECOND_API_URL}/get?anime={anime_name}&s={season_number_input}")
        response.raise_for_status()  # Raises HTTPError for bad responses (4xx or 5xx)
        data = response.json()
        episodes = data.get('videos', [])

        if not episodes:
            await update.message.reply_text("দুঃখিত, এই সিজনের জন্য কোন এপিসোড পাওয়া যায়নি। আপলোড বাতিল করা হলো।")
            return ConversationHandler.END

        # এপিসোডগুলিকে সিরিয়াল অনুযায়ী সাজানো (ছোট থেকে বড়)
        episodes.sort(key=lambda x: int(x['episode'])) # episode number should be integer for correct sorting

        context.user_data['episodes'] = episodes # Save episodes data for send command
        context.user_data['successful_episodes'] = []
        context.user_data['failed_episodes'] = []

        episode_count = len(episodes)
        confirmation_message_md = (
            f"মোট *{episode_count}* টি এপিসোড পাওয়া গেছে। আপলোড শুরু করতে /send কমান্ড দিন অথবা /cancel কমান্ড দিয়ে বাতিল করুন।"
        )
        await update.message.reply_text(confirmation_message_md, parse_mode=ParseMode.MARKDOWN_V2)
        return CONFIRMATION

    except requests.exceptions.RequestException as e:
        error_message = f"ডেটা fetch করতে সমস্যা হয়েছে। API request error: {e}"
        await update.message.reply_text(error_message)
        return ConversationHandler.END
    except ValueError: # catches json decode errors
        await update.message.reply_text("API থেকে ডেটা পার্স করতে সমস্যা হয়েছে।")
        return ConversationHandler.END


async def send_episodes(update: Update, context: CallbackContext):
    """Handles the /send command and starts uploading episodes after confirmation."""
    episodes = context.user_data.get('episodes', [])
    successful_episodes = context.user_data.get('successful_episodes', [])
    failed_episodes = context.user_data.get('failed_episodes', [])
    anime_name = context.user_data['anime']
    season_number_input = context.user_data['season']


    if not episodes:
        await update.message.reply_text("কোন এপিসোড আপলোডের জন্য নেই।")
        return ConversationHandler.END

    await update.message.reply_text(f"আপলোড প্রক্রিয়া শুরু হচ্ছে...")

    for episode in episodes:
        episode_number = episode['episode']
        hd_link = episode['links']['720p']
        sd_link = episode['links']['480p']

        try:
            # প্রথম API এ রিকোয়েস্ট পাঠানো
            first_api_response = requests.get(f"{FIRST_API_URL}?hd={hd_link}&sd={sd_link}")
            first_api_response.raise_for_status()
            first_api_data = first_api_response.json()
            new_hd_link = first_api_data['links']['hd'].replace("&raw=1", "@raw=1")
            new_sd_link = first_api_data['links']['sd'].replace("&raw=1", "@raw=1")

            # দ্বিতীয় API এ রিকোয়েস্ট পাঠানো
            second_api_response = requests.get(
                f"{SECOND_API_URL}?a={anime_name}&s={season_number_input}&e={episode_number}&720p={new_hd_link}&480p={new_sd_link}"
            )
            second_api_response.raise_for_status()
            second_api_data = second_api_response.json()

            if second_api_data['status'] == "success":
                successful_episodes.append(episode_number)
                success_message_md = (
                    f"*এনিমি:* `{second_api_data['anime']}`\n"
                    f"*সিজন:* `{second_api_data['season']}`\n"
                    f"*এপিসোড:* `{second_api_data['episode']}`\n"
                    f"*720p লিংক:* `{second_api_data['links']['720p']}`\n"
                    f"*480p লিংক:* `{second_api_data['links']['480p']}`\n\n"
                    f"_এই এপিসোড সফলভাবে আপলোড হয়েছে।_"
                )
                await update.message.reply_text(success_message_md, parse_mode=ParseMode.MARKDOWN_V2)
            else:
                failed_episodes.append(episode_number)
                await update.message.reply_text(f"এপিসোড {episode_number} আপলোড করতে সমস্যা হয়েছে।")

        except requests.exceptions.RequestException as e:
            failed_episodes.append(episode_number)
            await update.message.reply_text(f"এপিসোড {episode_number} আপলোড করতে সমস্যা হয়েছে। API request error: {e}")
        except ValueError: # catches json decode errors
            failed_episodes.append(episode_number)
            await update.message.reply_text(f"এপিসোড {episode_number} আপলোড করতে সমস্যা হয়েছে। ডেটা পার্সিং এরর।")

        # ৫ সেকেন্ড বিরতি
        time.sleep(5)

    # সকল এপিসোড আপলোড হওয়ার পর সারসংক্ষেপ মেসেজ পাঠানো
    summary_message_md = "*সকল এপিসোড আপলোড সম্পন্ন হয়েছে।*\n\n"
    if successful_episodes:
        summary_message_md += f"*সফলভাবে আপলোড হওয়া এপিসোড:* `{', '.join(map(str, successful_episodes))}`\n"
    if failed_episodes:
        summary_message_md += f"*ব্যর্থ হওয়া এপিসোড:* `{', '.join(map(str, failed_episodes))}`\n"

    await update.message.reply_text(summary_message_md, parse_mode=ParseMode.MARKDOWN_V2)
    return ConversationHandler.END


async def cancel(update: Update, context: CallbackContext):
    """Handles the /cancel command to cancel the conversation."""
    await update.message.reply_text("আপলোড বাতিল করা হয়েছে।")
    return ConversationHandler.END

def main():
    """Main function to start the bot."""
    application = ApplicationBuilder().token("7749823654:AAFnw3PiCgLEDCQqR9Htmhw8AXU2fLEB6vE").build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('add', add)],
        states={
            ANIME: [MessageHandler(filters.TEXT & ~filters.COMMAND, anime_number)],
            SEASON: [MessageHandler(filters.TEXT & ~filters.COMMAND, season_number)],
            CONFIRMATION: [
                CommandHandler('send', send_episodes),
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
