
import sqlite3
import logging
from datetime import datetime
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes
import config

logger = logging.getLogger(__name__)

class UserBlockSystem:
    def __init__(self):
        self.setup_database()
    
    def setup_database(self):
        """Setup blocked users table"""
        with sqlite3.connect(config.USER_DB_PATH) as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS blocked_users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER UNIQUE NOT NULL,
                    username TEXT,
                    first_name TEXT,
                    blocked_by INTEGER NOT NULL,
                    block_reason TEXT,
                    blocked_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    unblocked_date TIMESTAMP,
                    unblock_date TIMESTAMP,
                    status TEXT DEFAULT 'blocked'
                )
            ''')
            
            # Add unblock_date column if not exists (for auto-unblock)
            try:
                conn.execute('ALTER TABLE blocked_users ADD COLUMN unblock_date TIMESTAMP')
            except sqlite3.OperationalError:
                pass  # Column already exists
            
            # Add is_blocked column to users table if not exists
            try:
                conn.execute('ALTER TABLE users ADD COLUMN is_blocked INTEGER DEFAULT 0')
            except sqlite3.OperationalError:
                pass  # Column already exists
    
    async def block_user(self, admin_id: int, user_id: int, reason: str = None, context=None):
        """Block a user permanently"""
        try:
            with sqlite3.connect(config.USER_DB_PATH) as conn:
                # Get user info
                cursor = conn.execute('''
                    SELECT username, first_name FROM users WHERE user_id = ?
                ''', (user_id,))
                user_info = cursor.fetchone()
                
                if not user_info:
                    return False, "❌ ተጠቃሚ አልተገኘም!"
                
                username, first_name = user_info
                
                # Check if user exists in blocked_users table
                cursor = conn.execute('''
                    SELECT id, status FROM blocked_users 
                    WHERE user_id = ?
                ''', (user_id,))
                
                existing = cursor.fetchone()
                
                if existing:
                    if existing[1] == 'blocked':
                        return False, "⚠️ ተጠቃሚ በቀደሙ ተገድቧል!"
                    
                    # User was previously blocked and unblocked - update existing record
                    conn.execute('''
                        UPDATE blocked_users 
                        SET status = 'blocked', 
                            blocked_by = ?,
                            block_reason = ?,
                            blocked_date = CURRENT_TIMESTAMP,
                            unblock_date = NULL,
                            username = ?,
                            first_name = ?
                        WHERE user_id = ?
                    ''', (admin_id, reason, username, first_name, user_id))
                else:
                    # New block - insert new record
                    conn.execute('''
                        INSERT INTO blocked_users 
                        (user_id, username, first_name, blocked_by, block_reason, unblock_date)
                        VALUES (?, ?, ?, ?, ?, NULL)
                    ''', (user_id, username, first_name, admin_id, reason))
                
                # Update users table
                conn.execute('''
                    UPDATE users SET is_blocked = 1 WHERE user_id = ?
                ''', (user_id,))
                
                conn.commit()
                
                # Send notification to blocked user
                if context:
                    try:
                        block_message = (
                            "🚫 የተገደበ መልእክት\n\n"
                            "የBot አገልግሎት ተገድበዋል።\n\n"
                        )
                        if reason:
                            block_message += f"📝 ምክንያት: {reason}\n\n"
                        block_message += "ለበለጠ መረጃ Admin ን ያነጋግሩ: @Henok_Chat"
                        
                        await context.bot.send_message(
                            chat_id=user_id,
                            text=block_message
                        )
                    except Exception as e:
                        logger.error(f"Error sending block notification to user {user_id}: {e}")
                
                display_name = f"@{username}" if username else first_name or f"User {user_id}"
                return True, f"✅ {display_name} ተገድቧል!"
                
        except Exception as e:
            logger.error(f"Error blocking user: {e}")
            return False, f"❌ Error: {str(e)}"
    
    async def block_user_temp(self, admin_id: int, user_id: int, reason: str = None, duration_hours: int = 24, context=None):
        """Block a user temporarily (for auto-blocks)"""
        from datetime import datetime, timedelta
        
        try:
            with sqlite3.connect(config.USER_DB_PATH) as conn:
                # Get user info
                cursor = conn.execute('''
                    SELECT username, first_name FROM users WHERE user_id = ?
                ''', (user_id,))
                user_info = cursor.fetchone()
                
                if not user_info:
                    return False, "❌ ተጠቃሚ አልተገኘም!"
                
                username, first_name = user_info
                unblock_date = (datetime.now() + timedelta(hours=duration_hours)).strftime('%Y-%m-%d %H:%M:%S')
                
                # Check if user exists in blocked_users table
                cursor = conn.execute('''
                    SELECT id, status FROM blocked_users 
                    WHERE user_id = ?
                ''', (user_id,))
                
                existing = cursor.fetchone()
                
                if existing:
                    # Update existing record
                    conn.execute('''
                        UPDATE blocked_users 
                        SET status = 'blocked', 
                            blocked_by = ?,
                            block_reason = ?,
                            blocked_date = CURRENT_TIMESTAMP,
                            unblock_date = ?,
                            username = ?,
                            first_name = ?
                        WHERE user_id = ?
                    ''', (admin_id, reason, unblock_date, username, first_name, user_id))
                else:
                    # New block - insert new record
                    conn.execute('''
                        INSERT INTO blocked_users 
                        (user_id, username, first_name, blocked_by, block_reason, unblock_date)
                        VALUES (?, ?, ?, ?, ?, ?)
                    ''', (user_id, username, first_name, admin_id, reason, unblock_date))
                
                # Update users table
                conn.execute('''
                    UPDATE users SET is_blocked = 1 WHERE user_id = ?
                ''', (user_id,))
                
                conn.commit()
                
                display_name = f"@{username}" if username else first_name or f"User {user_id}"
                return True, f"✅ {display_name} ለ{duration_hours} ሰአት ተገድቧል!"
                
        except Exception as e:
            logger.error(f"Error temp blocking user: {e}")
            return False, f"❌ Error: {str(e)}"
    
    async def unblock_user(self, admin_id: int, user_id: int, context=None):
        """Unblock a user"""
        try:
            with sqlite3.connect(config.USER_DB_PATH) as conn:
                # Check if user is blocked
                cursor = conn.execute('''
                    SELECT username, first_name FROM blocked_users 
                    WHERE user_id = ? AND status = 'blocked'
                ''', (user_id,))
                
                user_info = cursor.fetchone()
                if not user_info:
                    return False, "❌ ተጠቃሚ አልተገኘም ወይም በቀደሙ አልተገደበም!"
                
                username, first_name = user_info
                
                # Unblock user
                conn.execute('''
                    UPDATE blocked_users 
                    SET status = 'unblocked', unblocked_date = CURRENT_TIMESTAMP
                    WHERE user_id = ? AND status = 'blocked'
                ''', (user_id,))
                
                # Update users table
                conn.execute('''
                    UPDATE users SET is_blocked = 0 WHERE user_id = ?
                ''', (user_id,))
                
                conn.commit()
                
                # Send notification to unblocked user
                if context:
                    try:
                        await context.bot.send_message(
                            chat_id=user_id,
                            text=(
                                "✅ *ተላቀቁ!*\n\n"
                                "የBot አገልግሎት እንደገና መጠቀም ይችላሉ።\n\n"
                                "እንኳን ደህና ተመለሱ! 🎬"
                            ),
                            parse_mode='Markdown'
                        )
                    except Exception as e:
                        logger.error(f"Error sending unblock notification to user {user_id}: {e}")
                
                display_name = f"@{username}" if username else first_name or f"User {user_id}"
                return True, f"✅ {display_name} ተላቀቀ!"
                
        except Exception as e:
            logger.error(f"Error unblocking user: {e}")
            return False, f"❌ Error: {str(e)}"
    
    def is_user_blocked(self, user_id: int) -> bool:
        """Check if user is blocked - also auto-unblocks if time has expired"""
        try:
            with sqlite3.connect(config.USER_DB_PATH) as conn:
                cursor = conn.execute('''
                    SELECT id, unblock_date FROM blocked_users 
                    WHERE user_id = ? AND status = 'blocked'
                ''', (user_id,))
                result = cursor.fetchone()
                if result is None:
                    return False

                unblock_date = result[1]
                if unblock_date:
                    try:
                        unblock_dt = datetime.strptime(unblock_date, '%Y-%m-%d %H:%M:%S')
                        if datetime.now() >= unblock_dt:
                            conn.execute('''
                                UPDATE blocked_users 
                                SET status = 'unblocked', unblocked_date = CURRENT_TIMESTAMP
                                WHERE user_id = ? AND status = 'blocked'
                            ''', (user_id,))
                            conn.execute('''
                                UPDATE users SET is_blocked = 0 WHERE user_id = ?
                            ''', (user_id,))
                            conn.commit()
                            logger.info(f"✅ Auto-unblocked user {user_id} - block period expired")
                            return False
                    except ValueError:
                        pass

                return True
        except Exception as e:
            logger.error(f"Error checking block status: {e}")
            return False
    
    async def show_blocked_users(self, query, context, page=0):
        """Show list of blocked users with unblock buttons"""
        from datetime import datetime
        
        try:
            with sqlite3.connect(config.USER_DB_PATH) as conn:
                # Count total blocked users
                cursor = conn.execute('''
                    SELECT COUNT(*) FROM blocked_users WHERE status = 'blocked'
                ''')
                total = cursor.fetchone()[0]
                
                # Get paginated blocked users
                limit = 5
                offset = page * limit
                
                cursor = conn.execute('''
                    SELECT user_id, username, first_name, block_reason, blocked_date, unblock_date
                    FROM blocked_users
                    WHERE status = 'blocked'
                    ORDER BY blocked_date DESC
                    LIMIT ? OFFSET ?
                ''', (limit, offset))
                
                blocked_users = cursor.fetchall()
        except Exception as e:
            logger.error(f"Error fetching blocked users: {e}")
            await query.answer("❌ Error fetching data!")
            return
        
        text = f"🚫 የተገደቡ ተጠቃሚዎች (ጠቅላላ: {total})\n\n"
        
        keyboard = []
        
        if blocked_users:
            for user_id, username, first_name, reason, blocked_date, unblock_date in blocked_users:
                display_name = f"@{username}" if username else first_name or f"User {user_id}"
                date_str = blocked_date[:16] if blocked_date else "Unknown"
                reason_str = reason if reason else "No reason"
                
                # Check if auto-unblock is set
                if unblock_date:
                    try:
                        unblock_dt = datetime.strptime(unblock_date, '%Y-%m-%d %H:%M:%S')
                        now = datetime.now()
                        if unblock_dt > now:
                            time_left = unblock_dt - now
                            hours_left = int(time_left.total_seconds() / 3600)
                            text += f"👤 {display_name}\n"
                            text += f"   🆔 {user_id}\n"
                            text += f"   📝 {reason_str}\n"
                            text += f"   📅 {date_str}\n"
                            text += f"   ⏰ Auto-unblock in: {hours_left}h\n\n"
                        else:
                            text += f"👤 {display_name}\n"
                            text += f"   🆔 {user_id}\n"
                            text += f"   📝 {reason_str}\n"
                            text += f"   📅 {date_str}\n"
                            text += f"   ⏰ Auto-unblock: Expired\n\n"
                    except:
                        text += f"👤 {display_name}\n"
                        text += f"   🆔 {user_id}\n"
                        text += f"   📝 {reason_str}\n"
                        text += f"   📅 {date_str}\n\n"
                else:
                    text += f"👤 {display_name}\n"
                    text += f"   🆔 {user_id}\n"
                    text += f"   📝 {reason_str}\n"
                    text += f"   📅 {date_str}\n\n"
                
                # Add unblock button for each user
                keyboard.append([InlineKeyboardButton(
                    f"✅ {display_name} አላቀቅ", 
                    callback_data=f"quick_unblock_{user_id}"
                )])
        else:
            text += "ምንም የተገደቡ ተጠቃሚዎች የሉም።"
        
        # Pagination
        nav_buttons = []
        
        if page > 0:
            nav_buttons.append(InlineKeyboardButton("◀️ ቀዳሚ", callback_data=f"block_list_{page-1}"))
        
        if (page + 1) * limit < total:
            nav_buttons.append(InlineKeyboardButton("ቀጣይ ▶️", callback_data=f"block_list_{page+1}"))
        
        if nav_buttons:
            keyboard.append(nav_buttons)
        
        keyboard.append([InlineKeyboardButton("🔙 ወደ User Management", callback_data="admin_user_management")])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(text, reply_markup=reply_markup)
    
    async def show_block_interface(self, query, context):
        """Show block/unblock interface"""
        keyboard = [
            [InlineKeyboardButton("🚫 ተጠቃሚ አግድ", callback_data="block_user_prompt")],
            [InlineKeyboardButton("✅ ተጠቃሚ አላቀቅ", callback_data="unblock_user_prompt")],
            [InlineKeyboardButton("📋 የተገደቡ ዝርዝር", callback_data="block_list_0")],
            [InlineKeyboardButton("🔙 ወደ User Management", callback_data="admin_user_management")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        text = (
            "🚫 User Block Management\n\n"
            "ተጠቃሚዎችን ለማገድ ወይም ለማላቀቅ የሚከተሉትን ይምረጡ:"
        )
        
        await query.edit_message_text(text, reply_markup=reply_markup)

# Global instance
user_block_system = UserBlockSystem()
