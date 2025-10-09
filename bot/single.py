import sqlite3
import logging
from telegram import Update
from telegram.ext import ContextTypes
import config
import asyncio

logger = logging.getLogger(__name__)

# Global counter for instant blocks
instant_blocks_count = 0

class SingleMovieManager:
    def __init__(self):
        self.setup_database()

    def setup_database(self):
        """Setup single movies database"""
        with sqlite3.connect(config.SINGLE_DB_PATH) as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS single_movies (
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
            cursor.execute("PRAGMA table_info(single_movies)")
            columns = [col[1] for col in cursor.fetchall()]

            if 'file_size' not in columns:
                logger.info("🔧 Migration: Adding file_size column to single_movies table")
                conn.execute('ALTER TABLE single_movies ADD COLUMN file_size INTEGER DEFAULT 0')
                conn.commit()
                logger.info("✅ Migration completed: file_size column added")

    def add_single_movie(self, file_id, message_id, file_unique_id, file_name, file_title, channel_id, file_size=0):
        """Add single movie to database"""
        try:
            with sqlite3.connect(config.SINGLE_DB_PATH) as conn:
                # Check if duplicate exists by name and size
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT id FROM single_movies 
                    WHERE file_name = ? AND file_size = ? AND file_size > 0
                ''', (file_name, file_size))

                if cursor.fetchone() and file_size > 0:
                    logger.warning(f"Duplicate movie ignored: {file_name} ({file_size} bytes)")
                    return False

                conn.execute('''
                    INSERT OR REPLACE INTO single_movies 
                    (file_id, message_id, file_unique_id, file_name, file_title, channel_id, file_size)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (file_id, message_id, file_unique_id, file_name, file_title, channel_id, file_size))
                logger.info(f"Single movie added: {file_name} ({file_size} bytes)")
                return True
        except Exception as e:
            logger.error(f"Error adding single movie: {e}")
            return False

    def search_single_movies(self, query):
        """Search single movies by name and sort alphabetically"""
        try:
            with sqlite3.connect(config.SINGLE_DB_PATH) as conn:
                cursor = conn.execute('''
                    SELECT file_id, file_name, file_title FROM single_movies 
                    WHERE file_name LIKE ? OR file_title LIKE ?
                    ORDER BY file_name ASC
                    LIMIT 100
                ''', (f'%{query}%', f'%{query}%'))
                return cursor.fetchall()
        except Exception as e:
            logger.error(f"Error searching single movies: {e}")
            return []

    def get_all_movies(self, limit=50):
        """Get all single movies with limit"""
        try:
            with sqlite3.connect(config.SINGLE_DB_PATH) as conn:
                cursor = conn.execute('''
                    SELECT file_id, file_name, file_title FROM single_movies 
                    ORDER BY added_date DESC
                    LIMIT ?
                ''', (limit,))
                return cursor.fetchall()
        except Exception as e:
            logger.error(f"Error getting all movies: {e}")
            return []

    def get_movies_count(self):
        """Get total movies count"""
        try:
            with sqlite3.connect(config.SINGLE_DB_PATH) as conn:
                cursor = conn.execute('SELECT COUNT(*) FROM single_movies')
                return cursor.fetchone()[0]
        except Exception as e:
            logger.error(f"Error getting movies count: {e}")
            return 0

    async def save_to_database(self, file_id, message_id, file_unique_id, file_name, file_title, channel_id, file_size):
        """Save single movie to database with duplicate checking - BLOCKS duplicates"""
        try:
            with sqlite3.connect(config.SINGLE_DB_PATH) as conn:
                cursor = conn.cursor()

                # Check for exact duplicate by name and size BEFORE inserting
                cursor.execute('''
                    SELECT id, file_name, file_size FROM single_movies 
                    WHERE file_name = ? AND file_size = ? AND file_size > 0
                ''', (file_name, file_size))

                existing = cursor.fetchone()

                if existing and file_size > 0:
                    logger.warning(f"🚫 Duplicate BLOCKED from database: {file_name} ({file_size} bytes)")
                    return existing[0], True  # Return existing ID and duplicate flag - DO NOT INSERT

                # Only insert if NOT duplicate
                cursor.execute('''
                    INSERT INTO single_movies 
                    (file_id, message_id, file_unique_id, file_name, file_title, channel_id, file_size)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (file_id, message_id, file_unique_id, file_name, file_title, channel_id, file_size))

                conn.commit()
                new_id = cursor.lastrowid
                logger.info(f"✅ Movie saved: {file_name} (ID: {new_id})")
                return new_id, False  # Return new ID and not duplicate

        except sqlite3.IntegrityError as e:
            logger.error(f"Database integrity error: {e}")
            return None, False
        except Exception as e:
            logger.error(f"Error saving movie: {e}")
            return None, False


async def handle_movie_search(update: Update, context: ContextTypes.DEFAULT_TYPE, query: str, page: int = 0):
    """Handle movie search and show results in inline keyboard with pagination"""
    from telegram import InlineKeyboardMarkup, InlineKeyboardButton

    # Send searching status
    searching_msg = await update.message.reply_text("🔍 በChannels ውስጥ እየፈለግሁ ነው...")

    movie_manager = SingleMovieManager()
    all_results = movie_manager.search_single_movies(query)

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

    # Pagination settings - 5 items per page, max 10 pages (50 items total)
    per_page = 5
    max_items = 50  # 10 pages × 5 items
    limited_results = all_results[:max_items]
    total_pages = (len(limited_results) + per_page - 1) // per_page

    # Get current page results
    start_idx = page * per_page
    end_idx = start_idx + per_page
    current_page_results = limited_results[start_idx:end_idx]

    # Create inline keyboard with movie options (5 per page)
    keyboard = []
    for i, (file_id, file_name, file_title) in enumerate(current_page_results):
        # Prioritize file_name over file_title for display
        display_name = file_name if file_name else (file_title if file_title else f"ፋይል {start_idx + i + 1}")
        # Limit title length for better display
        display_title = display_name[:45] + "..." if len(display_name) > 45 else display_name
        # Use actual index from all results for callback
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

    # Always add search and home buttons at the bottom
    keyboard.append([
        InlineKeyboardButton("🔍 ሌላ ለመፈለግ", callback_data="search_again_movie"),
        InlineKeyboardButton("🏠 Home", callback_data="go_home")
    ])

    reply_markup = InlineKeyboardMarkup(keyboard)

    # Store all results in user context for callback handling
    context.user_data['last_movie_results'] = all_results
    context.user_data['movie_search_query'] = query

    # Send the search results with pagination
    page_info = f"📄 ገጽ {page + 1}/{total_pages}" if total_pages > 1 else ""
    message = await update.message.reply_text(
        f"🔍 የፈለጉት '*{query}*'\n\n"
        f"{page_info}\n"
        "⬇️ የሚፈልጉትን ፊልም ይምረጡ:",
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


# Admin notifications removed - duplicates handled silently

async def handle_movie_channel_post(message, channel_id):
    """Handle new movie posts with quick pre-check and queue system"""
    if message.document or message.video:
        file_obj = message.document or message.video

        file_data = {
            'file_id': file_obj.file_id,
            'message_id': message.message_id,
            'file_unique_id': file_obj.file_unique_id,
            'file_name': getattr(file_obj, 'file_name', '') or '',
            'file_title': message.caption or '',
            'channel_id': channel_id,
            'file_size': getattr(file_obj, 'file_size', 0) or 0,
            'film_type': 'single'
        }

        # ⚡ QUICK PRE-CHECK (< 0.1s) - 100% exact match by name only
        if file_data['file_size'] > 0:
            import sqlite3
            with sqlite3.connect(config.SINGLE_DB_PATH) as conn:
                cursor = conn.cursor()
                
                # Quick name-only check for instant blocking
                cursor.execute('''
                    SELECT id, file_size FROM single_movies 
                    WHERE file_name = ? LIMIT 1
                ''', (file_data['file_name'],))
                
                existing = cursor.fetchone()
                
                if existing and existing[1] == file_data['file_size']:
                    # 100% exact match - INSTANT DELETE
                    try:
                        from telegram import Bot
                        bot = Bot(token=config.BOT_TOKEN)
                        await bot.delete_message(
                            chat_id=channel_id,
                            message_id=message.message_id
                        )
                        global instant_blocks_count
                        instant_blocks_count += 1
                        logger.info(f"⚡ INSTANT BLOCK: {file_data['file_name']} (Total: {instant_blocks_count})")
                        return False
                    except Exception as e:
                        logger.error(f"❌ Error deleting instant duplicate: {e}")

        # 📋 ADD TO BACKGROUND QUEUE for deep processing
        from background_worker import background_worker
        background_worker.add_to_queue(file_data)
        
        logger.info(f"✅ Queued for processing: {file_data['file_name']}")
        return True

    return False

# Global movie manager instance
movie_manager = SingleMovieManager()