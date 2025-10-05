import logging
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
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

# Reply Keyboard - Pre-built for faster response
_MAIN_KEYBOARD = ReplyKeyboardMarkup([
    [KeyboardButton("ተከታታይ ፊልም 📽"), KeyboardButton("ነጠላ ፊልም 🎬")],
    [KeyboardButton("🎞 ሁሉንም ፊልም")],
    [KeyboardButton("ቀር ሂሳብ 💰"), KeyboardButton("ገቢ ለማድረግ 🏦")],
    [KeyboardButton("ለመጋበዝ 🎁"), KeyboardButton("⚙️ አጠቃቀም")]
], resize_keyboard=True)

def get_main_keyboard():
    return _MAIN_KEYBOARD

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start command handler"""
    user = update.effective_user
    
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

        # Save user to database
        db.add_user(
            user_id=user.id,
            username=user.username,
            phone_number=contact.phone_number,
            first_name=user.first_name,
            last_name=user.last_name
        )
        
        pending_referrer = context.user_data.get('pending_referrer')
        if pending_referrer:
            await referral_system.process_referral(user.id, pending_referrer, context)
            context.user_data.pop('pending_referrer', None)

        await update.message.reply_text(
            "እግዚአብሔር ይመሰግናችሁ! 🙏\n\n"
            "አሁን የ ET Films Story Bot 🎥 ሁሉንም አገልግሎት መጠቀም ይችላሉ።",
            reply_markup=get_main_keyboard()
        )

        if user.id in USER_STATES:
            del USER_STATES[user.id]

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle all text messages"""
    user = update.effective_user
    text = update.message.text

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
        for key in ['last_movie_results', 'last_series_results']:
            if key in context.user_data:
                del context.user_data[key]
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

            reply_markup = InlineKeyboardMarkup(keyboard)
            page_info = f"ገጽ {page + 1}/{total_pages}" if total_pages > 1 else ""

            await query.edit_message_text(
                text=f"🔍 '{search_query}' ለሚል ፍለጋ {len(all_results)} ፊልሞች ተገኝተዋል:\n\n"
                     f"{page_info}\n"
                     "የሚፈልጉትን ፊልም ይምረጡ:",
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
            
            user_id = query.from_user.id
            
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
                    conn = sqlite3.connect(config.USER_DB_PATH)
                    conn.execute('UPDATE users SET balance = balance - ? WHERE user_id = ?', (PRICE, user_id))
                    conn.commit()
                    conn.close()

                    # Delete the inline keyboard message
                    try:
                        await query.message.delete()
                    except Exception as e:
                        logger.error(f"Error deleting inline keyboard message: {e}")

                    await context.bot.send_document(
                        chat_id=query.message.chat.id,
                        document=file_id
                    )
                    
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

            reply_markup = InlineKeyboardMarkup(keyboard)
            page_info = f"ገጽ {page + 1}/{total_pages}" if total_pages > 1 else ""

            # Edit the current message
            await query.edit_message_text(
                text=f"🔍 '{search_query}' ለሚል ፍለጋ {len(all_results)} ነጠላ ፊልሞች ተገኝተዋል:\n\n"
                     f"{page_info}\n"
                     "የሚፈልጉትን ፊልም ይምረጡ:",
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

            reply_markup = InlineKeyboardMarkup(keyboard)
            page_info = f"ገጽ {page + 1}/{total_pages}" if total_pages > 1 else ""

            # Edit the current message
            await query.edit_message_text(
                text=f"🔍 '{search_query}' ለሚል ፍለጋ {len(all_results)} ተከታታይ ፊልሞች ተገኝተዋል:\n\n"
                     f"{page_info}\n"
                     "የሚፈልጉትን ተከታታይ ፊልም ይምረጡ:",
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
                    conn = sqlite3.connect(config.USER_DB_PATH)
                    conn.execute('UPDATE users SET balance = balance - ? WHERE user_id = ?', (MOVIE_PRICE, user_id))
                    conn.commit()
                    conn.close()
                    
                    new_balance = user_balance - MOVIE_PRICE

                    # Delete the inline keyboard message completely
                    try:
                        await query.message.delete()
                    except Exception as e:
                        logger.error(f"Error deleting inline keyboard message: {e}")

                    await context.bot.send_document(
                        chat_id=query.message.chat.id,
                        document=file_id
                    )
                    
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
                    conn = sqlite3.connect(config.USER_DB_PATH)
                    conn.execute('UPDATE users SET balance = balance - ? WHERE user_id = ?', (SERIES_PRICE, user_id))
                    conn.commit()
                    conn.close()
                    
                    new_balance = user_balance - SERIES_PRICE

                    # Delete the inline keyboard message completely
                    try:
                        await query.message.delete()
                    except Exception as e:
                        logger.error(f"Error deleting inline keyboard message: {e}")

                    await context.bot.send_document(
                        chat_id=query.message.chat.id,
                        document=file_id
                    )
                    
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
    
    if not db.user_exists(user.id):
        await start(update, context)
        return
    
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
    
    if not db.user_exists(user.id):
        await start(update, context)
        return
    
    await payment_system.show_payment_menu(update, context)

async def referral_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /referral command - Show referral info"""
    user = update.effective_user
    
    if not db.user_exists(user.id):
        await start(update, context)
        return
    
    await referral_system.show_referral_info(update, context)

async def series_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /series command - Start series search"""
    user = update.effective_user
    
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

# Global variables for batch processing
BATCH_QUEUE = []
BATCH_TIMER = None
BATCH_DELAY = 2  # seconds

async def process_batch():
    """Process all messages in batch queue"""
    global BATCH_QUEUE, BATCH_TIMER

    if not BATCH_QUEUE:
        BATCH_TIMER = None
        return

    logger.info(f"Processing batch of {len(BATCH_QUEUE)} messages...")
    processed_count = 0

    for message_data in BATCH_QUEUE:
        try:
            message = message_data['message']
            channel_id = message_data['channel_id']

            # Determine which database to save to based on channel
            if channel_id in config.SINGLE_MOVIE_CHANNEL_IDS:
                success = await handle_movie_channel_post(message, channel_id)
                if success:
                    processed_count += 1

            elif channel_id in config.SERIES_CHANNEL_IDS:
                success = await handle_series_channel_post(message, channel_id)
                if success:
                    processed_count += 1

        except Exception as e:
            logger.error(f"Error processing batch message: {e}")

    # Clear the queue
    BATCH_QUEUE = []
    BATCH_TIMER = None
    logger.info(f"Batch processing completed! {processed_count}/{len(BATCH_QUEUE)} messages processed successfully.")

async def handle_channel_post(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle new posts in monitored channels with batch processing"""
    global BATCH_QUEUE, BATCH_TIMER

    if not update.channel_post:
        return

    message = update.channel_post
    channel_id = message.chat.id

    # Check if message has document/video
    if message.document or message.video:
        # Add to batch queue
        BATCH_QUEUE.append({
            'message': message,
            'channel_id': channel_id
        })

        logger.info(f"Added message to batch queue. Queue size: {len(BATCH_QUEUE)}")

        # Cancel existing timer if any
        if BATCH_TIMER:
            BATCH_TIMER.cancel()

        # Set new timer for batch processing
        import asyncio

        async def delayed_process():
            await asyncio.sleep(BATCH_DELAY)
            await process_batch()

        BATCH_TIMER = asyncio.create_task(delayed_process())

async def main():
    """Start the bot"""
    import asyncio
    import signal
    
    print("🤖 Telegram bot እየጀመር ነው...")
    
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
    
    # Start polling with conflict handling
    try:
        await application.start()
        
        # Wait a moment before starting polling
        await asyncio.sleep(2)
        
        await application.updater.start_polling(
            allowed_updates=Update.ALL_TYPES,
            drop_pending_updates=True  # Drop pending updates to avoid conflicts
        )
        
        print("✅ Bot started successfully! 🎬")
        
    except Exception as e:
        if "Conflict" in str(e):
            print("❌ አንድ ተጨማሪ Bot instance እየሮጠ ነው! እባክዎ አቁመው ይሞክሩ።")
            return
        else:
            logger.error(f"Error starting bot: {e}")
            raise
    
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