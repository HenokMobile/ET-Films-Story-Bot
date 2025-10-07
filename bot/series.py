import sqlite3
import logging
from telegram import Update
from telegram.ext import ContextTypes
import config

logger = logging.getLogger(__name__)

class SeriesManager:
    def __init__(self):
        self.setup_database()

    def setup_database(self):
        """Setup series database"""
        with sqlite3.connect(config.SERIES_DB_PATH) as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS series (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    file_id TEXT UNIQUE,
                    message_id INTEGER,
                    file_unique_id TEXT,
                    file_name TEXT,
                    file_title TEXT,
                    channel_id INTEGER,
                    file_size INTEGER DEFAULT 0,
                    added_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Migration: Add file_size column if it doesn't exist
            cursor = conn.cursor()
            cursor.execute("PRAGMA table_info(series)")
            columns = [col[1] for col in cursor.fetchall()]
            
            if 'file_size' not in columns:
                logger.info("🔧 Migration: Adding file_size column to series table")
                conn.execute('ALTER TABLE series ADD COLUMN file_size INTEGER DEFAULT 0')
                conn.commit()
                logger.info("✅ Migration completed: file_size column added")

    def add_series(self, file_id, message_id, file_unique_id, file_name, file_title, channel_id, file_size=0):
        """Add series to database"""
        try:
            with sqlite3.connect(config.SERIES_DB_PATH) as conn:
                # Check if duplicate exists by name and size
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT id FROM series 
                    WHERE file_name = ? AND file_size = ? AND file_size > 0
                ''', (file_name, file_size))
                
                if cursor.fetchone() and file_size > 0:
                    logger.warning(f"Duplicate series ignored: {file_name} ({file_size} bytes)")
                    return False
                
                conn.execute('''
                    INSERT OR REPLACE INTO series 
                    (file_id, message_id, file_unique_id, file_name, file_title, channel_id, file_size)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (file_id, message_id, file_unique_id, file_name, file_title, channel_id, file_size))
                logger.info(f"Series added: {file_name} ({file_size} bytes)")
                return True
        except Exception as e:
            logger.error(f"Error adding series: {e}")
            return False

    def search_series(self, query):
        """Search series by name and sort by episode number"""
        try:
            with sqlite3.connect(config.SERIES_DB_PATH) as conn:
                cursor = conn.execute('''
                    SELECT file_id, file_name, file_title FROM series 
                    WHERE file_name LIKE ? OR file_title LIKE ?
                    ORDER BY file_name ASC
                    LIMIT 50
                ''', (f'%{query}%', f'%{query}%'))
                results = cursor.fetchall()

                # Sort results to group by series name and then by episode number
                def sort_key(item):
                    file_name = item[1] or item[2] or ""
                    # Extract episode number for proper sorting
                    import re
                    match = re.search(r'(\d+)', file_name)
                    if match:
                        episode_num = int(match.group(1))
                        base_name = re.sub(r'\s*\d+.*$', '', file_name).strip()
                        return (base_name, episode_num)
                    return (file_name, 0)

                return sorted(results, key=sort_key)

        except Exception as e:
            logger.error(f"Error searching series: {e}")
            return []

    def get_all_series(self, limit=50):
        """Get all series with limit"""
        try:
            with sqlite3.connect(config.SERIES_DB_PATH) as conn:
                cursor = conn.execute('''
                    SELECT file_id, file_name, file_title FROM series 
                    ORDER BY added_date DESC
                    LIMIT ?
                ''', (limit,))
                return cursor.fetchall()
        except Exception as e:
            logger.error(f"Error getting all series: {e}")
            return []

    def get_series_count(self):
        """Get total series count"""
        try:
            with sqlite3.connect(config.SERIES_DB_PATH) as conn:
                cursor = conn.execute('SELECT COUNT(*) FROM series')
                return cursor.fetchone()[0]
        except Exception as e:
            logger.error(f"Error getting series count: {e}")
            return 0

async def handle_series_search(update: Update, context: ContextTypes.DEFAULT_TYPE, query: str, page: int = 0):
    """Handle series search and show results in inline keyboard with pagination"""
    from telegram import InlineKeyboardMarkup, InlineKeyboardButton

    # Send searching status
    searching_msg = await update.message.reply_text("🔍 እየፈለግሁ ነው...")

    series_manager = SeriesManager()
    all_results = series_manager.search_series(query)

    # Delete searching message
    try:
        await searching_msg.delete()
    except Exception as e:
        logger.error(f"Error deleting searching message: {e}")

    if not all_results:
        await update.message.reply_text(
            f"😥 *\"{query}\"* ይህን ፊልም ማግኘት አልቻልኩም፣\n\n"
            f"እባክዎ ስሙን ተሳስተው እንዳይሆን እንደገና በማረጋገጥ ይጻፉ\n"
            f"ወይንም ለመወጣት ከፈለጉ *⬅️ ለመመለስ* የሚለውን ይጫኑ 🙏",
            parse_mode='Markdown'
        )
        # Don't return - keep state active so user can search again
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
        # Prioritize file_name over file_title for display
        display_name = file_name if file_name else (file_title if file_title else f"ፋይል {start_idx + i + 1}")
        # Limit title length for better display
        display_title = display_name[:45] + "..." if len(display_name) > 45 else display_name
        # Use actual index from all results for callback
        keyboard.append([InlineKeyboardButton(
            f"📽 *{display_title}*", 
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

    # Store all results in user context for callback handling
    context.user_data['last_series_results'] = all_results
    context.user_data['series_search_query'] = query

    # Send the search results with pagination
    page_info = f"📄 ገጽ {page + 1}/{total_pages}" if total_pages > 1 else ""
    message = await update.message.reply_text(
        f"📽 *የተከታታይ ፊልም ፍለጋ ውጤት*\n\n"
        f"🔍 '*{query}*' ለሚል ፍለጋ *{len(all_results)}* ተከታታይ ፊልሞች ተገኝተዋል!\n\n"
        f"{page_info}\n"
        "⬇️ የሚፈልጉትን ተከታታይ ፊልም ይምረጡ:",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

    # Track this inline message for cleanup
    user_id = update.effective_user.id
    if 'last_inline_messages' not in context.user_data:
        context.user_data['last_inline_messages'] = {}
    if user_id not in context.user_data['last_inline_messages']:
        context.user_data['last_inline_messages'][user_id] = []
    context.user_data['last_inline_messages'][user_id].append(message.message_id)

async def send_duplicate_notification(bot, file_name, file_size, content_type="Series"):
    """Send duplicate notification to admin (Part 2 & 3)"""
    try:
        size_mb = file_size / (1024 * 1024)
        
        # Part 2: Channel Delete Notification
        delete_msg = (
            "🗑️ *Duplicate Deleted from Channel!*\n\n"
            f"📁 ስም: `{file_name}`\n"
            f"📏 መጠን: {size_mb:.2f} GB\n"
            f"📂 ቻናል: {content_type}\n\n"
            "⚠️ ምክንያት: በDatabase ውስጥ አስቀድሞ አለ\n"
            "   (ተመሳሳይ ስም \\+ ተመሳሳይ መጠን)"
        )
        
        # Part 3: Database Duplicate Alert
        db_alert_msg = (
            "⚠️ *Database Duplicate Detected!*\n\n"
            f"📁 አዲስ: `{file_name}` ({size_mb:.2f} GB)\n"
            f"💾 ያለው: `{file_name}` ({size_mb:.2f} GB)\n\n"
            "❌ በDatabase አልተቀመጠም\n"
            "✅ ከChannel ተሰርዟል"
        )
        
        # Send both notifications
        await bot.send_message(
            chat_id=config.ADMIN_USER_ID,
            text=delete_msg,
            parse_mode='Markdown'
        )
        
        await bot.send_message(
            chat_id=config.ADMIN_USER_ID,
            text=db_alert_msg,
            parse_mode='Markdown'
        )
        
        logger.info(f"✅ Duplicate notifications sent to admin for: {file_name}")
        
    except Exception as e:
        logger.error(f"❌ Error sending duplicate notification: {e}")

async def handle_series_channel_post(message, channel_id):
    """Handle new series posts in monitored channels"""
    series_manager = SeriesManager()

    if message.document or message.video:
        file_obj = message.document or message.video

        file_data = {
            'file_id': file_obj.file_id,
            'message_id': message.message_id,
            'file_unique_id': file_obj.file_unique_id,
            'file_name': getattr(file_obj, 'file_name', '') or '',
            'file_title': message.caption or '',
            'channel_id': channel_id,
            'file_size': getattr(file_obj, 'file_size', 0) or 0
        }

        # Check if duplicate exists (100% match: name + size, or wildcard for legacy size=0)
        if file_data['file_size'] > 0:
            import sqlite3
            with sqlite3.connect(config.SERIES_DB_PATH) as conn:
                cursor = conn.cursor()
                
                # Check for exact match (name + size) OR legacy match (name + size=0)
                cursor.execute('''
                    SELECT id, file_size FROM series 
                    WHERE file_name = ? AND (file_size = ? OR file_size = 0)
                ''', (file_data['file_name'], file_data['file_size']))
                
                existing = cursor.fetchone()
                
                if existing:
                    # If existing entry has size=0, update it with new size
                    if existing[1] == 0:
                        logger.info(f"📝 Updating legacy file size: {file_data['file_name']}")
                        conn.execute('''
                            UPDATE series 
                            SET file_size = ? 
                            WHERE id = ?
                        ''', (file_data['file_size'], existing[0]))
                        conn.commit()
                        logger.info(f"✅ Updated file size to {file_data['file_size']} bytes")
                    
                    # Delete from channel (duplicate regardless of size match)
                    try:
                        from telegram import Bot
                        bot = Bot(token=config.BOT_TOKEN)
                        
                        await bot.delete_message(
                            chat_id=channel_id,
                            message_id=message.message_id
                        )
                        
                        logger.info(f"🗑️ Deleted duplicate from channel: {file_data['file_name']}")
                        
                        # Send admin notifications (Part 2 & 3)
                        await send_duplicate_notification(
                            bot, 
                            file_data['file_name'], 
                            file_data['file_size'],
                            "Series"
                        )
                        
                        return False  # Don't save to database
                        
                    except Exception as e:
                        logger.error(f"❌ Error deleting duplicate from channel: {e}")

        success = series_manager.add_series(**file_data)
        if success:
            logger.info(f"Added new series: {file_data['file_name']} ({file_data['file_size']} bytes)")

        return success

    return False

# Global series manager instance
series_manager = SeriesManager()