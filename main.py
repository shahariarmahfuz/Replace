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
ANIME, SEASON, CONFIRMATION = range(3)

# API URLs
FIRST_API_URL = "https://replaceup-production.up.railway.app/up"
SECOND_API_URL = "https://nekofilx.onrender.com/re"

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Start command handler"""
    await update.message.reply_text(
        "Hello! Use /add command to upload anime videos."
    )

async def add(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Start anime upload process"""
    await update.message.reply_text("🎌 Enter anime number:")
    return ANIME

async def anime_number(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Store anime number"""
    context.user_data['anime'] = update.message.text
    await update.message.reply_text("📂 Enter season number:")
    return SEASON

async def season_number(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Store season number and show confirmation"""
    context.user_data['season'] = update.message.text
    anime = context.user_data['anime']
    season = context.user_data['season']
    
    confirm_text = (
        f"📝 You're about to upload:\n\n"
        f"• Anime: `{anime}`\n"
        f"• Season: `{season}`\n\n"
        f"✅ Confirm with /send\n"
        f"❌ Cancel with /cancel"
    )
    
    await update.message.reply_text(
        confirm_text,
        parse_mode=ParseMode.MARKDOWN_V2
    )
    return CONFIRMATION

async def send_episodes(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Start episode processing"""
    user_data = context.user_data
    anime = user_data['anime']
    season = user_data['season']
    
    try:
        response = requests.get(f"https://nekofilx.onrender.com/get?anime={anime}&s={season}")
        response.raise_for_status()
        data = response.json()
        
        episodes = sorted(data.get('videos', []), key=lambda x: x['episode'])
        total_episodes = len(episodes)
        
        await update.message.reply_text(
            f"🔎 Found {total_episodes} episodes\n"
            f"⏳ Starting processing..."
        )
        
        successful, failed = await process_episodes(update, anime, season, episodes)
        
        summary = (
            f"📊 **Upload Summary**\n\n"
            f"✅ Success: {len(successful)}\n"
            f"❌ Failed: {len(failed)}\n\n"
            f"Successful episodes: {', '.join(map(str, successful)) if successful else 'None'}\n"
            f"Failed episodes: {', '.join(map(str, failed)) if failed else 'None'}"
        )
        
        await update.message.reply_text(summary)
        
    except Exception as e:
        await handle_error(update, e)
    
    return ConversationHandler.END

async def process_episodes(update, anime, season, episodes):
    """Process episodes helper function"""
    successful = []
    failed = []
    
    for episode in episodes:
        ep_num = episode['episode']
        try:
            # Process first API
            hd_link = episode['links']['720p']
            sd_link = episode['links']['480p']
            
            first_res = requests.get(f"{FIRST_API_URL}?hd={hd_link}&sd={sd_link}")
            first_res.raise_for_status()
            
            # Update links
            new_hd = first_res.json()['links']['hd'].replace("&raw=1", "@raw=1")
            new_sd = first_res.json()['links']['sd'].replace("&raw=1", "@raw=1")
            
            # Process second API
            params = {
                'a': anime,
                's': season,
                'e': ep_num,
                '720p': new_hd,
                '480p': new_sd
            }
            second_res = requests.get(SECOND_API_URL, params=params)
            second_res.raise_for_status()
            
            # Send success message
            data = second_res.json()
            await send_success_message(update, data)
            successful.append(ep_num)
            
        except Exception as e:
            await update.message.reply_text(f"⚠️ Error in episode {ep_num}: {str(e)}")
            failed.append(ep_num)
        
        time.sleep(5)
    
    return successful, failed

async def send_success_message(update, data):
    """Format success message"""
    message = (
        f"✨ **Successfully Uploaded**\n\n"
        f"• Anime: `{data['anime']}`\n"
        f"• Season: `{data['season']}`\n"
        f"• Episode: `{data['episode']}`\n\n"
        f"🔗 [720p Link]({data['links']['720p']})\n"
        f"🔗 [480p Link]({data['links']['480p']})"
    )
    await update.message.reply_text(
        message,
        parse_mode=ParseMode.MARKDOWN_V2,
        disable_web_page_preview=True
    )

async def handle_error(update, error):
    """Error handling"""
    error_msg = (
        f"🚨 **Error Occurred**\n\n"
        f"`{str(error)}`\n\n"
        f"Please try again."
    )
    await update.message.reply_text(
        error_msg,
        parse_mode=ParseMode.MARKDOWN_V2
    )

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancel conversation"""
    await update.message.reply_text("❌ Process cancelled")
    context.user_data.clear()
    return ConversationHandler.END

def main() -> None:
    """Application setup"""
    application = ApplicationBuilder().token("7749823654:AAFnw3PiCgLEDCQqR9Htmhw8AXU2fLEB6vE").build()
    
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('add', add)],
        states={
            ANIME: [MessageHandler(filters.TEXT & ~filters.COMMAND, anime_number)],
            SEASON: [MessageHandler(filters.TEXT & ~filters.COMMAND, season_number)],
            CONFIRMATION: [
                CommandHandler('send', send_episodes),
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
