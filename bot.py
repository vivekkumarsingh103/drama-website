import os
import logging
import re
import threading
from datetime import datetime
from dotenv import load_dotenv
from pymongo import MongoClient
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes, ConversationHandler
from flask import Flask, jsonify
from flask_cors import CORS

# Load environment variables
load_dotenv()

# Initialize Flask app for Render
app = Flask(__name__)
CORS(app)

@app.route('/')
def home():
    return jsonify({"status": "dramawallah bot is running", "version": "1.0"})

@app.route('/health')
def health():
    return jsonify({"status": "healthy"})

@app.route('/api/dramas')
def api_dramas():
    try:
        dramas = list(dramas_collection.find({"type": "drama"}, {'_id': 0}))
        return jsonify({"success": True, "data": dramas})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/ongoing')
def api_ongoing():
    try:
        ongoing = list(dramas_collection.find({"type": "ongoing"}, {'_id': 0}))
        return jsonify({"success": True, "data": ongoing})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/news')
def api_news():
    try:
        news = list(news_collection.find({}, {'_id': 0}).sort('created_at', -1).limit(5))
        return jsonify({"success": True, "data": news})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

# MongoDB connection
try:
    client = MongoClient(os.getenv('MONGODB_URI'))
    db = client.dramawallah
    dramas_collection = db.dramas
    news_collection = db.news
    users_collection = db.users
    force_sub_collection = db.force_sub
    logging.info("✅ connected to mongodb")
except Exception as e:
    logging.error(f"❌ mongodb connection failed: {e}")

# Bot configuration
BOT_TOKEN = os.getenv('BOT_TOKEN')
ADMIN_ID = int(os.getenv('ADMIN_ID'))
WEBSITE_URL = "https://dramawallah.netlify.app"

# Conversation states
WAITING_CHANNEL_LINK, WAITING_POSTER_IMAGE, WAITING_DRAMA_FILES = range(3)
WAITING_NEWS_TITLE, WAITING_NEWS_CONTENT, WAITING_NEWS_IMAGE = range(3, 6)
WAITING_CHANNEL_ID = range(6, 7)

# Clean filename function
def clean_filename(filename):
    patterns_to_remove = [
        r'\[.*?\]', r'\(.*?\)', r'\{.*?\}',
        r'[0-9]{4}', r'S[0-9]+E[0-9]+', 
        r'Season[\.\s]*[0-9]+', r'Episode[\.\s]*[0-9]+',
        r'x264', r'x265', r'HEVC', r'WEBRip', r'BluRay',
        r'[0-9]+p', r'480p', r'720p', r'1080p', r'2160p',
        r'\s+',
    ]
    
    cleaned = filename
    for pattern in patterns_to_remove:
        cleaned = re.sub(pattern, ' ', cleaned, flags=re.IGNORECASE)
    
    cleaned = re.sub(r'[^\w\s]', '', cleaned)
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()
    cleaned = cleaned.title()
    
    return cleaned

# Generate shortener link
def generate_shortener_link(destination_url):
    return f"http://ouo.io/qs/tmqxi7by?s={destination_url}"

# Start command
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    
    users_collection.update_one(
        {'user_id': user.id},
        {'$set': {
            'username': user.username,
            'first_name': user.first_name,
            'last_seen': datetime.now()
        }},
        upsert=True
    )
    
    welcome_text = """
🎬 *welcome to dramawallah bot*

*available commands:*
/search_drama - search for dramas

*for admins:*
/add - add new drama
/ongoing - manage ongoing dramas  
/add_news - post news
/broadcast - message all users

developed by @bibegs
    """.lower()

    await update.message.reply_text(welcome_text, parse_mode='Markdown')

# Add drama command
async def add_drama(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.from_user.id != ADMIN_ID:
        await update.message.reply_text("this command is for admins only.")
        return ConversationHandler.END
    
    await update.message.reply_text("send me the private channel link:")
    return WAITING_CHANNEL_LINK

async def handle_channel_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['channel_link'] = update.message.text
    await update.message.reply_text("now send the poster image:")
    return WAITING_POSTER_IMAGE

async def handle_poster_image(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.photo:
        photo_file = await update.message.photo[-1].get_file()
        image_url = photo_file.file_path
        
        context.user_data['poster_image'] = image_url
        await update.message.reply_text("now send the drama files (you can send multiple):")
        return WAITING_DRAMA_FILES
    else:
        await update.message.reply_text("please send an image.")
        return WAITING_POSTER_IMAGE

async def handle_drama_files(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.document or update.message.video:
        file_obj = update.message.document or update.message.video
        file_name = clean_filename(file_obj.file_name)
        
        if 'files' not in context.user_data:
            context.user_data['files'] = []
        
        context.user_data['files'].append({
            'file_id': file_obj.file_id,
            'file_name': file_name,
            'file_size': file_obj.file_size
        })
        
        await update.message.reply_text(f"added: {file_name}\nsend more files or type /done to finish")
        return WAITING_DRAMA_FILES
    
    elif update.message.text == '/done' and context.user_data.get('files'):
        drama_name = clean_filename(context.user_data['files'][0]['file_name'].split('.')[0])
        
        drama_data = {
            'name': drama_name,
            'channel_link': context.user_data['channel_link'],
            'poster_image': context.user_data['poster_image'],
            'files': context.user_data['files'],
            'created_at': datetime.now(),
            'type': 'drama'
        }
        
        dramas_collection.insert_one(drama_data)
        
        await update.message.reply_text(f"✅ drama '{drama_name}' added successfully!\nchannel: {context.user_data['channel_link']}")
        
        context.user_data.clear()
        return ConversationHandler.END

    else:
        await update.message.reply_text("please send files or type /done to finish")
        return WAITING_DRAMA_FILES

# Ongoing drama command
async def ongoing_drama(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.from_user.id != ADMIN_ID:
        await update.message.reply_text("this command is for admins only.")
        return ConversationHandler.END
    
    await update.message.reply_text("send me the ongoing drama channel link:")
    return WAITING_CHANNEL_LINK

async def handle_ongoing_channel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['channel_link'] = update.message.text
    await update.message.reply_text("now send the poster image for ongoing drama:")
    return WAITING_POSTER_IMAGE

async def handle_ongoing_files(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.document or update.message.video:
        file_obj = update.message.document or update.message.video
        file_name = clean_filename(file_obj.file_name)
        
        if 'files' not in context.user_data:
            context.user_data['files'] = []
        
        context.user_data['files'].append({
            'file_id': file_obj.file_id,
            'file_name': file_name,
            'file_size': file_obj.file_size
        })
        
        await update.message.reply_text(f"added: {file_name}\nsend more files or type /done to finish")
        return WAITING_DRAMA_FILES
    
    elif update.message.text == '/done' and context.user_data.get('files'):
        drama_name = clean_filename(context.user_data['files'][0]['file_name'].split('.')[0])
        
        drama_data = {
            'name': drama_name,
            'channel_link': context.user_data['channel_link'],
            'poster_image': context.user_data['poster_image'],
            'files': context.user_data['files'],
            'created_at': datetime.now(),
            'type': 'ongoing'
        }
        
        dramas_collection.insert_one(drama_data)
        
        await update.message.reply_text(f"✅ ongoing drama '{drama_name}' added successfully!")
        
        context.user_data.clear()
        return ConversationHandler.END

# Search drama in PM
async def search_drama_pm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[InlineKeyboardButton("🔍 search on website", url=WEBSITE_URL)]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "click below to search dramas on our website:".lower(),
        reply_markup=reply_markup
    )

# Group search handler
async def handle_group_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.chat.type in ['group', 'supergroup']:
        search_text = update.message.text.lower().strip()
        
        if len(search_text) < 3:
            return
        
        drama = dramas_collection.find_one({
            'name': {'$regex': search_text, '$options': 'i'}
        })
        
        if drama:
            keyboard = [[InlineKeyboardButton(f"📥 {drama['name']}", url=drama['channel_link'])]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            response = await update.message.reply_text(
                f"found: {drama['name']}".lower(),
                reply_markup=reply_markup
            )
            
            # Delete after 2 minutes
            await context.job_queue.run_once(
                delete_message, 
                120, 
                data={'chat_id': update.message.chat_id, 'message_id': response.message_id}
            )

async def delete_message(context: ContextTypes.DEFAULT_TYPE):
    job_data = context.job.data
    try:
        await context.bot.delete_message(
            chat_id=job_data['chat_id'],
            message_id=job_data['message_id']
        )
    except:
        pass

# Add news command
async def add_news(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.from_user.id != ADMIN_ID:
        await update.message.reply_text("this command is for admins only.")
        return ConversationHandler.END
    
    await update.message.reply_text("send news title:")
    return WAITING_NEWS_TITLE

async def handle_news_title(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['news_title'] = update.message.text
    await update.message.reply_text("send news content:")
    return WAITING_NEWS_CONTENT

async def handle_news_content(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['news_content'] = update.message.text
    await update.message.reply_text("send news image or type /skip:")
    return WAITING_NEWS_IMAGE

async def handle_news_image(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.photo:
        photo_file = await update.message.photo[-1].get_file()
        image_url = photo_file.file_path
        context.user_data['news_image'] = image_url
    else:
        context.user_data['news_image'] = None
    
    news_data = {
        'title': context.user_data['news_title'],
        'content': context.user_data['news_content'],
        'image': context.user_data['news_image'],
        'created_at': datetime.now()
    }
    
    news_collection.insert_one(news_data)
    
    await update.message.reply_text("✅ news posted successfully!")
    context.user_data.clear()
    return ConversationHandler.END

# Broadcast command
async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.from_user.id != ADMIN_ID:
        await update.message.reply_text("this command is for admins only.")
        return
    
    if update.message.reply_to_message:
        users = users_collection.find()
        sent = 0
        
        for user in users:
            try:
                await update.message.reply_to_message.copy(user['user_id'])
                sent += 1
            except:
                continue
        
        await update.message.reply_text(f"broadcast sent to {sent} users.")
    else:
        await update.message.reply_text("please reply to a message to broadcast.")

# Force subscription
async def fs_on(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.from_user.id != ADMIN_ID:
        await update.message.reply_text("this command is for admins only.")
        return ConversationHandler.END
    
    await update.message.reply_text("send channel id to force subscribe:")
    return WAITING_CHANNEL_ID

async def handle_channel_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    force_sub_collection.update_one(
        {'_id': 'force_sub'},
        {'$set': {'channel_id': update.message.text}},
        upsert=True
    )
    
    await update.message.reply_text("✅ force subscription enabled!")
    return ConversationHandler.END

async def fs_off(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.from_user.id != ADMIN_ID:
        await update.message.reply_text("this command is for admins only.")
        return
    
    force_sub_collection.delete_one({'_id': 'force_sub'})
    await update.message.reply_text("✅ force subscription disabled!")

async def fs_dlt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.from_user.id != ADMIN_ID:
        await update.message.reply_text("this command is for admins only.")
        return
    
    keyboard = [[InlineKeyboardButton("❌ delete force sub", callback_data="delete_force_sub")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("click to delete force subscription:", reply_markup=reply_markup)

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data == "delete_force_sub":
        force_sub_collection.delete_one({'_id': 'force_sub'})
        await query.edit_message_text("✅ force subscription deleted!")

# Remove command
async def remove_drama(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.from_user.id != ADMIN_ID:
        await update.message.reply_text("this command is for admins only.")
        return
    
    dramas = list(dramas_collection.find({}, {'name': 1}))
    
    if not dramas:
        await update.message.reply_text("no dramas found.")
        return
    
    keyboard = []
    for drama in dramas:
        keyboard.append([InlineKeyboardButton(f"❌ {drama['name']}", callback_data=f"remove_{drama['_id']}")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("select drama to remove:", reply_markup=reply_markup)

async def remove_button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data.startswith("remove_"):
        drama_id = query.data.split("_")[1]
        
        dramas_collection.delete_one({'_id': drama_id})
        await query.edit_message_text("✅ drama removed successfully!")

def run_flask():
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)

def main():
    # Setup logging
    logging.basicConfig(
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        level=logging.INFO
    )
    
    # Create bot application
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Add handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("search_drama", search_drama_pm))
    application.add_handler(CommandHandler("broadcast", broadcast))
    application.add_handler(CommandHandler("fs_off", fs_off))
    application.add_handler(CommandHandler("fs_dlt", fs_dlt))
    application.add_handler(CommandHandler("remove", remove_drama))
    
    # Conversation handlers
    add_handler = ConversationHandler(
        entry_points=[CommandHandler("add", add_drama)],
        states={
            WAITING_CHANNEL_LINK: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_channel_link)],
            WAITING_POSTER_IMAGE: [MessageHandler(filters.PHOTO, handle_poster_image)],
            WAITING_DRAMA_FILES: [MessageHandler(filters.DOCUMENT | filters.VIDEO | filters.TEXT, handle_drama_files)],
        },
        fallbacks=[CommandHandler("cancel", lambda u, c: ConversationHandler.END)]
    )
    
    ongoing_handler = ConversationHandler(
        entry_points=[CommandHandler("ongoing", ongoing_drama)],
        states={
            WAITING_CHANNEL_LINK: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_ongoing_channel)],
            WAITING_POSTER_IMAGE: [MessageHandler(filters.PHOTO, handle_poster_image)],
            WAITING_DRAMA_FILES: [MessageHandler(filters.DOCUMENT | filters.VIDEO | filters.TEXT, handle_ongoing_files)],
        },
        fallbacks=[CommandHandler("cancel", lambda u, c: ConversationHandler.END)]
    )
    
    news_handler = ConversationHandler(
        entry_points=[CommandHandler("add_news", add_news)],
        states={
            WAITING_NEWS_TITLE: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_news_title)],
            WAITING_NEWS_CONTENT: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_news_content)],
            WAITING_NEWS_IMAGE: [MessageHandler(filters.PHOTO | filters.TEXT, handle_news_image)],
        },
        fallbacks=[CommandHandler("cancel", lambda u, c: ConversationHandler.END)]
    )
    
    fs_handler = ConversationHandler(
        entry_points=[CommandHandler("fs_on", fs_on)],
        states={
            WAITING_CHANNEL_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_channel_id)],
        },
        fallbacks=[CommandHandler("cancel", lambda u, c: ConversationHandler.END)]
    )
    
    application.add_handler(add_handler)
    application.add_handler(ongoing_handler)
    application.add_handler(news_handler)
    application.add_handler(fs_handler)
    
    # Group message handler
    application.add_handler(MessageHandler(filters.TEXT & filters.ChatType.GROUPS, handle_group_message))
    
    # Callback handlers
    application.add_handler(CallbackQueryHandler(button_handler, pattern="^delete_force_sub$"))
    application.add_handler(CallbackQueryHandler(remove_button_handler, pattern="^remove_"))
    
    # Start Flask in separate thread
    flask_thread = threading.Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()
    
    logging.info("🚀 starting bot...")
    application.run_polling()

if __name__ == '__main__':
    main()
