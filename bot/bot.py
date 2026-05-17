import logging
import asyncio
import os
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler
import config
from database import db
from single import handle_movie_search, handle_movie_channel_post
from series import handle_series_search, handle_series_channel_post
from all_film import handle_all_film_search
from admin import admin_panel
from payment import payment_system
from referral import referral_system
from help import handle_usage_command, handle_usage_callbacks, help_command
from user_block import user_block_system # Import the user_block_system

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# User states
USER_STATES = {}
WAITING_FOR_CONTACT = "waiting_for_contact"
WAITING_FOR_MOVIE_SEARCH = "waiting_for_movie_search"
WAITING_FOR_SERIES_SEARCH = "waiting_for_series_search"
WAITING_FOR_ALL_SEARCH = "waiting_for_all_search"
ADMIN_SETTING_SINGLE_CHANNEL = "admin_setting_single_channel"
ADMIN_SETTING_SERIES_CHANNEL = "admin_setting_series_channel"

# Reply Keyboard - built at import time using runtime env
def _build_keyboard():
    _domain = os.environ.get("REPLIT_DEV_DOMAIN", "")
    _url = f"https://{_domain}/webapp/" if _domain else None
    row_films = [KeyboardButton("ተከታታይ ፊልም 📽"), KeyboardButton("ነጠላ ፊልም 🎬")]
    row_all = [KeyboardButton("🎞 ሁሉንም ፊልም")]
    if _url:
        row_all.append(KeyboardButton("📱 Mini App", web_app=WebAppInfo(url=_url)))
    return ReplyKeyboardMarkup([
        row_films,
        row_all,
        [KeyboardButton("ቀር ሂሳብ 💰"), KeyboardButton("ገቢ ለማድረግ 🏦")],
        [KeyboardButton("ለመጋበዝ 🎁"), KeyboardButton("⚙️ አጠቃቀም")]
    ], resize_keyboard=True)

_MAIN_KEYBOARD = _build_keyboard()

def get_main_keyboard():
    return _MAIN_KEYBOARD

def _is_streamable(file_name: str) -> bool:
    """Returns True if the file can be played inline by Telegram (no download needed)."""
    ext = (file_name or "").lower().rsplit(".", 1)[-1]
    return ext in {"mp4", "m4v", "mov"}


async def send_film(bot, chat_id: int, file_id: str, file_name: str):
    """Send film as video (inline playback) for MP4/M4V, or as document for other formats."""
    if _is_streamable(file_name):
        try:
            await bot.send_video(
                chat_id=chat_id,
                video=file_id,
                supports_streaming=True,
            )
            return
        except Exception:
            pass
    await bot.send_document(chat_id=chat_id, document=file_id)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command"""
    user = update.effective_user

    # Check if user is blocked
    if user_block_system.is_user_blocked(user.id):
        await update.message.reply_text(
            "🚫 **የተገደበ ተጠቃሚ**\n\n"
            "እርስዎ ከBot አገልግሎት ተገደብተዋል።\n"
            "ለበለጠ መረጃ [Admin](https://t.me/Henok_Chat) ን ያነጋግሩ።",
            parse_mode='Markdown'
        )
        return

    referrer_id = None
    if context.args and len(context.args) > 0:
        arg = context.args[0]
        if arg.startswith('invite_'):
            try:
                referrer_id = int(arg.replace('invite_', ''))
                context.user_data['pending_referrer'] = referrer_id
            except ValueError:
                logger.warning(f"Invalid referral code: {arg}")

    if not db.user_exists(user.id):
        # New user - request contact
        keyboard = [[KeyboardButton("Contact መጋራት 📱", request_contact=True)]]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)

        await update.message.reply_text(
            f"እንኳን ደህና መጡ {user.first_name}! 👋\n\n"
            "የ ET Films Story Bot 🎥 ተጠቃሚ ለመሆን፣ እባክዎ Contact ይጋሩ።",
            reply_markup=reply_markup
        )
        USER_STATES[user.id] = WAITING_FOR_CONTACT
    else:
        # Clear search state
        USER_STATES.pop(user.id, None)

        # Clear search results from context
        if 'last_movie_results' in context.user_data:
            del context.user_data['last_movie_results']
        if 'last_series_results' in context.user_data:
            del context.user_data['last_series_results']
        if 'last_all_results' in context.user_data:
            del context.user_data['last_all_results']
        if 'movie_search_query' in context.user_data:
            del context.user_data['movie_search_query']
        if 'series_search_query' in context.user_data:
            del context.user_data['series_search_query']
        if 'all_search_query' in context.user_data:
            del context.user_data['all_search_query']

        # Existing user
        await update.message.reply_text(
            f"⚪️ እንደገና እንኳን ደህና መጡ! {user.first_name}\n\n"
            "☢️ እባክዎ የምትፈልገው ነገር ከታች ይምረጡ።👇",
            reply_markup=get_main_keyboard()
        )

async def handle_contact(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle contact sharing"""
    if update.message.contact:
        user = update.effective_user
        contact = update.message.contact

        # Check if user is blocked before adding
        if user_block_system.is_user_blocked(user.id):
            await update.message.reply_text(
                "🚫 **የተገደበ ተጠቃሚ**\n\n"
                "እርስዎ ከBot አገልግሎት ተገደብተዋል።\n"
                "ለበለጠ መረጃ [Admin](https://t.me/Henok_Chat) ን ያነጋግሩ።",
                parse_mode='Markdown'
            )
            return

        # Save user to database
        db.add_user(
            user_id=user.id,
            username=user.username,
            phone_number=contact.phone_number,
            first_name=user.first_name,
            last_name=user.last_name
        )

        # Add welcome bonus to new user
        import sqlite3
        with sqlite3.connect(config.USER_DB_PATH) as conn:
            conn.execute(
                'UPDATE users SET balance = balance + ? WHERE user_id = ?',
                (config.WELCOME_BONUS, user.id)
            )
            conn.commit()

        pending_referrer = context.user_data.get('pending_referrer')
        if pending_referrer:
            await referral_system.process_referral(user.id, pending_referrer, context)
            context.user_data.pop('pending_referrer', None)

        await update.message.reply_text(
            f"✅ መመዝገብዎ ተሳክቷል!\n"
            f"🎁 የ{config.WELCOME_BONUS} ብር Welcome Bonus አግኝተዋል!\n\n"
            "እንኳን ወደ ET Films Story Bot 🎥 በደህና መጡ!\n\n"
            f"💰 የአሁን ቀሪ ሂሳብዎ: {config.WELCOME_BONUS} ብር\n"
            "🎬 እስከ 2 ፊልሞች ድረስ ነፃ ይመልከቱ!\n\n"
            "━━━━━━━━━━━━━━━━━━━\n\n"
            "🌍 ከየትኛው ሀገር ፊልም ብትፈልግ ይገኛል!\n"
            "🎬 Hollywood • Bollywood • Korean\n"
            "🇪🇹 Ethiopian • Turkish • Egyptian\n"
            "🌍 African • European • Chinese... እና ሌሎች!\n\n"
            "🎭 ማንኛውም የፊልም ዓይነት!\n"
            "⚔️ Action • 😂 Comedy • ❤️ Romance\n"
            "👻 Horror • 🚀 Sci-Fi • 🦸 Superhero\n"
            "🎨 Animation • 📚 Documentary... እና ሌሎች!\n\n"
            "✅ በአማርኛ ትርጉም እና ያለትርጉም በሁለቱም!\n\n"
            "━━━━━━━━━━━━━━━━━━━\n\n"
            "💡 እንዴት እንደሚሠራ:\n\n"
            "1️⃣ ከታች የሚፈልጉትን ይምረጡ:\n"
            "   📽 ተከታታይ ፊልም (2 ብር)\n"
            "   🎬 ነጠላ ፊልም (3 ብር)\n"
            "   🎞 ሁሉንም ፊልም (ሁሉንም አንድላይ ይፈልጉ)\n\n"
            "2️⃣ የፊልም ስም ይፃፉ እና ይፈልጉ\n\n"
            "3️⃣ ፊልሙን ይግዙ - በቀጥታ ይደርስዎታል!\n\n"
            "━━━━━━━━━━━━━━━━━━━\n\n"
            "💰 ተጨማሪ አገልግሎቶች:\n"
            "• 💵 ቀሪ ሂሳብ - ሂሳብዎን ይመልከቱ\n"
            "• 🏦 ገቢ ለማድረግ - ገንዘብ ግቢ ያድርጉ\n"
            "• 🎁 ለመጋበዝ - ጓደኞችን ጋብዙ (በእንድ ሰው 2 ብር ያግኙ)\n\n"
            "📱 ለእገዛ: ⚙️ አጠቃቀም ይጫኑ\n\n"
            "እንደሚያስደስት ተስፋ እናደርጋለን! 🍿✨",
            reply_markup=get_main_keyboard()
        )

        if user.id in USER_STATES:
            del USER_STATES[user.id]

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle incoming messages"""
    # Update bot status timestamp
    import time
    if 'bot_status' in globals():
        globals()['bot_status']['last_update'] = time.time()
        globals()['bot_status']['running'] = True
    
    user = update.effective_user
    text = update.message.text

    # Check if user is blocked
    if user_block_system.is_user_blocked(user.id):
        await update.message.reply_text(
            "🚫 **የተገደበ ተጠቃሚ**\n\n"
            "እርስዎ ከBot አገልግሎት ተገደብተዋል።\n"
            "ለበለጠ መረጃ [Admin](https://t.me/Henok_Chat) ን ያነጋግሩ።",
            parse_mode='Markdown'
        )
        return

    # Delete the usage message if it exists
    if 'usage_message_id' in context.user_data:
        try:
            await context.bot.delete_message(
                chat_id=update.effective_chat.id,
                message_id=context.user_data['usage_message_id']
            )
        except Exception as e:
            logger.info(f"Could not delete usage message: {e}")
        finally:
            del context.user_data['usage_message_id']

    # Periodic cleanup of old search results to prevent memory leaks
    if 'last_cleanup' not in context.user_data:
        context.user_data['last_cleanup'] = 0

    import time
    current_time = time.time()
    if current_time - context.user_data.get('last_cleanup', 0) > 3600:  # Every hour
        # Clear old search results
        for key in ['last_movie_results', 'last_series_results', 'last_all_results',
                    'movie_search_query', 'series_search_query', 'all_search_query']:
            if key in context.user_data:
                del context.user_data[key]
        # Clear stale user state to prevent memory leak
        USER_STATES.pop(user.id, None)
        context.user_data['last_cleanup'] = current_time

    # Check if user is registered
    if not db.user_exists(user.id) and user.id not in USER_STATES:
        await start(update, context)
        return

    # Handle admin messages
    if user.id == config.ADMIN_USER_ID:
        import asyncio
        from admin_balance import admin_balance
        async def handle_admin_isolated():
            try:
                await admin_panel.handle_admin_message(update, context)
                await admin_balance.handle_admin_message(update, context)
            except Exception as e:
                logger.error(f"Admin message handling error: {e}")

        asyncio.create_task(handle_admin_isolated())

    # Clean up any existing inline keyboards when user sends new message
    if user.id in context.user_data.get('last_inline_messages', {}):
        last_message_ids = context.user_data['last_inline_messages'][user.id]
        for message_id in last_message_ids:
            try:
                await context.bot.delete_message(
                    chat_id=update.message.chat.id,
                    message_id=message_id
                )
            except Exception as e:
                logger.error(f"Error deleting previous inline message: {e}")
        # Clear the tracked messages
        del context.user_data['last_inline_messages'][user.id]

    # Handle back button first - clear ALL related states
    if text == "⬅️ ለመመለስ":
        # Clear user state
        USER_STATES.pop(user.id, None)

        # Clear search results from context
        if 'last_movie_results' in context.user_data:
            del context.user_data['last_movie_results']
        if 'last_series_results' in context.user_data:
            del context.user_data['last_series_results']
        if 'movie_search_query' in context.user_data:
            del context.user_data['movie_search_query']
        if 'series_search_query' in context.user_data:
            del context.user_data['series_search_query']

        # Clear any tracked inline messages
        if 'last_inline_messages' in context.user_data and user.id in context.user_data['last_inline_messages']:
            del context.user_data['last_inline_messages'][user.id]

        await update.message.reply_text(
            "ዋና ምናሌ 🏠",
            reply_markup=get_main_keyboard()
        )
        return

    # Handle keyboard buttons BEFORE checking user states
    if text == "ነጠላ ፊልም 🎬":
        # Create back button keyboard
        back_keyboard = [[KeyboardButton("⬅️ ለመመለስ")]]
        back_reply_markup = ReplyKeyboardMarkup(back_keyboard, resize_keyboard=True)

        await update.message.reply_text(
            "የምፈልጉትን ነጠላ ፊልም ስም ይጻፉ:",
            reply_markup=back_reply_markup
        )
        USER_STATES[user.id] = WAITING_FOR_MOVIE_SEARCH

    elif text == "ተከታታይ ፊልም 📽":
        # Create back button keyboard
        back_keyboard = [[KeyboardButton("⬅️ ለመመለስ")]]
        back_reply_markup = ReplyKeyboardMarkup(back_keyboard, resize_keyboard=True)

        await update.message.reply_text(
            "የምፈልጉትን ተከታታይ ፊልም ስም ይጻፉ:",
            reply_markup=back_reply_markup
        )
        USER_STATES[user.id] = WAITING_FOR_SERIES_SEARCH

    elif text == "🎞 ሁሉንም ፊልም":
        # Create back button keyboard
        back_keyboard = [[KeyboardButton("⬅️ ለመመለስ")]]
        back_reply_markup = ReplyKeyboardMarkup(back_keyboard, resize_keyboard=True)

        await update.message.reply_text(
            "የምፈልጉትን ፊልም ስም ይጻፉ (ነጠላ ወይም ተከታታይ):",
            reply_markup=back_reply_markup
        )
        USER_STATES[user.id] = WAITING_FOR_ALL_SEARCH

    elif text == "ቀር ሂሳብ 💰":
        # Show balance display
        try:
            # Get user balance from database
            user_balance = db.get_user_balance(user.id)

            # Convert to integer safely
            if user_balance is None:
                balance_amount = 0
            else:
                try:
                    balance_amount = int(float(user_balance))
                except (ValueError, TypeError):
                    logger.error(f"Invalid balance value for user {user.id}: {user_balance}")
                    balance_amount = 0

            await update.message.reply_text(
                f"💰 የእርስዎ ሒሳብ መጠን\n\n"
                f"💵 ያለዎት ገንዘብ: {balance_amount:,} ብር\n\n"
                f"💡 ገንዘብ ለመጨመር 'ገቢ ለማድረግ 🏦' ይጫኑ",
                reply_markup=get_main_keyboard()
            )
            logger.info(f"Balance displayed for user {user.id}: {balance_amount} ብር")

        except Exception as e:
            logger.error(f"Error showing balance for user {user.id}: {e}", exc_info=True)
            await update.message.reply_text(
                f"💰 የእርስዎ ሒሳብ መጠን\n\n"
                f"💵 ያለዎት ገንዘብ: 0 ብር\n\n"
                f"💡 ገንዘብ ለመጨመር 'ገቢ ለማድረግ 🏦' ይጫኑ\n\n"
                f"⚠️ የሒሳብ መረጃ ለማግኘት ችግር ተፈጥሯል። እባክዎ እንደገና ይሞክሩ።",
                reply_markup=get_main_keyboard()
            )

    elif text == "ገቢ ለማድረግ 🏦":
        await payment_system.show_payment_menu(update, context)

    elif text == "ለመጋበዝ 🎁":
        await referral_system.show_referral_info(update, context)

    elif text == "⚙️ አጠቃቀም":
        await handle_usage_command(update, context)

    # Payment method handling
    elif text in ["📱 Telebirr", "🏦 CBE", "🌐 CBEbirr", "💳 Card"]:
        method_map = {
            "📱 Telebirr": "Telebirr",
            "🏦 CBE": "CBE", 
            "🌐 CBEbirr": "CBEbirr",
            "💳 Card": "Card"
        }
        await payment_system.process_payment_method(update, context, method_map[text])

    # Payment confirmation handling
    elif text == "✅ አረጋግጥ":
        await payment_system.confirm_payment(update, context)

    # Payment back button handling in screenshot step
    elif text == "↩️ ለመመለስ":
        # Check if user is in payment session first
        session = payment_system.payment_sessions.get(user.id)
        if session:
            if session['step'] == 'screenshot':
                # Special handling for screenshot step
                if await payment_system.handle_back_in_screenshot(update, context):
                    return
            else:
                # Clear payment session and return to main menu
                del payment_system.payment_sessions[user.id]
                await update.message.reply_text(
                    "ዋና ምናሌ 🏠",
                    reply_markup=get_main_keyboard()
                )
                return

        # If not in payment session, handle normally
        await update.message.reply_text(
            "ዋና ምናሌ 🏠",
            reply_markup=get_main_keyboard()
        )

    # Admin commands
    elif text == "/henok" and user.id == config.ADMIN_USER_ID:
        await admin_panel.show_admin_panel(update, context)

    # Handle user states for search
    elif user.id in USER_STATES:
        state = USER_STATES[user.id]

        # Check for search query length
        if state in [WAITING_FOR_MOVIE_SEARCH, WAITING_FOR_SERIES_SEARCH, WAITING_FOR_ALL_SEARCH]:
            if len(text) < 3:
                await update.message.reply_text("❌ የፊልም ስም ቢያንስ 3 ፊደላት መሆን አለበት። እባክዎ እንደገና አስተካክለው ይጻፉ 🙏")
                return # Stop further processing
            if len(text) > 60:
                await update.message.reply_text("❌ የፊልም ስም ከ60 ፊደላት መብለጥ የለበትም። እባክዎ እንደገና አስተካክለው ይጻፉ 🙏")
                return # Stop further processing

        if state == WAITING_FOR_MOVIE_SEARCH:
            await handle_movie_search(update, context, text)
            # Don't delete state - keep it active for continuous searching
            return

        elif state == WAITING_FOR_SERIES_SEARCH:
            await handle_series_search(update, context, text)
            # Don't delete state - keep it active for continuous searching
            return

        elif state == WAITING_FOR_ALL_SEARCH:
            await handle_all_film_search(update, context, text)
            # Don't delete state - keep it active for continuous searching
            return

    # Payment input handling
    else:
        # Check if user is in payment session
        session = payment_system.payment_sessions.get(user.id)
        if session:
            current_step = session['step']

            if current_step == 'phone':
                await payment_system.process_input(update, context, 'phone', text)
            elif current_step == 'account':
                await payment_system.process_input(update, context, 'account', text)
            elif current_step == 'name':
                await payment_system.process_input(update, context, 'name', text)
            elif current_step == 'amount':
                await payment_system.process_input(update, context, 'amount', text)
            elif current_step == 'screenshot':
                # Reject text/number input on screenshot step
                await update.message.reply_text(
                    "❌ Text መላክ አይቻልም!\n\n📸 የክፍያ Screenshot (Photo) ብቻ ይላኩ"
                )

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle photo uploads for payment screenshots"""
    user_id = update.effective_user.id

    # Check if user is blocked
    if user_block_system.is_user_blocked(user_id):
        await update.message.reply_text(
            "🚫 **የተገደበ ተጠቃሚ**\n\n"
            "እርስዎ ከBot አገልግሎት ተገደብተዋል።\n"
            "ለበለጠ መረጃ [Admin](https://t.me/Henok_Chat) ን ያነጋግሩ።",
            parse_mode='Markdown'
        )
        return

    # Check if user is in payment session and expecting screenshot
    session = payment_system.payment_sessions.get(user_id)
    if session and session['step'] == 'screenshot':
        await payment_system.process_screenshot(update, context)
    else:
        # Not expecting photo, ignore or give guidance
        await update.message.reply_text("📸 ምንም የፎቶ አገልግሎት አልጠበቅኩም። እባክዎ ዋናውን ምናሌ ይጠቀሙ።")

async def handle_admin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle admin panel callbacks"""
    query = update.callback_query
    data = query.data
    user_id = query.from_user.id

    # Check if user is blocked
    if user_block_system.is_user_blocked(user_id):
        await query.answer("🚫 እርስዎ ተገድበዋል።", show_alert=True)
        return

    # Handle search again buttons
    if data == "search_again_movie":
        await query.answer()
        await query.message.delete()
        from telegram import ReplyKeyboardMarkup, KeyboardButton
        back_keyboard = [[KeyboardButton("⬅️ ለመመለስ")]]
        back_reply_markup = ReplyKeyboardMarkup(back_keyboard, resize_keyboard=True)
        await context.bot.send_message(
            chat_id=query.message.chat.id,
            text="የምፈልጉትን ነጠላ ፊልም ስም ይጻፉ:",
            reply_markup=back_reply_markup
        )
        USER_STATES[user_id] = WAITING_FOR_MOVIE_SEARCH
        return
    
    elif data == "search_again_series":
        await query.answer()
        await query.message.delete()
        from telegram import ReplyKeyboardMarkup, KeyboardButton
        back_keyboard = [[KeyboardButton("⬅️ ለመመለስ")]]
        back_reply_markup = ReplyKeyboardMarkup(back_keyboard, resize_keyboard=True)
        await context.bot.send_message(
            chat_id=query.message.chat.id,
            text="የምፈልጉትን ተከታታይ ፊልም ስም ይጻፉ:",
            reply_markup=back_reply_markup
        )
        USER_STATES[user_id] = WAITING_FOR_SERIES_SEARCH
        return
    
    elif data == "search_again_all":
        await query.answer()
        await query.message.delete()
        from telegram import ReplyKeyboardMarkup, KeyboardButton
        back_keyboard = [[KeyboardButton("⬅️ ለመመለስ")]]
        back_reply_markup = ReplyKeyboardMarkup(back_keyboard, resize_keyboard=True)
        await context.bot.send_message(
            chat_id=query.message.chat.id,
            text="የምፈልጉትን ፊልም ስም ይጻፉ (ነጠላ ወይም ተከታታይ):",
            reply_markup=back_reply_markup
        )
        USER_STATES[user_id] = WAITING_FOR_ALL_SEARCH
        return
    
    elif data == "go_home":
        await query.answer()
        await query.message.delete()
        USER_STATES.pop(user_id, None)
        await context.bot.send_message(
            chat_id=query.message.chat.id,
            text="🏠 ዋና ምናሌ",
            reply_markup=get_main_keyboard()
        )
        return

    # Handle all films pagination
    if data.startswith("all_prev_") or data.startswith("all_next_"):
        from telegram import InlineKeyboardMarkup, InlineKeyboardButton
        try:
            if data.startswith("all_prev_"):
                page = int(data.replace("all_prev_", ""))
            else:  # all_next_
                page = int(data.replace("all_next_", ""))

            search_query = context.user_data.get('all_search_query', '')
            all_results = context.user_data.get('last_all_results', [])

            if not all_results:
                await query.answer("❌ የፍለጋ ውጤት ጊዜው አልፏል!", show_alert=True)
                try:
                    await query.message.delete()
                except Exception as e:
                    logger.error(f"Error deleting expired message: {e}")
                return

            # Pagination settings
            per_page = 5
            total_pages = (len(all_results) + per_page - 1) // per_page

            # Get current page results
            start_idx = page * per_page
            end_idx = start_idx + per_page
            current_page_results = all_results[start_idx:end_idx]

            # Create inline keyboard
            keyboard = []
            for i, (file_id, file_name, file_title, film_type) in enumerate(current_page_results):
                display_name = file_name if file_name else (file_title if file_title else f"ፋይል {start_idx + i + 1}")
                display_title = display_name[:45] + "..." if len(display_name) > 45 else display_name
                emoji = "🎬" if film_type == "movie" else "📽"
                keyboard.append([InlineKeyboardButton(
                    f"{emoji} {display_title}", 
                    callback_data=f"all_{film_type}_{start_idx + i}"
                )])

            # Add pagination buttons
            pagination_row = []
            if page > 0:
                pagination_row.append(InlineKeyboardButton("⬅️ ቀድሞ", callback_data=f"all_prev_{page-1}"))
            if page < total_pages - 1:
                pagination_row.append(InlineKeyboardButton("ቀጣይ ➡️", callback_data=f"all_next_{page+1}"))

            if pagination_row:
                keyboard.append(pagination_row)

            # Always add search and home buttons
            keyboard.append([
                InlineKeyboardButton("🔍 ሌላ ለመፈለግ", callback_data="search_again_all"),
                InlineKeyboardButton("🏠 Home", callback_data="go_home")
            ])

            reply_markup = InlineKeyboardMarkup(keyboard)
            page_info = f"📄 ገጽ {page + 1}/{total_pages}" if total_pages > 1 else ""

            await query.edit_message_text(
                text=f"🔍 የፈለጉት '{search_query}'\n\n"
                     f"{page_info}\n"
                     "⬇️ የሚፈልጉትን ፊልም ይምረጡ:",
                reply_markup=reply_markup
            )
            await query.answer()
        except Exception as e:
            logger.error(f"All films pagination error: {e}")
            await query.answer("❌ ስህተት ተፈጥሯል!", show_alert=True)
        return

    # Handle all films file sending
    elif data.startswith("all_movie_") or data.startswith("all_series_"):
        try:
            # Parse callback data
            parts = data.split("_")
            film_type = parts[1]  # "movie" or "series"
            index = int(parts[2])

            # Check if user is blocked
            if user_block_system.is_user_blocked(user_id):
                await query.answer("🚫 እርስዎ ተገድበዋል።", show_alert=True)
                return

            # Get the last search results from context
            if 'last_all_results' in context.user_data:
                results = context.user_data['last_all_results']
                if 0 <= index < len(results):
                    file_id = results[index][0]
                    file_name = results[index][1]

                    # Check user balance
                    PRICE = 3 if film_type == "movie" else 2
                    user_balance = db.get_user_balance(user_id)

                    if user_balance < PRICE:
                        await query.answer(
                            f"❌ በቂ ሂሳብ የለዎትም!\n\n"
                            f"💰 ያለዎት: {user_balance} ብር\n"
                            f"💵 የሚያስፈልግ: {PRICE} ብር\n\n"
                            f"እባክዎ ገቢ ያድርጉ! 🏦",
                            show_alert=True
                        )
                        return

                    # Deduct balance
                    import sqlite3
                    with sqlite3.connect(config.USER_DB_PATH) as conn:
                        conn.execute('UPDATE users SET balance = balance - ? WHERE user_id = ?', (PRICE, user_id))
                        conn.commit()

                    # Delete the inline keyboard message
                    try:
                        await query.message.delete()
                    except Exception as e:
                        logger.error(f"Error deleting inline keyboard message: {e}")

                    await send_film(context.bot, query.message.chat.id, file_id, file_name)

                    # Log download
                    db.log_download(user_id, file_id, film_type, file_name)

                    await query.answer(f"✅ {PRICE} ብር ተከፍሏል!")

                    # Clear user state and return to main menu
                    USER_STATES.pop(user_id, None)
                    await context.bot.send_message(
                        chat_id=query.message.chat.id,
                        text="🏠 ወደ ዋና ምናሌ ተመልሰዋል",
                        reply_markup=get_main_keyboard()
                    )
                else:
                    await query.answer("❌ ፊልም አልተገኘም!", show_alert=True)
                    try:
                        await query.message.delete()
                    except Exception as e:
                        logger.error(f"Error deleting expired message: {e}")
            else:
                await query.answer("❌ የፍለጋ ውጤት ጊዜው አልፏል!", show_alert=True)
                try:
                    await query.message.delete()
                except Exception as e:
                    logger.error(f"Error deleting expired message: {e}")
        except Exception as e:
            logger.error(f"Error sending all film file: {e}")
            await query.answer("❌ ፊልም መላክ አልተቻለም!", show_alert=True)
        return

    # Handle movie pagination
    if data.startswith("movie_prev_") or data.startswith("movie_next_"):
        from telegram import InlineKeyboardMarkup, InlineKeyboardButton
        try:
            if data.startswith("movie_prev_"):
                page = int(data.replace("movie_prev_", ""))
            else:  # movie_next_
                page = int(data.replace("movie_next_", ""))

            search_query = context.user_data.get('movie_search_query', '')
            all_results = context.user_data.get('last_movie_results', [])

            if not all_results:
                await query.answer("❌ የፍለጋ ውጤት ጊዜው አልፏል!", show_alert=True)
                # Delete the message with expired results
                try:
                    await query.message.delete()
                except Exception as e:
                    logger.error(f"Error deleting expired message: {e}")
                return

            # Pagination settings
            per_page = 5
            total_pages = (len(all_results) + per_page - 1) // per_page

            # Get current page results
            start_idx = page * per_page
            end_idx = start_idx + per_page
            current_page_results = all_results[start_idx:end_idx]

            # Create inline keyboard with movie options (5 per page)
            keyboard = []
            for i, (file_id, file_name, file_title) in enumerate(current_page_results):
                display_name = file_name if file_name else (file_title if file_title else f"ፋይል {start_idx + i + 1}")
                display_title = display_name[:50] + "..." if len(display_name) > 50 else display_name
                keyboard.append([InlineKeyboardButton(
                    f"🎬 {display_title}", 
                    callback_data=f"movie_{start_idx + i}"
                )])

            # Add pagination buttons
            pagination_row = []
            if page > 0:
                pagination_row.append(InlineKeyboardButton("⬅️ ቀድሞ", callback_data=f"movie_prev_{page-1}"))
            if page < total_pages - 1:
                pagination_row.append(InlineKeyboardButton("ቀጣይ ➡️", callback_data=f"movie_next_{page+1}"))

            if pagination_row:
                keyboard.append(pagination_row)

            # Always add search and home buttons
            keyboard.append([
                InlineKeyboardButton("🔍 ሌላ ለመፈለግ", callback_data="search_again_movie"),
                InlineKeyboardButton("🏠 Home", callback_data="go_home")
            ])

            reply_markup = InlineKeyboardMarkup(keyboard)
            page_info = f"📄 ገጽ {page + 1}/{total_pages}" if total_pages > 1 else ""

            # Edit the current message
            await query.edit_message_text(
                text=f"🔍 የፈለጉት '{search_query}'\n\n"
                     f"{page_info}\n"
                     "⬇️ የሚፈልጉትን ፊልም ይምረጡ:",
                reply_markup=reply_markup
            )
            await query.answer()
        except Exception as e:
            logger.error(f"Movie pagination error: {e}")
            await query.answer("❌ ስህተት ተፈጥሯል!", show_alert=True)
        return

    # Handle series pagination  
    elif data.startswith("series_prev_") or data.startswith("series_next_"):
        from telegram import InlineKeyboardMarkup, InlineKeyboardButton
        try:
            if data.startswith("series_prev_"):
                page = int(data.replace("series_prev_", ""))
            else:  # series_next_
                page = int(data.replace("series_next_", ""))

            search_query = context.user_data.get('series_search_query', '')
            all_results = context.user_data.get('last_series_results', [])

            if not all_results:
                await query.answer("❌ የፍለጋ ውጤት ጊዜው አልፏል!", show_alert=True)
                # Delete the message with expired results
                try:
                    await query.message.delete()
                except Exception as e:
                    logger.error(f"Error deleting expired message: {e}")
                return

            # Pagination settings
            per_page = 5
            total_pages = (len(all_results) + per_page - 1) // per_page

            # Get current page results
            start_idx = page * per_page
            end_idx = start_idx + per_page
            current_page_results = all_results[start_idx:end_idx]

            # Create inline keyboard with series options (5 per page)
            keyboard = []
            for i, (file_id, file_name, file_title) in enumerate(current_page_results):
                display_name = file_name if file_name else (file_title if file_title else f"ፋይል {start_idx + i + 1}")
                display_title = display_name[:50] + "..." if len(display_name) > 50 else display_name
                keyboard.append([InlineKeyboardButton(
                    f"📽 {display_title}", 
                    callback_data=f"series_{start_idx + i}"
                )])

            # Add pagination buttons
            pagination_row = []
            if page > 0:
                pagination_row.append(InlineKeyboardButton("⬅️ ቀድሞ", callback_data=f"series_prev_{page-1}"))
            if page < total_pages - 1:
                pagination_row.append(InlineKeyboardButton("ቀጣይ ➡️", callback_data=f"series_next_{page+1}"))

            if pagination_row:
                keyboard.append(pagination_row)

            # Always add search and home buttons
            keyboard.append([
                InlineKeyboardButton("🔍 ሌላ ለመፈለግ", callback_data="search_again_series"),
                InlineKeyboardButton("🏠 Home", callback_data="go_home")
            ])

            reply_markup = InlineKeyboardMarkup(keyboard)
            page_info = f"📄 ገጽ {page + 1}/{total_pages}" if total_pages > 1 else ""

            # Edit the current message
            await query.edit_message_text(
                text=f"🔍 የፈለጉት '{search_query}'\n\n"
                     f"{page_info}\n"
                     "⬇️ የሚፈልጉትን ተከታታይ ፊልም ይምረጡ:",
                reply_markup=reply_markup
            )
            await query.answer()
        except Exception as e:
            logger.error(f"Series pagination error: {e}")
            await query.answer("❌ ስህተት ተፈጥሯል!", show_alert=True)
        return

    # Handle movie file sending with payment check
    elif data.startswith("movie_"):
        try:
            index = int(data.replace("movie_", ""))
            user_id = query.from_user.id

            # Check if user is blocked
            if user_block_system.is_user_blocked(user_id):
                await query.answer("🚫 እርስዎ ተገድበዋል።", show_alert=True)
                return

            # Get the last search results from context
            if 'last_movie_results' in context.user_data:
                results = context.user_data['last_movie_results']
                if 0 <= index < len(results):
                    file_id = results[index][0]
                    file_name = results[index][1]

                    # Check user balance - 3 birr for single movie
                    MOVIE_PRICE = 3
                    user_balance = db.get_user_balance(user_id)

                    if user_balance < MOVIE_PRICE:
                        await query.answer(
                            f"❌ በቂ ሂሳብ የለዎትም!\n\n"
                            f"💰 ያለዎት: {user_balance} ብር\n"
                            f"💵 የሚያስፈልግ: {MOVIE_PRICE} ብር\n\n"
                            f"እባክዎ ገቢ ያድርጉ! 🏦",
                            show_alert=True
                        )
                        return

                    # Deduct balance
                    import sqlite3
                    with sqlite3.connect(config.USER_DB_PATH) as conn:
                        conn.execute('UPDATE users SET balance = balance - ? WHERE user_id = ?', (MOVIE_PRICE, user_id))
                        conn.commit()

                    new_balance = user_balance - MOVIE_PRICE

                    # Delete the inline keyboard message completely
                    try:
                        await query.message.delete()
                    except Exception as e:
                        logger.error(f"Error deleting inline keyboard message: {e}")

                    await send_film(context.bot, query.message.chat.id, file_id, file_name)

                    # Log download
                    db.log_download(user_id, file_id, "movie", file_name)

                    await query.answer(f"✅ {MOVIE_PRICE} ብር ተከፍሏል!")

                    # Clear user state and return to main menu
                    USER_STATES.pop(user_id, None)
                    await context.bot.send_message(
                        chat_id=query.message.chat.id,
                        text="🏠 ወደ ዋና ምናሌ ተመልሰዋል",
                        reply_markup=get_main_keyboard()
                    )
                else:
                    await query.answer("❌ ፊልም አልተገኘም!", show_alert=True)
                    # Delete the message with expired results
                    try:
                        await query.message.delete()
                    except Exception as e:
                        logger.error(f"Error deleting expired message: {e}")
            else:
                await query.answer("❌ የፍለጋ ውጤት ጊዜው አልፏል!", show_alert=True)
                # Delete the message with expired results
                try:
                    await query.message.delete()
                except Exception as e:
                    logger.error(f"Error deleting expired message: {e}")
        except Exception as e:
            logger.error(f"Error sending movie file: {e}")
            await query.answer("❌ ፊልም መላክ አልተቻለም!", show_alert=True)
        return

    elif data.startswith("series_") and not data.startswith("series_db_checking"):
        try:
            index = int(data.replace("series_", ""))
            user_id = query.from_user.id

            # Check if user is blocked
            if user_block_system.is_user_blocked(user_id):
                await query.answer("🚫 እርስዎ ተገድበዋል።", show_alert=True)
                return

            # Get the last search results from context
            if 'last_series_results' in context.user_data:
                results = context.user_data['last_series_results']
                if 0 <= index < len(results):
                    file_id = results[index][0]
                    file_name = results[index][1]

                    # Check user balance - 2 birr for series episode
                    SERIES_PRICE = 2
                    user_balance = db.get_user_balance(user_id)

                    if user_balance < SERIES_PRICE:
                        await query.answer(
                            f"❌ በቂ ሂሳብ የለዎትም!\n\n"
                            f"💰 ያለዎት: {user_balance} ብር\n"
                            f"💵 የሚያስፈልግ: {SERIES_PRICE} ብር\n\n"
                            f"እባክዎ ገቢ ያድርጉ! 🏦",
                            show_alert=True
                        )
                        return

                    # Deduct balance
                    import sqlite3
                    with sqlite3.connect(config.USER_DB_PATH) as conn:
                        conn.execute('UPDATE users SET balance = balance - ? WHERE user_id = ?', (SERIES_PRICE, user_id))
                        conn.commit()

                    new_balance = user_balance - SERIES_PRICE

                    # Delete the inline keyboard message completely
                    try:
                        await query.message.delete()
                    except Exception as e:
                        logger.error(f"Error deleting inline keyboard message: {e}")

                    await send_film(context.bot, query.message.chat.id, file_id, file_name)

                    # Log download
                    db.log_download(user_id, file_id, "series", file_name)

                    await query.answer(f"✅ {SERIES_PRICE} ብር ተከፍሏል!")

                    # Clear user state and return to main menu
                    USER_STATES.pop(user_id, None)
                    await context.bot.send_message(
                        chat_id=query.message.chat.id,
                        text="🏠 ወደ ዋና ምናሌ ተመልሰዋል",
                        reply_markup=get_main_keyboard()
                    )
                else:
                    await query.answer("❌ ተከታታይ ፊልም አልተገኘም!", show_alert=True)
                    # Delete the message with expired results
                    try:
                        await query.message.delete()
                    except Exception as e:
                        logger.error(f"Error deleting expired message: {e}")
            else:
                await query.answer("❌ የፍለጋ ውጤት ጊዜው አልፏል!", show_alert=True)
                # Delete the message with expired results
                try:
                    await query.message.delete()
                except Exception as e:
                    logger.error(f"Error deleting expired message: {e}")
        except Exception as e:
            logger.error(f"Error sending series file: {e}")
            await query.answer("❌ ተከታታይ ፊልም መላክ አልተቻለም!", show_alert=True)
        return

    # Handle payment approval callbacks
    if data.startswith("approve_payment_") or data.startswith("reject_payment_"):
        await payment_system.handle_admin_approval(update, context)
        return

    # Handle admin balance callbacks
    from admin_balance import admin_balance
    if data in ["admin_finance", "user_management", "pending_payments", "successful_payments", 
                "failed_payments", "payment_reports", "search_payment_by_id", "search_by_id", "search_by_username", 
                "search_by_phone", "report_daily", "report_weekly", "report_monthly", "report_yearly"] or \
       data.startswith(("pending_page_", "successful_page_", "failed_page_", "approve_", 
                       "reject_", "view_payment_", "details_", "add_balance_", "reduce_balance_", "user_history_", 
                       "history_page_", "back_to_user_")):
        await admin_balance.handle_callback_query(query, context)
        return

    # Handle admin callbacks
    await admin_panel.handle_admin_callback(update, context)

async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /henok command"""
    user = update.effective_user

    logger.info(f"Henok command received from user {user.id}, expected admin {config.ADMIN_USER_ID}")

    if user.id == config.ADMIN_USER_ID:
        await admin_panel.show_admin_panel(update, context)
    else:
        await update.message.reply_text("❌ የAdmin መብት የለዎትም!")

async def balance_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /balance command - Show user balance"""
    user = update.effective_user

    if user_block_system.is_user_blocked(user.id):
        await update.message.reply_text(
            "🚫 **የተገደበ ተጠቃሚ**\n\n"
            "እርስዎ ከBot አገልግሎት ተገደብተዋል።\n"
            "ለበለጠ መረጃ [Admin](https://t.me/Henok_Chat) ን ያነጋግሩ።",
            parse_mode='Markdown'
        )
        return

    if not db.user_exists(user.id):
        await start(update, context)
        return

    # Clear search state
    USER_STATES.pop(user.id, None)

    try:
        user_balance = db.get_user_balance(user.id)

        if user_balance is None:
            balance_amount = 0
        else:
            try:
                balance_amount = int(float(user_balance))
            except (ValueError, TypeError):
                logger.error(f"Invalid balance value for user {user.id}: {user_balance}")
                balance_amount = 0

        await update.message.reply_text(
            f"💰 የእርስዎ ሒሳብ መጠን\n\n"
            f"💵 ያለዎት ገንዘብ: {balance_amount:,} ብር\n\n"
            f"💡 ገንዘብ ለመጨመር /payment ይጠቀሙ",
            reply_markup=get_main_keyboard()
        )
        logger.info(f"Balance displayed for user {user.id}: {balance_amount} ብር")

    except Exception as e:
        logger.error(f"Error showing balance for user {user.id}: {e}", exc_info=True)
        await update.message.reply_text(
            f"💰 የእርስዎ ሒሳብ መጠን\n\n"
            f"💵 ያለዎት ገንዘብ: 0 ብር\n\n"
            f"⚠️ የሒሳብ መረጃ ለማግኘት ችግር ተፈጥሯል። እባክዎ እንደገና ይሞክሩ።",
            reply_markup=get_main_keyboard()
        )

async def payment_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /payment command - Show payment menu"""
    user = update.effective_user

    if user_block_system.is_user_blocked(user.id):
        await update.message.reply_text(
            "🚫 **የተገደበ ተጠቃሚ**\n\n"
            "እርስዎ ከBot አገልግሎት ተገደብተዋል።\n"
            "ለበለጠ መረጃ [Admin](https://t.me/Henok_Chat) ን ያነጋግሩ።",
            parse_mode='Markdown'
        )
        return

    if not db.user_exists(user.id):
        await start(update, context)
        return

    # Clear search state
    USER_STATES.pop(user.id, None)

    await payment_system.show_payment_menu(update, context)

async def referral_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /referral command - Show referral info"""
    user = update.effective_user

    if user_block_system.is_user_blocked(user.id):
        await update.message.reply_text(
            "🚫 **የተገደበ ተጠቃሚ**\n\n"
            "እርስዎ ከBot አገልግሎት ተገደብተዋል።\n"
            "ለበለጠ መረጃ [Admin](https://t.me/Henok_Chat) ን ያነጋግሩ።",
            parse_mode='Markdown'
        )
        return

    if not db.user_exists(user.id):
        await start(update, context)
        return

    # Clear search state
    USER_STATES.pop(user.id, None)

    # Clear search results from context
    if 'last_movie_results' in context.user_data:
        del context.user_data['last_movie_results']
    if 'last_series_results' in context.user_data:
        del context.user_data['last_series_results']
    if 'last_all_results' in context.user_data:
        del context.user_data['last_all_results']
    if 'movie_search_query' in context.user_data:
        del context.user_data['movie_search_query']
    if 'series_search_query' in context.user_data:
        del context.user_data['series_search_query']
    if 'all_search_query' in context.user_data:
        del context.user_data['all_search_query']

    await referral_system.show_referral_info(update, context)

async def series_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /series command - Start series search"""
    user = update.effective_user

    if user_block_system.is_user_blocked(user.id):
        await update.message.reply_text(
            "🚫 **የተገደበ ተጠቃሚ**\n\n"
            "እርስዎ ከBot አገልግሎት ተገደብተዋል።\n"
            "ለበለጠ መረጃ [Admin](https://t.me/Henok_Chat) ን ያነጋግሩ።",
            parse_mode='Markdown'
        )
        return

    if not db.user_exists(user.id):
        await start(update, context)
        return

    back_keyboard = [[KeyboardButton("⬅️ ለመመለስ")]]
    back_reply_markup = ReplyKeyboardMarkup(back_keyboard, resize_keyboard=True)

    await update.message.reply_text(
        "የምፈልጉትን ተከታታይ ፊልም ስም ይጻፉ:",
        reply_markup=back_reply_markup
    )
    USER_STATES[user.id] = WAITING_FOR_SERIES_SEARCH

async def single_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /single command - Start single movie search"""
    user = update.effective_user

    if user_block_system.is_user_blocked(user.id):
        await update.message.reply_text(
            "🚫 **የተገደበ ተጠቃሚ**\n\n"
            "እርስዎ ከBot አገልግሎት ተገደብተዋል።\n"
            "ለበለጠ መረጃ [Admin](https://t.me/Henok_Chat) ን ያነጋግሩ።",
            parse_mode='Markdown'
        )
        return

    if not db.user_exists(user.id):
        await start(update, context)
        return

    back_keyboard = [[KeyboardButton("⬅️ ለመመለስ")]]
    back_reply_markup = ReplyKeyboardMarkup(back_keyboard, resize_keyboard=True)

    await update.message.reply_text(
        "የምፈልጉትን ነጠላ ፊልም ስም ይጻፉ:",
        reply_markup=back_reply_markup
    )
    USER_STATES[user.id] = WAITING_FOR_MOVIE_SEARCH

async def all_films_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /all_films command - Start all films search"""
    user = update.effective_user

    if user_block_system.is_user_blocked(user.id):
        await update.message.reply_text(
            "🚫 **የተገደበ ተጠቃሚ**\n\n"
            "እርስዎ ከBot አገልግሎት ተገደብተዋል።\n"
            "ለበለጠ መረጃ [Admin](https://t.me/Henok_Chat) ን ያነጋግሩ።",
            parse_mode='Markdown'
        )
        return

    if not db.user_exists(user.id):
        await start(update, context)
        return

    back_keyboard = [[KeyboardButton("⬅️ ለመመለስ")]]
    back_reply_markup = ReplyKeyboardMarkup(back_keyboard, resize_keyboard=True)

    await update.message.reply_text(
        "የምፈልጉትን ፊልም ስም ይጻፉ (ነጠላ ወይም ተከታታይ):",
        reply_markup=back_reply_markup
    )
    USER_STATES[user.id] = WAITING_FOR_ALL_SEARCH

# Global asyncio Queue for channel posts - continuous processing
CHANNEL_QUEUE = None  # Will be initialized in main()

async def channel_consumer():
    """Simple async queue feeder - no blocking calls for maximum throughput"""
    import time
    import gc

    processed_count = 0
    error_count = 0
    start_time = time.time()
    last_cleanup = time.time()

    logger.info("🚀 Channel Consumer started - async queue feeder mode!")

    while True:
        # Periodic memory cleanup (every 5 minutes)
        if time.time() - last_cleanup > 300:
            gc.collect()
            last_cleanup = time.time()
            logger.info("🧹 Memory cleanup performed")
        try:
            # Get message from queue (blocks until available)
            message_data = await CHANNEL_QUEUE.get()

            message = message_data['message']
            channel_id = message_data['channel_id']

            # Simple async processing - no blocking duplicate checks
            file_obj = message.document or message.video
            if file_obj:
                try:
                    if channel_id in config.SINGLE_MOVIE_CHANNEL_IDS:
                        success = await handle_movie_channel_post(message, channel_id)
                        if success:
                            processed_count += 1

                    elif channel_id in config.SERIES_CHANNEL_IDS:
                        success = await handle_series_channel_post(message, channel_id)
                        if success:
                            processed_count += 1
                except Exception as e:
                    logger.error(f"❌ Error processing message: {e}")
                    error_count += 1

                # Log stats every 50 files
                if (processed_count + error_count) > 0 and (processed_count + error_count) % 50 == 0:
                    elapsed = time.time() - start_time
                    rate = (processed_count + error_count) / elapsed if elapsed > 0 else 0
                    logger.info(
                        f"📊 Stats: {processed_count} processed, "
                        f"{error_count} errors | Queue: {CHANNEL_QUEUE.qsize()} | Rate: {rate:.1f} files/sec"
                    )

            CHANNEL_QUEUE.task_done()

        except Exception as e:
            logger.error(f"❌ Channel consumer error: {e}")
            await asyncio.sleep(0.1)

async def handle_channel_post(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle new posts in monitored channels with backpressure protection"""
    if not update.channel_post:
        return

    message = update.channel_post
    channel_id = message.chat.id

    # Check if message has document/video
    if message.document or message.video:
        try:
            # Instant enqueue with timeout for backpressure
            await asyncio.wait_for(
                CHANNEL_QUEUE.put({
                    'message': message,
                    'channel_id': channel_id
                }),
                timeout=5.0  # Wait max 5 seconds if queue is full
            )

            queue_size = CHANNEL_QUEUE.qsize()
            logger.info(f"✅ Enqueued. Queue: {queue_size}")

            # Progressive warnings and admin notification
            if queue_size > 8000:
                logger.critical(f"🚨 CRITICAL: Queue at {queue_size}/10000 - near capacity!")
                # Notify admin
                try:
                    await context.bot.send_message(
                        chat_id=config.ADMIN_USER_ID,
                        text=f"🚨 ALERT: Channel queue critical!\n\n"
                             f"Queue size: {queue_size}/10,000\n"
                             f"System may start rejecting files soon!"
                    )
                except:
                    pass
            elif queue_size > 5000:
                logger.warning(f"⚠️ WARNING: Queue at {queue_size}/10000")

        except asyncio.TimeoutError:
            logger.error(f"🚨 Queue FULL (timeout)! Message REJECTED after 5s wait")
            # Notify admin of data loss
            try:
                file_name = getattr(message.document or message.video, 'file_name', 'Unknown')
                await context.bot.send_message(
                    chat_id=config.ADMIN_USER_ID,
                    text=f"❌ FILE LOST - Queue Full!\n\n"
                         f"File: {file_name}\n"
                         f"Queue overloaded - please slow down uploads!"
                )
            except:
                pass
        except asyncio.QueueFull:
            logger.error(f"🚨 Queue FULL! Message REJECTED")

async def main():
    """Start the bot"""
    import asyncio
    import signal

    global CHANNEL_QUEUE

    print("🤖 Telegram bot እየጀመር ነው...")

    # Initialize channel queue with bounded size
    CHANNEL_QUEUE = asyncio.Queue(maxsize=10000)
    logger.info("📋 Channel Queue initialized (max: 10,000)")

    # Initialize background worker
    from background_worker import background_worker
    await background_worker.initialize(config.BOT_TOKEN)

    # Start background worker in separate task
    asyncio.create_task(background_worker.start())
    logger.info("🔄 Background Worker started in parallel")

    # Start channel consumer in separate task - NEW!
    asyncio.create_task(channel_consumer())
    logger.info("🚀 Channel Consumer started - instant processing!")

    # Health check server disabled
    # # Bot status tracking for health check
    # bot_status = {'running': False, 'last_update': None}
    # 
    # # Start health check server for UptimeRobot
    # async def health_check(request):
    #     import time
    #     current_time = time.time()
    #     
    #     # Check if bot received updates recently (within 5 minutes)
    #     if bot_status['last_update']:
    #         time_since_update = current_time - bot_status['last_update']
    #         if time_since_update > 300:  # 5 minutes
    #             return web.Response(text="STALE", status=503)
    #     
    #     status = "OK" if bot_status['running'] else "STARTING"
    #     return web.Response(text=status, status=200)
    # 
    # async def update_status(request):
    #     bot_status['last_update'] = time.time()
    #     return web.Response(text="Updated", status=200)
    #
    # app = web.Application()
    # app.router.add_get('/', health_check)
    # app.router.add_get('/health', health_check)
    # app.router.add_post('/ping', update_status)
    # 
    # runner = web.AppRunner(app)
    # await runner.setup()
    # site = web.TCPSite(runner, '0.0.0.0', 8080)
    # asyncio.create_task(site.start())
    # logger.info("🏥 Health check server started on port 8080")

    # Create application with conflict resolution
    application = Application.builder().token(config.BOT_TOKEN).build()

    # Set up error handling for conflicts
    application.add_error_handler(handle_bot_error)

    # Add handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("henok", admin_command))
    application.add_handler(CommandHandler("balance", balance_command))
    application.add_handler(CommandHandler("payment", payment_command))
    application.add_handler(CommandHandler("referral", referral_command))
    application.add_handler(CommandHandler("series", series_command))
    application.add_handler(CommandHandler("single", single_command))
    application.add_handler(CommandHandler("all_films", all_films_command))
    application.add_handler(MessageHandler(filters.CONTACT, handle_contact))
    application.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    application.add_handler(CallbackQueryHandler(handle_usage_callbacks, pattern='^usage_'))
    application.add_handler(CallbackQueryHandler(handle_admin_callback))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # Add channel post handler with proper filter
    application.add_handler(MessageHandler(
        (filters.Document.ALL | filters.VIDEO) & filters.ChatType.CHANNEL, 
        handle_channel_post
    ))

    # Initialize the application
    await application.initialize()

    # Start polling with conflict handling and auto-restart
    retry_count = 0
    max_retries = 999  # Infinite retries with backoff
    
    while retry_count < max_retries:
        try:
            await application.start()

            # Wait a moment before starting polling
            await asyncio.sleep(2)

            await application.updater.start_polling(
                allowed_updates=Update.ALL_TYPES,
                drop_pending_updates=True,  # Drop pending updates
                pool_timeout=30,  # Increase connection timeout
                connect_timeout=30,
                read_timeout=30,
                write_timeout=30
            )

            print("✅ Bot started successfully! 🎬")
            retry_count = 0  # Reset on successful start

        # Send startup notifications to pending users and admin
            await send_startup_notifications(application)
            
            break  # Exit retry loop on success

        except Exception as e:
            if "Conflict" in str(e):
                print("❌ አንድ ተጨማሪ Bot instance እየሮጠ ነው! እባክዎ አቁመው ይሞክሩ።")
                return
            else:
                retry_count += 1
                backoff = min(retry_count * 5, 60)  # Max 60 seconds
                logger.error(f"❌ Bot error (attempt {retry_count}): {e}")
                logger.info(f"🔄 Restarting in {backoff} seconds...")
                
                # Notify admin of restart
                try:
                    await application.bot.send_message(
                        chat_id=config.ADMIN_USER_ID,
                        text=f"⚠️ Bot Restarting!\n\n"
                             f"Error: {str(e)[:100]}\n"
                             f"Retry: {retry_count}\n"
                             f"Backoff: {backoff}s"
                    )
                except:
                    pass
                
                await asyncio.sleep(backoff)
                
                # Cleanup before retry
                try:
                    await application.updater.stop()
                    await application.stop()
                except:
                    pass
                
                continue  # Retry

    # Keep the application running
    try:
        # Handle shutdown gracefully
        stop_signals = (signal.SIGHUP, signal.SIGTERM, signal.SIGINT)
        for sig in stop_signals:
            signal.signal(sig, lambda s, f: asyncio.create_task(shutdown(application)))

        # Keep running
        while True:
            await asyncio.sleep(1)

    except KeyboardInterrupt:
        print("🛑 Bot stopped by user")
    finally:
        # Cleanup
        await shutdown(application)

async def handle_bot_error(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle bot errors"""
    error = context.error
    if "Conflict" in str(error):
        logger.warning("⚠️ Bot conflict detected - another instance might be running")
        print("⚠️ አንድ ተጨማሪ Bot instance እየሮጠ ሊሆን ይችላል!")
    else:
        logger.error(f"Bot error: {error}", exc_info=True)
        # Log user context for debugging
        if update and update.effective_user:
            logger.error(f"Error occurred for user {update.effective_user.id}")
        if update and update.effective_message:
            logger.error(f"Message text: {update.effective_message.text[:100] if update.effective_message.text else 'N/A'}")

async def send_startup_notifications(application):
    """Send startup statistics to admin only - no user notifications"""
    try:
        from series import SeriesManager
        from single import SingleMovieManager

        # Instantiate managers
        series_mgr = SeriesManager()
        movie_mgr = SingleMovieManager()

        # Get database counts
        series_count = series_mgr.get_series_count()
        movies_count = movie_mgr.get_movies_count()

        # Send admin report only
        admin_message = (
            "🤖 *ET Films Bot ተጀምሯል!*\n\n"
            f"✅ Series Database: {series_count:,} ፋይሎች\n"
            f"✅ Single Movies Database: {movies_count:,} ፋይሎች\n"
            f"✅ Duplicate Detection: ዝግጁ"
        )

        await application.bot.send_message(
            chat_id=config.ADMIN_USER_ID,
            text=admin_message,
            parse_mode='Markdown'
        )

        # Set Mini App menu button for all users
        try:
            from telegram import MenuButtonWebApp, WebAppInfo as WAI
            _domain = os.environ.get("REPLIT_DEV_DOMAIN", "")
            if _domain:
                _webapp_url = f"https://{_domain}/webapp/"
                await application.bot.set_chat_menu_button(
                    menu_button=MenuButtonWebApp(
                        text="🎬 ET Films",
                        web_app=WAI(url=_webapp_url)
                    )
                )
                logger.info(f"✅ Mini App menu button set: {_webapp_url}")
        except Exception as me:
            logger.warning(f"Menu button setup skipped: {me}")

        logger.info("✅ Bot started - admin notified, no user notifications sent")

    except Exception as e:
        logger.error(f"❌ Error in startup notifications: {e}")

async def shutdown(application):
    """Gracefully shutdown the application"""
    import asyncio
    print("🛑 Shutting down bot...")
    try:
        # Clean shutdown with timeout
        await asyncio.wait_for(application.updater.stop(), timeout=10)
        await asyncio.wait_for(application.stop(), timeout=5)
        await asyncio.wait_for(application.shutdown(), timeout=5)

        # Bot cleanup completed

    except asyncio.TimeoutError:
        logger.warning("⚠️ Shutdown timeout - forcing stop")
    except Exception as e:
        logger.error(f"Error during shutdown: {e}")

if __name__ == '__main__':
    import asyncio
    asyncio.run(main())