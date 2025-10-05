
import sqlite3
import logging
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes
import config

logger = logging.getLogger(__name__)

class AllFilmManager:
    def __init__(self):
        pass

    def search_all_films(self, query):
        """Search both single movies and series databases"""
        results = []
        
        # Search single movies
        try:
            with sqlite3.connect(config.SINGLE_DB_PATH) as conn:
                cursor = conn.execute('''
                    SELECT file_id, file_name, file_title, 'movie' as type FROM single_movies 
                    WHERE file_name LIKE ? OR file_title LIKE ?
                    ORDER BY file_name ASC
                    LIMIT 25
                ''', (f'%{query}%', f'%{query}%'))
                results.extend(cursor.fetchall())
        except Exception as e:
            logger.error(f"Error searching single movies: {e}")

        # Search series
        try:
            with sqlite3.connect(config.SERIES_DB_PATH) as conn:
                cursor = conn.execute('''
                    SELECT file_id, file_name, file_title, 'series' as type FROM series 
                    WHERE file_name LIKE ? OR file_title LIKE ?
                    ORDER BY file_name ASC
                    LIMIT 25
                ''', (f'%{query}%', f'%{query}%'))
                results.extend(cursor.fetchall())
        except Exception as e:
            logger.error(f"Error searching series: {e}")

        # Sort all results alphabetically
        results.sort(key=lambda x: (x[1] or x[2] or "").lower())
        
        return results[:50]  # Limit to 50 total results

async def handle_all_film_search(update: Update, context: ContextTypes.DEFAULT_TYPE, query: str, page: int = 0):
    """Handle search across all films (both single and series)"""
    
    # Send searching status
    searching_msg = await update.message.reply_text("🔍 በሁሉም ፊልሞች ውስጥ እየፈለግሁ ነው...")

    all_film_manager = AllFilmManager()
    all_results = all_film_manager.search_all_films(query)

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
        return

    # Pagination settings
    per_page = 5
    total_pages = (len(all_results) + per_page - 1) // per_page

    # Get current page results
    start_idx = page * per_page
    end_idx = start_idx + per_page
    current_page_results = all_results[start_idx:end_idx]

    # Create inline keyboard with film options (5 per page)
    keyboard = []
    for i, (file_id, file_name, file_title, film_type) in enumerate(current_page_results):
        display_name = file_name if file_name else (file_title if file_title else f"ፋይል {start_idx + i + 1}")
        display_title = display_name[:45] + "..." if len(display_name) > 45 else display_name
        
        # Add emoji based on type
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

    # Store all results in user context for callback handling
    context.user_data['last_all_results'] = all_results
    context.user_data['all_search_query'] = query

    # Send the search results with pagination
    page_info = f"📄 ገጽ {page + 1}/{total_pages}" if total_pages > 1 else ""
    message = await update.message.reply_text(
        f"🎞 *የሁሉም ፊልም ፍለጋ ውጤት*\n\n"
        f"🔍 '*{query}*' ለሚል ፍለጋ *{len(all_results)}* ፊልሞች ተገኝተዋል!\n\n"
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

# Global instance
all_film_manager = AllFilmManager()
