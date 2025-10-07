import sqlite3
import logging
from telegram import Update
from telegram.ext import ContextTypes
import config
import asyncio

logger = logging.getLogger(__name__)

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
                    added_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')

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
                    LIMIT 50
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
        # Prioritize file_name over file_title for display
        display_name = file_name if file_name else (file_title if file_title else f"ፋይል {start_idx + i + 1}")
        # Limit title length for better display
        display_title = display_name[:45] + "..." if len(display_name) > 45 else display_name
        # Use actual index from all results for callback
        keyboard.append([InlineKeyboardButton(
            f"🎬 *{display_title}*", 
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

    # Store all results in user context for callback handling
    context.user_data['last_movie_results'] = all_results
    context.user_data['movie_search_query'] = query

    # Send the search results with pagination
    page_info = f"📄 ገጽ {page + 1}/{total_pages}" if total_pages > 1 else ""
    message = await update.message.reply_text(
        f"🎬 *የፊልም ፍለጋ ውጤት*\n\n"
        f"🔍 '*{query}*' ለሚል ፍለጋ *{len(all_results)}* ነጠላ ፊልሞች ተገኝተዋል!\n\n"
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


async def handle_movie_channel_post(message, channel_id):
    """Handle new movie posts in monitored channels"""
    movie_manager = SingleMovieManager()

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

        success = movie_manager.add_single_movie(**file_data)
        if success:
            logger.info(f"Added new movie: {file_data['file_name']} ({file_data['file_size']} bytes)")

        return success

    return False

# Global movie manager instance
movie_manager = SingleMovieManager()