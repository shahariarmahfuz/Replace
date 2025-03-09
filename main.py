import time
import requests
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ConversationHandler

# কনভারসেশন স্টেটস
ANIME, SEASON = range(2)

# API URLs
FIRST_API_URL = "https://b15638c8-af87-4164-b831-414c185be4c8-00-3o5w0isf9c16d.pike.replit.dev/up"
SECOND_API_URL = "https://nekofilx.onrender.com/re"

async def start(update: Update, context):
    await update.message.reply_text("হ্যালো! এনিমি ভিডিও আপলোড করতে /add কমান্ড ব্যবহার করুন।")

async def add(update: Update, context):
    await update.message.reply_text("এনিমি নাম্বারটি দিন:")
    return ANIME

async def anime_number(update: Update, context):
    context.user_data['anime'] = update.message.text
    await update.message.reply_text("সিজন নাম্বারটি দিন:")
    return SEASON

async def season_number(update: Update, context):
    context.user_data['season'] = update.message.text
    anime = context.user_data['anime']
    season = context.user_data['season']

    # প্রথম API থেকে ডেটা fetch করা
    response = requests.get(f"https://nekofilx.onrender.com/get?anime={anime}&s={season}")
    if response.status_code == 200:
        data = response.json()
        episodes = data.get('videos', [])

        # এপিসোডগুলিকে সিরিয়াল অনুযায়ী সাজানো (ছোট থেকে বড়)
        episodes.sort(key=lambda x: x['episode'])

        await update.message.reply_text(f"মোট {len(episodes)} টি এপিসোড পাওয়া গেছে। প্রক্রিয়া শুরু হচ্ছে...")

        successful_episodes = []
        failed_episodes = []

        for episode in episodes:
            episode_number = episode['episode']
            hd_link = episode['links']['720p']
            sd_link = episode['links']['480p']

            # প্রথম API এ রিকোয়েস্ট পাঠানো
            first_api_response = requests.get(f"{FIRST_API_URL}?hd={hd_link}&sd={sd_link}")
            if first_api_response.status_code == 200:
                first_api_data = first_api_response.json()
                new_hd_link = first_api_data['links']['hd'].replace("&raw=1", "@raw=1")
                new_sd_link = first_api_data['links']['sd'].replace("&raw=1", "@raw=1")

                # দ্বিতীয় API এ রিকোয়েস্ট পাঠানো
                second_api_response = requests.get(f"{SECOND_API_URL}?a={anime}&s={season}&e={episode_number}&720p={new_hd_link}&480p={new_sd_link}")
                if second_api_response.status_code == 200:
                    second_api_data = second_api_response.json()
                    if second_api_data['status'] == "success":
                        successful_episodes.append(episode_number)
                        await update.message.reply_text(
                            f"এনিমি: {second_api_data['anime']}\n"
                            f"সিজন: {second_api_data['season']}\n"
                            f"এপিসোড: {second_api_data['episode']}\n"
                            f"720p লিংক: {second_api_data['links']['720p']}\n"
                            f"480p লিংক: {second_api_data['links']['480p']}\n"
                            f"এই এপিসোড সফলভাবে আপলোড হয়েছে।"
                        )
                    else:
                        failed_episodes.append(episode_number)
                        await update.message.reply_text(f"এপিসোড {episode_number} আপলোড করতে সমস্যা হয়েছে।")
                else:
                    failed_episodes.append(episode_number)
                    await update.message.reply_text(f"দ্বিতীয় API তে রিকোয়েস্ট পাঠাতে সমস্যা হয়েছে।")
            else:
                failed_episodes.append(episode_number)
                await update.message.reply_text(f"প্রথম API তে রিকোয়েস্ট পাঠাতে সমস্যা হয়েছে।")

            # ৫ সেকেন্ড বিরতি
            time.sleep(5)

        # সকল এপিসোড আপলোড হওয়ার পর সারসংক্ষেপ মেসেজ পাঠানো
        summary_message = "সকল এপিসোড আপলোড সম্পন্ন হয়েছে।\n\n"
        if successful_episodes:
            summary_message += f"সফলভাবে আপলোড হওয়া এপিসোড: {', '.join(map(str, successful_episodes))}\n"
        if failed_episodes:
            summary_message += f"ব্যর্থ হওয়া এপিসোড: {', '.join(map(str, failed_episodes))}\n"

        await update.message.reply_text(summary_message)

    else:
        await update.message.reply_text("দুঃখিত, ডেটা পাওয়া যায়নি।")

    return ConversationHandler.END

async def cancel(update: Update, context):
    await update.message.reply_text("কমান্ড বাতিল করা হয়েছে।")
    return ConversationHandler.END

def main():
    # টেলিগ্রাম টোকেন ব্যবহার করে অ্যাপ্লিকেশন তৈরি
    application = ApplicationBuilder().token("7749823654:AAFnw3PiCgLEDCQqR9Htmhw8AXU2fLEB6vE").build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('add', add)],
        states={
            ANIME: [MessageHandler(filters.TEXT & ~filters.COMMAND, anime_number)],
            SEASON: [MessageHandler(filters.TEXT & ~filters.COMMAND, season_number)],
        },
        fallbacks=[CommandHandler('cancel', cancel)],
    )

    application.add_handler(CommandHandler("start", start))
    application.add_handler(conv_handler)

    application.run_polling()

if __name__ == '__main__':
    main()
