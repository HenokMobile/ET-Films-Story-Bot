import sqlite3
import logging
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import MessageHandler, filters, CallbackQueryHandler, ContextTypes
import config
from database import db
from datetime import datetime

logger = logging.getLogger(__name__)

class AdminPanel:
    def __init__(self):
        self.user_states = {}

    def update_config_file(self, key, value):
        """Update config file with new value"""
        try:
            import re

            with open('config.py', 'r', encoding='utf-8') as f:
                content = f.read()

            # Update the specific line with proper formatting
            pattern = f'^{key}\\s*=.*$'
            replacement = f'{key} = {repr(value)}'

            # Use re.sub to replace the line
            updated_content = re.sub(pattern, replacement, content, flags=re.MULTILINE)

            # If the key wasn't found, it means it doesn't exist, so we add it
            if key not in content: # Corrected check to look for key directly
                updated_content += f'\n{key} = {repr(value)}\n'

            # Write back to file
            with open('config.py', 'w', encoding='utf-8') as f:
                f.write(updated_content)

            logger.info(f"Updated config file: {key} = {value}")

            # Reload the config module to reflect changes
            import importlib
            import config as config_module
            importlib.reload(config_module)

        except Exception as e:
            logger.error(f"Failed to update config file: {e}")

    async def show_admin_panel(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show main admin panel"""
        user = update.effective_user

        if user.id != config.ADMIN_USER_ID:
            await update.message.reply_text("❌ የAdmin መብት የለዎትም!")
            return

        keyboard = [
            [InlineKeyboardButton("📺 ቻነል ቅንብሮች", callback_data="admin_channels")],
            [InlineKeyboardButton("💰 ሂሳብ ለመቆጣጠር", callback_data="admin_finance")],
            [InlineKeyboardButton("👥 የተጠቃሚዎች አስተዳደር", callback_data="admin_user_management")],
            [InlineKeyboardButton("📊 የተጠቃሚዎች ስታቲስቲክስ", callback_data="admin_users")],
            [InlineKeyboardButton("🎬 የፊልም ስታቲስቲክስ", callback_data="admin_movies")],
            [InlineKeyboardButton("🎁 የግብዣ ስታቲስቲክስ", callback_data="admin_referrals")],
            [InlineKeyboardButton("⚙️ የቦት ቅንብሮች", callback_data="admin_settings")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(
            "🔧 **Admin Panel**\n\n"
            "ምን ማድረግ ይፈልጋሉ?",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )

    async def handle_admin_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle admin panel callbacks"""
        query = update.callback_query
        await query.answer()



    def get_duplicate_stats_from_logs(self):
        """Extract duplicate statistics from log files"""
        import re
        from datetime import datetime, timedelta
        import os

        try:
            stats = {'today': 0, 'week': 0, 'total': 0}

            # Patterns for duplicate detection
            log_patterns = [
                r'🗑️ Deleted duplicate from channel:',
                r'🚫 Duplicate BLOCKED from database:',
                r'⚡ INSTANT BLOCK:'
            ]

            now = datetime.now()
            today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
            week_start = now - timedelta(days=7)

            # Search in multiple locations
            log_locations = [
                '.',           # Current directory
                'bot/',        # Bot directory
                '../',         # Parent directory
            ]

            found_logs = False

            for location in log_locations:
                if not os.path.exists(location):
                    continue

                try:
                    log_files = [f for f in os.listdir(location) if f.endswith('.log')]

                    for log_file in log_files:
                        found_logs = True
                        full_path = os.path.join(location, log_file)

                        with open(full_path, 'r', encoding='utf-8', errors='ignore') as f:
                            for line in f:
                                # Check if line contains any duplicate pattern
                                is_duplicate = any(pattern in line for pattern in log_patterns)

                                if is_duplicate:
                                    stats['total'] += 1

                                    # Parse timestamp - multiple formats
                                    timestamp_patterns = [
                                        r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})',  # 2025-01-09 08:19:38
                                        r'(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})',  # ISO format
                                    ]

                                    for ts_pattern in timestamp_patterns:
                                        timestamp_match = re.search(ts_pattern, line)
                                        if timestamp_match:
                                            try:
                                                ts_str = timestamp_match.group(1)
                                                # Try both formats
                                                for fmt in ['%Y-%m-%d %H:%M:%S', '%Y-%m-%dT%H:%M:%S']:
                                                    try:
                                                        log_time = datetime.strptime(ts_str, fmt)
                                                        if log_time >= today_start:
                                                            stats['today'] += 1
                                                        if log_time >= week_start:
                                                            stats['week'] += 1
                                                        break
                                                    except:
                                                        continue
                                                break
                                            except:
                                                continue
                except Exception as e:
                    logger.debug(f"Could not read logs from {location}: {e}")
                    continue

            if not found_logs:
                logger.warning("⚠️ No log files found for duplicate stats")

            return stats

        except Exception as e:
            logger.error(f"Error getting duplicate stats: {e}")
            return {'today': 0, 'week': 0, 'total': 0}

    async def handle_admin_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle admin panel callbacks"""
        query = update.callback_query
        await query.answer()

        if query.from_user.id != config.ADMIN_USER_ID:
            await query.edit_message_text("❌ የAdmin መብት የለዎትም!")
            return

        data = query.data

        if data == "admin_channels":
            await self.show_channel_settings(query, context)
        elif data == "manage_single_channels":
            await self.show_single_channels_menu(query, context)
        elif data == "manage_series_channels":
            await self.show_series_channels_menu(query, context)
        elif data == "add_single_channel":
            await self.request_single_channel_id(query, context)
        elif data == "add_series_channel":
            await self.request_series_channel_id(query, context)
        elif data.startswith("remove_single_"):
            channel_id = int(data.replace("remove_single_", ""))
            await self.remove_single_channel(query, context, channel_id)
        elif data.startswith("remove_series_"):
            channel_id = int(data.replace("remove_series_", ""))
            await self.remove_series_channel(query, context, channel_id)
        elif data == "admin_finance":
            from admin_balance import admin_balance
            await admin_balance.show_finance_dashboard(query, context)
        elif data == "finance_pending":
            from admin_balance import admin_balance
            await admin_balance.show_pending_payments_detailed(query, context)
        elif data == "finance_approved" or data == "balance_approved_payments":
            from admin_balance import admin_balance
            await admin_balance.show_approved_payments(query, context)
        elif data == "finance_rejected" or data == "balance_rejected_payments":
            from admin_balance import admin_balance
            await admin_balance.show_rejected_payments(query, context)
        elif data == "finance_user_management":
            from admin_balance import admin_balance
            await admin_balance.show_user_balance_search(query, context)
        elif data.startswith("finance_pending_page_"):
            page = int(data.replace("finance_pending_page_", ""))
            await self.show_pending_payments(query, context, page)
        elif data.startswith("finance_approved_page_"):
            page = int(data.replace("finance_approved_page_", ""))
            await self.show_approved_payments(query, context, page)
        elif data.startswith("finance_rejected_page_") or data.startswith("balance_rejected_page_"):
            if data.startswith("finance_rejected_page_"):
                page = int(data.replace("finance_rejected_page_", ""))
            else:
                page = int(data.replace("balance_rejected_page_", ""))
            from admin_balance import admin_balance
            await admin_balance.show_rejected_payments(query, context, page)
        elif data.startswith("balance_approved_page_"):
            page = int(data.replace("balance_approved_page_", ""))
            from admin_balance import admin_balance
            await admin_balance.show_approved_payments(query, context, page)
        elif data.startswith("message_user_"):
            await self.handle_message_user(query, context)
        elif data == "admin_users":
            await self.show_user_statistics(query, context)
        elif data == "admin_movies":
            await self.show_movie_statistics(query, context)
        elif data == "admin_series":
            await self.show_series_statistics(query, context)
        elif data == "admin_settings":
            await self.show_bot_settings(query, context)
        elif data == "admin_finance":
            from admin_balance import admin_balance
            await admin_balance.show_finance_dashboard(query, context)
        elif data.startswith("confirm_single_delete_"):
            channel_id = data.replace("confirm_single_delete_", "")
            await self.execute_single_db_cleanup(query, context, channel_id)
        elif data.startswith("confirm_series_delete_"):
            channel_id = data.replace("confirm_series_delete_", "")
            await self.execute_series_db_cleanup(query, context, channel_id)
        elif data.startswith("confirm_duplicate_delete_"):
            channel_id = data.replace("confirm_duplicate_delete_", "")
            await self.execute_duplicate_cleanup(query, context, channel_id)
        elif data == "back_to_channels":
            await self.show_channel_settings(query, context)
        elif data == "back_to_admin":
            await self.show_admin_main_menu(query, context)
        elif data == "admin_referrals":
            await self.show_referral_statistics(query, context)
        elif data == "admin_user_management":
            await self.show_user_management(query, context)
        elif data == "admin_user_list":
            await self.show_user_list(query, context, page=0)
        elif data.startswith("user_list_"):
            page = int(data.replace("user_list_", ""))
            await self.show_user_list(query, context, page)
        elif data == "admin_block_system":
            from user_block import user_block_system
            await user_block_system.show_block_interface(query, context)
        elif data.startswith("block_list_"):
            from user_block import user_block_system
            page = int(data.replace("block_list_", ""))
            await user_block_system.show_blocked_users(query, context, page)
        elif data == "block_user_prompt":
            await query.edit_message_text(
                "🚫 **ተጠቃሚ ለማገድ**\n\n"
                "እባክዎ የተጠቃሚውን ID ያስገቡ:",
                parse_mode='Markdown'
            )
            self.user_states[query.from_user.id] = "WAITING_BLOCK_USER_ID"
        elif data == "unblock_user_prompt":
            await query.edit_message_text(
                "✅ **ተጠቃሚ ለማላቀቅ**\n\n"
                "እባክዎ የተጠቃሚውን ID ያስገቡ:",
                parse_mode='Markdown'
            )
            self.user_states[query.from_user.id] = "WAITING_UNBLOCK_USER_ID"
        elif data.startswith("quick_unblock_"):
            from user_block import user_block_system
            user_id = int(data.replace("quick_unblock_", ""))
            
            success, message = await user_block_system.unblock_user(query.from_user.id, user_id, context)
            await query.answer(message, show_alert=True)
            
            # Refresh the blocked users list
            await user_block_system.show_blocked_users(query, context, page=0)


    async def show_channel_settings(self, query, context):
        """Show channel settings menu"""
        keyboard = [
            [InlineKeyboardButton("🎬 ነጠላ ፊልም Channels", callback_data="manage_single_channels")],
            [InlineKeyboardButton("📽 ተከታታይ ፊልም Channels", callback_data="manage_series_channels")],
            [InlineKeyboardButton("🔙 ወደ Admin Panel", callback_data="back_to_admin")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        # Get channels count
        single_count = len(config.SINGLE_MOVIE_CHANNEL_IDS)
        series_count = len(config.SERIES_CHANNEL_IDS)

        text = (
            "📺 **Channel Settings**\n\n"
            f"🎬 ነጠላ ፊልም: {single_count} channels\n"
            f"📽 ተከታታይ ፊልም: {series_count} channels\n\n"
            "የትኛውን ማስተካከል ይፈልጋሉ?"
        )

        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')

    async def show_user_statistics(self, query, context):
        """Show comprehensive user statistics"""
        try:
            with sqlite3.connect(config.USER_DB_PATH) as conn:
                # Basic user counts
                cursor = conn.execute("SELECT COUNT(*) FROM users")
                total_users = cursor.fetchone()[0]

                cursor = conn.execute("""
                    SELECT COUNT(*) FROM users 
                    WHERE joined_date >= date('now', '-1 day')
                """)
                today_users = cursor.fetchone()[0]

                cursor = conn.execute("""
                    SELECT COUNT(*) FROM users 
                    WHERE joined_date >= date('now', '-7 days')
                """)
                week_users = cursor.fetchone()[0]

                # Total balance statistics
                cursor = conn.execute("SELECT COALESCE(SUM(balance), 0) FROM users")
                total_balance = cursor.fetchone()[0]

                cursor = conn.execute("SELECT COALESCE(AVG(balance), 0) FROM users WHERE balance > 0")
                avg_balance = cursor.fetchone()[0]

                cursor = conn.execute("SELECT COUNT(*) FROM users WHERE balance = 0")
                zero_balance_count = cursor.fetchone()[0]

                # Highest balance user
                cursor = conn.execute("""
                    SELECT user_id, username, first_name, balance 
                    FROM users 
                    ORDER BY balance DESC 
                    LIMIT 1
                """)
                highest_balance_user = cursor.fetchone()

                # Get payment statistics
                cursor = conn.execute("""
                    SELECT COUNT(*), COALESCE(SUM(amount), 0) 
                    FROM payments 
                    WHERE status = 'approved'
                """)
                payment_stats = cursor.fetchone()
                total_purchases = payment_stats[0] if payment_stats else 0
                total_deposited = payment_stats[1] if payment_stats else 0

                # Top 5 users by approved deposits
                cursor = conn.execute("""
                    SELECT u.user_id, u.username, u.first_name, COALESCE(SUM(p.amount), 0) as total_deposit
                    FROM users u
                    LEFT JOIN payments p ON u.user_id = p.user_id AND p.status = 'approved'
                    GROUP BY u.user_id
                    ORDER BY total_deposit DESC
                    LIMIT 5
                """)
                top_depositors = cursor.fetchall()

                # Top 5 referrers
                cursor = conn.execute("""
                    SELECT user_id, username, first_name, referral_count, total_referral_earnings
                    FROM users
                    WHERE referral_count > 0
                    ORDER BY referral_count DESC
                    LIMIT 5
                """)
                top_referrers = cursor.fetchall()

        except Exception as e:
            logger.error(f"Error fetching user statistics: {e}")
            total_users = today_users = week_users = 0
            total_balance = avg_balance = zero_balance_count = 0
            highest_balance_user = None
            total_purchases = total_deposited = 0
            top_depositors = []
            top_referrers = []

        # Format highest balance user
        if highest_balance_user:
            if highest_balance_user[1]:
                hb_name = f"@{highest_balance_user[1]}"
            elif highest_balance_user[2]:
                hb_name = highest_balance_user[2]
            else:
                hb_name = f"User {highest_balance_user[0]}"
            highest_balance_text = f"{hb_name} - {highest_balance_user[3]:,} ብር"
        else:
            highest_balance_text = "መረጃ የለም"

        # Format top depositors
        top_depositors_text = ""
        if top_depositors:
            for i, (uid, uname, fname, total) in enumerate(top_depositors, 1):
                if uname:
                    name = f"@{uname}"
                elif fname:
                    name = fname
                else:
                    name = f"User {uid}"
                if total > 0:
                    top_depositors_text += f"{i}. {name} - {total:,} ብር\n"
        if not top_depositors_text:
            top_depositors_text = "ገና የተገባ ገንዘብ የለም\n"

        # Format top referrers
        top_referrers_text = ""
        if top_referrers:
            for i, (uid, uname, fname, ref_count, earnings) in enumerate(top_referrers, 1):
                if uname:
                    name = f"@{uname}"
                elif fname:
                    name = fname
                else:
                    name = f"User {uid}"
                top_referrers_text += f"{i}. {name} - {ref_count} ግብዣዎች ({earnings} ብር)\n"
        if not top_referrers_text:
            top_referrers_text = "ገና ምንም referral የለም\n"

        keyboard = [[InlineKeyboardButton("🔙 ወደ Admin Panel", callback_data="back_to_admin")]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        text = (
            "👥 የተጠቃሚዎች ስታቲስቲክስ\n\n"
            "━━━━━━━━━━━━━━━━━━━\n"
            "📊 የተጠቃሚ መረጃ:\n"
            f"• ጠቅላላ ተጠቃሚዎች: {total_users:,}\n"
            f"• ዛሬ የተቀላቀሉ: {today_users:,}\n"
            f"• በዚህ ሳምንት: {week_users:,}\n\n"
            "━━━━━━━━━━━━━━━━━━━\n"
            "💰 የገንዘብ መረጃ:\n"
            f"• ጠቅላላ balance: {total_balance:,} ብር\n"
            f"• አማካይ balance: {int(avg_balance):,} ብር\n"
            f"• Highest balance: {highest_balance_text}\n"
            f"• Zero balance users: {zero_balance_count:,}\n\n"
            "━━━━━━━━━━━━━━━━━━━\n"
            "💸 የገቢ መረጃ:\n"
            f"• ጠቅላላ የገባ ገንዘብ: {total_deposited:,} ብር\n"
            f"• ጠቅላላ deposits: {total_purchases:,}\n\n"
            "━━━━━━━━━━━━━━━━━━━\n"
            "👑 Top 5 Depositors:\n"
            f"{top_depositors_text}\n"
            "━━━━━━━━━━━━━━━━━━━\n"
            "🎁 Top 5 Referrers:\n"
            f"{top_referrers_text}"
        )

        await query.edit_message_text(text, reply_markup=reply_markup)

    async def show_movie_statistics(self, query, context):
        """Show combined movie and series statistics with file size and downloads"""
        try:
            # Single movies stats
            with sqlite3.connect(config.SINGLE_DB_PATH) as conn:
                cursor = conn.execute("SELECT COUNT(*), COALESCE(SUM(file_size), 0) FROM single_movies")
                single_data = cursor.fetchone()
                total_movies = single_data[0] or 0
                total_movie_size = single_data[1] or 0

                cursor = conn.execute("""
                    SELECT COUNT(*) FROM single_movies 
                    WHERE joined_date >= date('now', '-1 day')
                """)
                today_movies = cursor.fetchone()[0] or 0

                cursor = conn.execute("""
                    SELECT COUNT(*) FROM single_movies 
                    WHERE joined_date >= date('now', '-7 days')
                """)
                week_movies = cursor.fetchone()[0] or 0

            # Series stats
            with sqlite3.connect(config.SERIES_DB_PATH) as conn:
                cursor = conn.execute("SELECT COUNT(*), COALESCE(SUM(file_size), 0) FROM series")
                series_data = cursor.fetchone()
                total_series = series_data[0] or 0
                total_series_size = series_data[1] or 0

                cursor = conn.execute("""
                    SELECT COUNT(*) FROM series 
                    WHERE joined_date >= date('now', '-1 day')
                """)
                today_series = cursor.fetchone()[0] or 0

                cursor = conn.execute("""
                    SELECT COUNT(*) FROM series 
                    WHERE joined_date >= date('now', '-7 days')
                """)
                week_series = cursor.fetchone()[0] or 0

            # Download stats
            with sqlite3.connect(config.USER_DB_PATH) as conn:
                cursor = conn.execute("""
                    SELECT COUNT(*) FROM download_logs 
                    WHERE download_date >= date('now', '-1 day')
                """)
                today_downloads = cursor.fetchone()[0] or 0

                cursor = conn.execute("""
                    SELECT COUNT(*) FROM download_logs 
                    WHERE download_date >= date('now', '-7 days')
                """)
                week_downloads = cursor.fetchone()[0] or 0

                cursor = conn.execute("SELECT COUNT(*) FROM download_logs")
                total_downloads = cursor.fetchone()[0] or 0

                # Top downloaded movies
                cursor = conn.execute("""
                    SELECT file_name, COUNT(*) as count 
                    FROM download_logs 
                    WHERE file_name IS NOT NULL
                    GROUP BY file_id 
                    ORDER BY count DESC 
                    LIMIT 5
                """)
                top_downloads = cursor.fetchall()

            # Background Worker stats
            from background_worker import background_worker
            worker_stats = background_worker.get_stats()

            # Get instant block count from single.py and series.py
            from single import instant_blocks_count as single_instant_blocks
            from series import instant_blocks_count as series_instant_blocks

            # Total duplicates = background worker blocks + instant blocks
            total_duplicates = worker_stats.get('duplicates_blocked', 0) + single_instant_blocks + series_instant_blocks

        except Exception as e:
            logger.error(f"Error fetching movie statistics: {e}")
            total_movies = today_movies = week_movies = 0
            total_series = today_series = week_series = 0
            total_movie_size = total_series_size = 0
            today_downloads = week_downloads = total_downloads = 0
            top_downloads = []
            total_duplicates = 0
            worker_stats = {'queue_size': 0, 'processed': 0, 'duplicates_blocked': 0, 'errors': 0}

        # Calculate sizes in GB/MB
        total_size_bytes = total_movie_size + total_series_size
        if total_size_bytes >= 1073741824:  # >= 1GB
            total_size_str = f"{total_size_bytes / 1073741824:.2f} GB"
        else:
            total_size_str = f"{total_size_bytes / 1048576:.2f} MB"

        avg_size = (total_movie_size + total_series_size) / (total_movies + total_series) if (total_movies + total_series) > 0 else 0
        avg_size_str = f"{avg_size / 1048576:.2f} MB" if avg_size > 0 else "0 MB"

        # Top downloads text
        top_downloads_text = ""
        if top_downloads:
            for i, (name, count) in enumerate(top_downloads, 1):
                display_name = name[:30] + "..." if name and len(name) > 30 else (name or "Unknown")
                top_downloads_text += f"{i}. {display_name} - {count} ×\n"
        else:
            top_downloads_text = "ገና የታወቁ downloads የሉም\n"

        keyboard = [[InlineKeyboardButton("🔙 ወደ Admin Panel", callback_data="back_to_admin")]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        text = (
            "🎬 የፊልም ስታቲስቲክስ\n\n"
            "━━━━━━━━━━━━━━━━━━━\n"
            "📊 የፊልም ብዛት:\n"
            f"• ጠቅላላ ነጠላ ፊልሞች: {total_movies:,}\n"
            f"• ጠቅላላ ተከታታይ ፊልሞች: {total_series:,}\n"
            f"• ዛሬ የተጨመሩ: {today_movies + today_series:,}\n"
            f"• በሳምንት የተጨመሩ: {week_movies + week_series:,}\n\n"
            "━━━━━━━━━━━━━━━━━━━\n"
            "💾 የStorage መረጃ:\n"
            f"• ጠቅላላ File Size: {total_size_str}\n"
            f"• አማካይ File Size: {avg_size_str}\n\n"
            "━━━━━━━━━━━━━━━━━━━\n"
            "🔄 Background Worker:\n"
            f"• Queue Size: {worker_stats['queue_size']:,}\n"
            f"• Processed: {worker_stats['processed']:,}\n"
            f"• Duplicates Blocked: {worker_stats['duplicates_blocked']:,}\n"
            f"• Errors: {worker_stats['errors']:,}\n\n"
            "━━━━━━━━━━━━━━━━━━━\n"
            "🚫 የDuplicate መከላከያ:\n"
            f"• ⚡ Instant Blocks (ነጠላ): {single_instant_blocks:,}\n"
            f"• ⚡ Instant Blocks (ተከታታይ): {series_instant_blocks:,}\n"
            f"• 🗑️ Queue Blocks: {worker_stats['duplicates_blocked']:,}\n"
            f"• ጠቅላላ የታገዱ: {total_duplicates:,}\n\n"
            "━━━━━━━━━━━━━━━━━━━\n"
            "📈 የDownload ስታቲስቲክስ:\n"
            f"• ዛሬ የተላኩ ፊልሞች: {today_downloads:,}\n"
            f"• በሳምንት የተላኩ: {week_downloads:,}\n"
            f"• ጠቅላላ Downloads: {total_downloads:,}\n\n"
            "━━━━━━━━━━━━━━━━━━━\n"
            "🏆 Top 5 Downloaded:\n"
            f"{top_downloads_text}"
        )

        await query.edit_message_text(text, reply_markup=reply_markup)

    async def show_series_statistics(self, query, context):
        """Redirect to combined movie statistics"""
        await self.show_movie_statistics(query, context)

    async def show_referral_statistics(self, query, context):
        """Show referral statistics"""
        try:
            with sqlite3.connect(config.USER_DB_PATH) as conn:
                # Total successful referrals (users who have a referrer)
                cursor = conn.execute("SELECT COUNT(*) FROM users WHERE referrer_id IS NOT NULL")
                total_referrals = cursor.fetchone()[0]

                # Total referral earnings across all users
                cursor = conn.execute("SELECT COALESCE(SUM(total_referral_earnings), 0) FROM users")
                total_earnings = cursor.fetchone()[0]

                # Top 10 referrers by referral count
                cursor = conn.execute("""
                    SELECT user_id, username, first_name, referral_count, total_referral_earnings
                    FROM users
                    WHERE referral_count > 0
                    ORDER BY referral_count DESC
                    LIMIT 10
                """)
                top_referrers_data = cursor.fetchall()

                top_referrers_list = []
                if top_referrers_data:
                    for rank, (user_id, username, first_name, ref_count, earnings) in enumerate(top_referrers_data, 1):
                        # Choose display name
                        if username:
                            name = f"@{username}"
                        elif first_name:
                            name = first_name
                        else:
                            name = f"User {user_id}"

                        top_referrers_list.append(
                            f"{rank}. {name}\n"
                            f"   👥 {ref_count} ግብዣዎች | 💰 {earnings} ብር"
                        )
                else:
                    top_referrers_list.append("ገና ምንም የግብዣ መረጃ የለም")

                top_referrers_text = "\n\n".join(top_referrers_list)

        except Exception as e:
            logger.error(f"Error fetching referral statistics: {e}")
            total_referrals = 0
            total_earnings = 0
            top_referrers_text = "መረጃ ማግኘት አልተቻለም"

        keyboard = [[InlineKeyboardButton("🔙 ወደ Admin Panel", callback_data="back_to_admin")]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        text = (
            "🎁 የግብዣ ስርዓት ስታቲስቲክስ\n\n"
            f"📊 ጠቅላላ የተሳኩ ግብዣዎች: {total_referrals}\n"
            f"💰 ጠቅላላ የተገኘ ገንዘብ: {total_earnings} ብር\n\n"
            f"━━━━━━━━━━━━━━━━━━━\n\n"
            f"🏆 Top 10 Referrers:\n\n{top_referrers_text}"
        )

        await query.edit_message_text(text, reply_markup=reply_markup)

    async def show_bot_settings(self, query, context):
        """Show bot settings"""
        keyboard = [[InlineKeyboardButton("🔙 ወደ Admin Panel", callback_data="back_to_admin")]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        text = (
            "⚙️ Bot Settings\n\n"
            f"🤖 Bot Token: {config.BOT_TOKEN[:10]}...\n"
            f"👑 Admin ID: {config.ADMIN_USER_ID}\n"
            f"💾 Database Status: ✅ Active"
        )

        await query.edit_message_text(text, reply_markup=reply_markup)

    async def show_admin_main_menu(self, query, context):
        """Show main admin menu"""
        keyboard = [
            [InlineKeyboardButton("📺 ቻነል ቅንብሮች", callback_data="admin_channels")],
            [InlineKeyboardButton("💰 ሂሳብ ለመቆጣጠር", callback_data="admin_finance")],
            [InlineKeyboardButton("👥 የተጠቃሚዎች አስተዳደር", callback_data="admin_user_management")],
            [InlineKeyboardButton("📊 የተጠቃሚዎች ስታቲስቲክስ", callback_data="admin_users")],
            [InlineKeyboardButton("🎬 የፊልም ስታቲስቲክስ", callback_data="admin_movies")],
            [InlineKeyboardButton("🎁 የግብዣ ስታቲስቲክስ", callback_data="admin_referrals")],
            [InlineKeyboardButton("⚙️ የቦት ቅንብሮች", callback_data="admin_settings")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.edit_message_text(
            "🔧 Admin Panel\n\n"
            "ምን ማድረግ ይፈልጋሉ?",
            reply_markup=reply_markup
        )

    async def get_channel_info(self, context, channel_id):
        """Get channel information including username/title"""
        try:
            chat = await context.bot.get_chat(channel_id)
            if chat.username:
                return f"@{chat.username}"
            elif chat.title:
                return chat.title
            else:
                return f"ID: {channel_id}"
        except:
            return f"ID: {channel_id}"

    async def resolve_channel_id(self, context, identifier):
        """Resolve channel ID from username or ID string"""
        try:
            if identifier.startswith("@"):
                chat = await context.bot.get_chat(identifier)
                return chat.id, await self.get_channel_info(context, chat.id) # Return cleaned info
            else:
                channel_id = int(identifier)
                # Fetch chat to confirm it's a valid channel and get info
                chat = await context.bot.get_chat(channel_id)
                return channel_id, await self.get_channel_info(context, channel_id) # Return cleaned info
        except ValueError:
            return None, "Invalid ID format"
        except Exception as e:
            logger.error(f"Error resolving channel ID: {e}")
            return None, str(e)


    async def check_bot_admin_in_channel(self, context, channel_id, user_id):
        """Check if bot and user are admins in the channel"""
        try:
            # Check if bot is admin
            bot_member = await context.bot.get_chat_member(channel_id, context.bot.id)
            if bot_member.status not in ['administrator', 'creator']:
                return False, "❌ Bot በዚህ Channel ውስጥ Admin አይደለም!"

            # Check if user is admin  
            user_member = await context.bot.get_chat_member(channel_id, user_id)
            if user_member.status not in ['administrator', 'creator']:
                return False, "❌ እርስዎ በዚህ Channel ውስጥ Admin አይደሉም!"

            return True, "✅ Validation ተሳክቷል"

        except Exception as e:
            logger.error(f"Failed to check admin status: {e}")
            return False, "❌ Channel ማረጋገጥ አልተቻለም! Channel ID ትክክል መሆኑን ያረጋግጡ።"

    async def show_single_channels_menu(self, query, context):
        """Show single movie channels management menu"""
        keyboard = [[InlineKeyboardButton("➕ Channel ጨምር", callback_data="add_single_channel")]]

        # Add existing channels with remove buttons
        for channel_id in config.SINGLE_MOVIE_CHANNEL_IDS:
            channel_info = await self.get_channel_info(context, channel_id)
            keyboard.append([InlineKeyboardButton(f"❌ Remove {channel_info}", callback_data=f"remove_single_{channel_id}")])

        keyboard.append([InlineKeyboardButton("🔙 ወደ Channel Settings", callback_data="back_to_channels")])
        reply_markup = InlineKeyboardMarkup(keyboard)

        # Build channels text with info
        channels_list = []
        for channel_id in config.SINGLE_MOVIE_CHANNEL_IDS:
            channel_info = await self.get_channel_info(context, channel_id)
            channels_list.append(f"• {channel_info} (ID: {channel_id})")

        channels_text = "\n".join(channels_list) if config.SINGLE_MOVIE_CHANNEL_IDS else "ምንም Channel የለም"

        text = (
            "🎬 ነጠላ ፊልም Channels\n\n"
            f"የአሁኑ Channels:\n{channels_text}\n\n"
            "ምን ማድረግ ይፈልጋሉ?"
        )

        await query.edit_message_text(text, reply_markup=reply_markup)

    async def show_series_channels_menu(self, query, context):
        """Show series channels management menu"""
        keyboard = [[InlineKeyboardButton("➕ Channel ጨምር", callback_data="add_series_channel")]]

        # Add existing channels with remove buttons
        for channel_id in config.SERIES_CHANNEL_IDS:
            channel_info = await self.get_channel_info(context, channel_id)
            keyboard.append([InlineKeyboardButton(f"❌ Remove {channel_info}", callback_data=f"remove_series_{channel_id}")])

        keyboard.append([InlineKeyboardButton("🔙 ወደ Channel Settings", callback_data="back_to_channels")])
        reply_markup = InlineKeyboardMarkup(keyboard)

        # Build channels text with info
        channels_list = []
        for channel_id in config.SERIES_CHANNEL_IDS:
            channel_info = await self.get_channel_info(context, channel_id)
            channels_list.append(f"• {channel_info} (ID: {channel_id})")

        channels_text = "\n".join(channels_list) if config.SERIES_CHANNEL_IDS else "ምንም Channel የለም"

        text = (
            "📽 ተከታታይ ፊልም Channels\n\n"
            f"የአሁኑ Channels:\n{channels_text}\n\n"
            "ምን ማድረግ ይፈልጋሉ?"
        )

        await query.edit_message_text(text, reply_markup=reply_markup)

    async def request_single_channel_id(self, query, context):
        """Request single movie channel ID"""
        await query.edit_message_text(
            "🎬 **ነጠላ ፊልም Channel ID ጨምር**\n\n"
            "እባክዎ የነጠላ ፊልም Channel ID ያስገቡ:\n"
            "(ምሳሌ: -1001234567890)"
        )
        self.user_states[query.from_user.id] = "WAITING_SINGLE_CHANNEL_ID"

    async def request_series_channel_id(self, query, context):
        """Request series channel ID"""
        await query.edit_message_text(
            "📽 **ተከታታይ ፊልም Channel ID ጨምር**\n\n"
            "እባክዎ የተከታታይ ፊልም Channel ID ወይም Username ያስገቡ:\n"
            "(ምሳሌ: -1001234567890 or @channelname)"
        )
        self.user_states[query.from_user.id] = "WAITING_SERIES_CHANNEL_ID"

    async def remove_single_channel(self, query, context, channel_id):
        """Remove single movie channel"""
        if channel_id in config.SINGLE_MOVIE_CHANNEL_IDS:
            # Create a new list without the channel_id
            updated_list = [ch_id for ch_id in config.SINGLE_MOVIE_CHANNEL_IDS if ch_id != channel_id]
            config.SINGLE_MOVIE_CHANNEL_IDS[:] = updated_list  # Update the original list

            # Save to config file
            self.update_config_file('SINGLE_MOVIE_CHANNEL_IDS', updated_list)

            await query.answer("✅ Channel ተወግዷል!")
            await self.show_single_channels_menu(query, context)
        else:
            await query.answer("❌ Channel አልተገኘም!")

    async def remove_series_channel(self, query, context, channel_id):
        """Remove series channel"""
        if channel_id in config.SERIES_CHANNEL_IDS:
            # Create a new list without the channel_id
            updated_list = [ch_id for ch_id in config.SERIES_CHANNEL_IDS if ch_id != channel_id]
            config.SERIES_CHANNEL_IDS[:] = updated_list  # Update the original list

            # Save to config file
            self.update_config_file('SERIES_CHANNEL_IDS', updated_list)

            await query.answer("✅ Channel ተወግዷል!")
            await self.show_series_channels_menu(query, context)
        else:
            await query.answer("❌ Channel አልተገኘም!")

    async def handle_admin_balance_callbacks(self, query, context, data):
        """Handle admin balance callbacks"""
        from admin_balance import admin_balance

        # Map callbacks to admin_balance methods
        callback_map = {
            "balance_pending_payments": admin_balance.show_pending_payments_detailed,
            "balance_approved_payments": admin_balance.show_approved_payments,
            "balance_rejected_payments": admin_balance.show_rejected_payments,
            "balance_user_management": admin_balance.show_user_balance_search,
            "balance_reports": admin_balance.show_balance_reports,
            "balance_alerts": admin_balance.show_balance_alerts,
            "balance_bulk_operations": admin_balance.show_bulk_operations,
            "balance_settings": admin_balance.show_balance_settings,
            "balance_search_by_id": admin_balance.handle_user_search_by_id,
            "balance_top_users": admin_balance.show_top_balance_users,
            "balance_low_users": admin_balance.show_low_balance_users,
            "bulk_approve_all_confirm": admin_balance.handle_bulk_approve_confirm,
            "bulk_approve_all_execute": admin_balance.execute_bulk_approve,
        }

        # Handle pagination callbacks
        if data.startswith("balance_pending_page_"):
            page = int(data.replace("balance_pending_page_", ""))
            await admin_balance.show_pending_payments_detailed(query, context, page)
            return

        # Handle user-specific callbacks
        if data.startswith("add_balance_") or data.startswith("reduce_balance_"):
            user_id = data.split("_")[-1]
            if data.startswith("add_balance_"):
                await self.initiate_add_balance(query, context, user_id)
            else:
                await self.initiate_reduce_balance(query, context, user_id)
            return

        # Execute mapped callback
        if data in callback_map:
            await callback_map[data](query, context)

    async def handle_admin_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle admin text messages"""
        user = update.effective_user
        text = update.message.text

        if user.id != config.ADMIN_USER_ID:
            return

        # Handle admin_balance messages
        from admin_balance import admin_balance
        await admin_balance.handle_admin_message(update, context)


        if user.id in self.user_states:
            state = self.user_states[user.id]

            if state == "WAITING_SINGLE_CHANNEL_ID":
                try:
                    channel_id = int(text)

                    # Check if channel already exists
                    if channel_id in config.SINGLE_MOVIE_CHANNEL_IDS:
                        await update.message.reply_text(
                            f"⚠️ ይህ Channel ID በቀደሙ ተጨምሯል: {channel_id}"
                        )
                        del self.user_states[user.id]
                        return

                    # Check admin permissions
                    is_valid, message = await self.check_bot_admin_in_channel(context, channel_id, user.id)

                    if is_valid:
                        # Add to the list and update config
                        updated_list = config.SINGLE_MOVIE_CHANNEL_IDS + [channel_id]
                        config.SINGLE_MOVIE_CHANNEL_IDS[:] = updated_list

                        # Save to config file
                        self.update_config_file('SINGLE_MOVIE_CHANNEL_IDS', updated_list)

                        # Get channel info for confirmation
                        channel_info = await self.get_channel_info(context, channel_id)
                        await update.message.reply_text(
                            f"✅ የነጠላ ፊልም Channel ተጨምሯል!\n\n"
                            f"📺 Channel: {channel_info}\n"
                            f"🆔 ID: {channel_id}",
                            parse_mode='Markdown'
                        )
                    else:
                        await update.message.reply_text(
                            f"{message}\n\n"
                            "⚠️ Channel ለመጨመር፣ እርስዎ እና Bot በChannel ውስጥ Admin መሆን አለባችሁ።\n\n"
                            "📝 እንዴት ማድረግ እንደሚችሉ:\n"
                            "1️⃣ Channel ውስጥ ግቡ\n"
                            "2️⃣ Bot ን Admin ያድርጉ\n"
                            "3️⃣ እንደገና ይሞክሩ",
                            parse_mode='Markdown'
                        )

                    del self.user_states[user.id]
                except ValueError:
                    await update.message.reply_text(
                        "❌ እባክዎ ትክክለኛ Channel ID ያስገቡ (ቁጥር)\n"
                        "ምሳሌ: -1001234567890"
                    )

            elif state == "WAITING_SERIES_CHANNEL_ID":
                # Resolve channel ID from input (could be ID or username)
                channel_id, channel_info_or_error = await self.resolve_channel_id(context, text)

                if channel_id is None:
                    await update.message.reply_text(
                        f"❌ Channel ማግኘት አልተቻለም!\n\n"
                        f"ስህተት: {channel_info_or_error}\n\n"
                        "እባክዎ ትክክለኛ Channel ID ወይም Username ያስገቡ:\n"
                        "• -1001234567890 (Channel ID)\n"
                        "• @channelname (Username)"
                    )
                    return

                # Check if channel already exists
                if channel_id in config.SERIES_CHANNEL_IDS:
                    await update.message.reply_text(
                        f"⚠️ ይህ Channel በቀደሙ ተጨምሯል: {channel_info_or_error}",
                        parse_mode='Markdown'
                    )
                    del self.user_states[user.id]
                    return

                # Check admin permissions
                is_valid, message = await self.check_bot_admin_in_channel(context, channel_id, user.id)

                if is_valid:
                    # Add to the list and update config
                    updated_list = config.SERIES_CHANNEL_IDS + [channel_id]
                    config.SERIES_CHANNEL_IDS[:] = updated_list

                    # Save to config file
                    self.update_config_file('SERIES_CHANNEL_IDS', updated_list)

                    await update.message.reply_text(
                        f"✅ የተከታታይ ፊልም Channel ተጨምሯል!\n\n"
                        f"📺 Channel: {channel_info_or_error}\n"
                        f"🆔 ID: {channel_id}",
                        parse_mode='Markdown'
                    )
                else:
                    await update.message.reply_text(
                        f"{message}\n\n"
                        "⚠️ Channel ለመጨመር፣ እርስዎ እና Bot በChannel ውስጥ Admin መሆን አለባችሁ።\n\n"
                        "📝 እንዴት ማድረግ እንደሚችሉ:\n"
                        "1️⃣ Channel ውስጥ ግቡ\n"
                        "2️⃣ Bot ን Admin ያድርጉ\n"
                        "3️⃣ እንደገና ይሞክሩ",
                        parse_mode='Markdown'
                    )

                del self.user_states[user.id]



            elif state.startswith("WAITING_MESSAGE_FOR_USER_"):
                # Handle sending message to user
                target_user_id = int(state.replace("WAITING_MESSAGE_FOR_USER_", ""))

                try:
                    # Send message to target user
                    await context.bot.send_message(
                        target_user_id,
                        f"📩 የAdmin መልእክት:\n\n{text}"
                    )

                    await update.message.reply_text(
                        f"✅ መልእክት ለተጠቃሚ {target_user_id} ተልኳል!"
                    )
                except Exception as e:
                    logger.error(f"Error sending message to user {target_user_id}: {e}")
                    await update.message.reply_text(
                        f"❌ መልእክት መላክ አልተቻለም!\n\n"
                        f"ምክንያት: {str(e)}"
                    )

                del self.user_states[user.id]
            
            elif state == "WAITING_BLOCK_USER_ID":
                from user_block import user_block_system
                try:
                    user_id = int(text)
                    
                    # Ask for block reason
                    self.user_states[user.id] = f"WAITING_BLOCK_REASON_{user_id}"
                    await update.message.reply_text(
                        f"🚫 User {user_id} ለማገድ\n\n"
                        "እባክዎ የማገድ ምክንያት ያስገቡ:"
                    )
                except ValueError:
                    await update.message.reply_text("❌ እባክዎ ትክክለኛ User ID ያስገቡ (ቁጥር)")
                    del self.user_states[user.id]
            
            elif state.startswith("WAITING_BLOCK_REASON_"):
                from user_block import user_block_system
                user_id = int(state.replace("WAITING_BLOCK_REASON_", ""))
                
                success, message = await user_block_system.block_user(user.id, user_id, text, context)
                await update.message.reply_text(message)
                del self.user_states[user.id]
            
            elif state == "WAITING_UNBLOCK_USER_ID":
                from user_block import user_block_system
                try:
                    user_id = int(text)
                    
                    success, message = await user_block_system.unblock_user(user.id, user_id, context)
                    await update.message.reply_text(message)
                except ValueError:
                    await update.message.reply_text("❌ እባክዎ ትክክለኛ User ID ያስገቡ (ቁጥር)")
                
                del self.user_states[user.id]













    async def show_finance_dashboard(self, query, context):
        """Show financial management menu - redirected to admin_balance.py"""
        from admin_balance import admin_balance
        await admin_balance.show_finance_dashboard(query, context)



    async def handle_message_user(self, query, context):
        """Handle sending message to user from payment notification"""
        # Extract user_id from callback data
        user_id = int(query.data.replace("message_user_", ""))

        # Store user_id in context for later use
        context.user_data['message_target_user'] = user_id
        self.user_states[query.from_user.id] = f"WAITING_MESSAGE_FOR_USER_{user_id}"

        # Ask admin to send a message
        await query.answer("💬 እባክዎ መልእክቱን ይጻፉ", show_alert=True)

        try:
            if query.message.caption:
                await query.edit_message_caption(
                    caption=f"{query.message.caption}\n\n💬 ለተጠቃሚ መልእክት ለመላክ እባክዎ መልእክቱን ይጻፉ።"
                )
            else:
                await query.edit_message_text(
                    f"{query.message.text}\n\n💬 ለተጠቃሚ መልእክት ለመላክ እባክዎ መልእክቱን ይጻፉ።"
                )
        except:
            await context.bot.send_message(
                query.from_user.id,
                f"💬 ለተጠቃሚ {user_id} መልእክት ለመላክ እባክዎ መልእክቱን ይጻፉ።"
            )



    async def show_user_management(self, query, context):
        """Show user management options"""
        from user_block import user_block_system
        
        keyboard = [
            [InlineKeyboardButton("🔍 የተጠቃሚ ፍለጋ", callback_data="admin_user_search")],
            [InlineKeyboardButton("📝 የተጠቃሚ ዝርዝር", callback_data="admin_user_list")],
            [InlineKeyboardButton("🚫 Block/Unblock ስርዓት", callback_data="admin_block_system")],
            [InlineKeyboardButton("🔙 ወደ Admin Panel", callback_data="back_to_admin")],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.edit_message_text(
            "👥 **የተጠቃሚዎች አስተዳደር**\n\n"
            "ምን ማድረግ ይፈልጋሉ?",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
    
    async def show_user_list(self, query, context, page=0):
        """Show paginated list of all users"""
        try:
            with sqlite3.connect(config.USER_DB_PATH) as conn:
                # Count total users
                cursor = conn.execute('SELECT COUNT(*) FROM users')
                total = cursor.fetchone()[0]
                
                # Get paginated users
                limit = 10
                offset = page * limit
                
                cursor = conn.execute('''
                    SELECT user_id, username, first_name, balance, joined_date, is_blocked
                    FROM users
                    ORDER BY joined_date DESC
                    LIMIT ? OFFSET ?
                ''', (limit, offset))
                
                users = cursor.fetchall()
        except Exception as e:
            logger.error(f"Error fetching user list: {e}")
            await query.answer("❌ Error fetching data!")
            return
        
        text = f"📋 የተጠቃሚዎች ዝርዝር (ጠቅላላ: {total})\n\n"
        
        if users:
            for user_id, username, first_name, balance, joined_date, is_blocked in users:
                # Display name
                if username:
                    display_name = f"@{username}"
                elif first_name:
                    display_name = first_name
                else:
                    display_name = f"User {user_id}"
                
                # Status icon
                status = "🚫" if is_blocked else "✅"
                
                # Date
                date_str = joined_date[:10] if joined_date else "Unknown"
                
                text += f"{status} {display_name}\n"
                text += f"   💰 {balance} ብር | 📅 {date_str}\n"
                text += f"   ID: {user_id}\n\n"
        else:
            text += "ምንም ተጠቃሚዎች የሉም።"
        
        # Pagination
        keyboard = []
        nav_buttons = []
        
        if page > 0:
            nav_buttons.append(InlineKeyboardButton("◀️ ቀዳሚ", callback_data=f"user_list_{page-1}"))
        
        total_pages = (total + limit - 1) // limit
        if page < total_pages - 1:
            nav_buttons.append(InlineKeyboardButton("ቀጣይ ▶️", callback_data=f"user_list_{page+1}"))
        
        if nav_buttons:
            keyboard.append(nav_buttons)
        
        keyboard.append([InlineKeyboardButton("🔙 ወደ User Management", callback_data="admin_user_management")])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        page_info = f"ገጽ {page + 1}/{total_pages}" if total_pages > 1 else ""
        if page_info:
            text += f"\n{page_info}"
        
        await query.edit_message_text(text, reply_markup=reply_markup)

# Create global admin instance
admin_panel = AdminPanel()