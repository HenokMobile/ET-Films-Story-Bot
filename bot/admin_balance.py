import sqlite3
import logging
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import MessageHandler, filters, CallbackQueryHandler, ContextTypes
import config
# from database import db # This import was removed as it's not used in the edited code.
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class AdminBalanceManager:
    def __init__(self):
        self.user_states = {}

    def escape_markdown(self, text):
        """Escape special characters for Telegram MarkdownV2"""
        if not text:
            return ""
        special_chars = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
        escaped_text = str(text)
        for char in special_chars:
            escaped_text = escaped_text.replace(char, f'\\{char}')
        return escaped_text

    async def show_finance_dashboard(self, query, context):
        """Show main finance dashboard"""
        keyboard = [
            [InlineKeyboardButton("🔍 በገቢ ID ፈልግ", callback_data="search_payment_by_id")],
            [InlineKeyboardButton("👤 የተጠቃሚ ሂሳብ መስተዳደር", callback_data="user_management")],
            [InlineKeyboardButton("⏳ በጥያቄ ላይ ያሉ ክፍያዎች", callback_data="pending_payments")],
            [InlineKeyboardButton("✅ የተሳኩ ክፍያዎች", callback_data="successful_payments")],
            [InlineKeyboardButton("❌ ያልተሳኩ ክፍያዎች", callback_data="failed_payments")],
            [InlineKeyboardButton("📊 የክፍያ ሪፖርቶች", callback_data="payment_reports")],
            [InlineKeyboardButton("🔙 ወደ Admin Panel", callback_data="back_to_admin")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        # Get basic statistics
        conn = sqlite3.connect(config.USER_DB_PATH)
        cursor = conn.cursor()

        cursor.execute("SELECT COUNT(*) FROM payments WHERE status = 'pending'")
        pending_count = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM payments WHERE status = 'approved'")
        approved_count = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM payments WHERE status = 'rejected'")
        rejected_count = cursor.fetchone()[0]

        cursor.execute("SELECT SUM(amount) FROM payments WHERE status = 'approved'")
        total_approved = cursor.fetchone()[0] or 0

        conn.close()

        text = (
            "💰 የሂሳብ መቆጣጠሪያ Dashboard\n\n"
            f"⏳ በጥያቄ ላይ: {pending_count:,} ክፍያዎች\n"
            f"✅ የተሳኩ: {approved_count:,} ክፍያዎች\n"
            f"❌ ያልተሳኩ: {rejected_count:,} ክፍያዎች\n"
            f"💰 ጠቅላላ የተሳካ ገቢ: {total_approved:,} ብር"
        )

        try:
            # First, delete the message the button is attached to
            await query.message.delete()
        except Exception as e:
            logger.warning(f"Could not delete message in show_finance_dashboard: {e}")
        
        # Then, send a new message with the dashboard
        await context.bot.send_message(
            chat_id=query.message.chat_id,
            text=text,
            reply_markup=reply_markup
        )

    async def show_user_management(self, query, context):
        """Show user management options"""
        keyboard = [
            [InlineKeyboardButton("🔍 በUser ID ፈልግ", callback_data="search_by_id")],
            [InlineKeyboardButton("👤 በUsername ፈልግ", callback_data="search_by_username")],
            [InlineKeyboardButton("📱 በስልክ ቁጥር ፈልግ", callback_data="search_by_phone")],
            [InlineKeyboardButton("🔙 ወደ Dashboard", callback_data="admin_finance")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        text = (
            "👤 **የተጠቃሚ ሂሳብ መስተዳደር**\n\n"
            "ተጠቃሚ እንዴት መፈለግ ይፈልጋሉ?"
        )

        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')

    async def show_pending_payments(self, query, context, page=0):
        """Show pending payments with full details"""
        conn = sqlite3.connect(config.USER_DB_PATH)
        cursor = conn.cursor()

        limit = 1
        offset = page * limit

        cursor.execute("""
            SELECT p.id, p.user_id, p.method, p.name, p.phone, p.account, p.amount, 
                   p.photo_file_id, p.created_at, u.username, u.first_name, u.phone_number
            FROM payments p
            LEFT JOIN users u ON p.user_id = u.user_id
            WHERE p.status = 'pending'
            ORDER BY p.created_at DESC
            LIMIT ? OFFSET ?
        """, (limit, offset))

        payments = cursor.fetchall()

        cursor.execute("SELECT COUNT(*) FROM payments WHERE status = 'pending'")
        total_count = cursor.fetchone()[0]

        conn.close()

        if not payments:
            keyboard = [[InlineKeyboardButton("🔙 ወደ Dashboard", callback_data="admin_finance")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(
                "⏳ **በጥያቄ ላይ ያሉ ክፍያዎች**\n\nምንም የጥያቄ ክፍያ የለም!",
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
            return

        keyboard = []
        for payment in payments:
            payment_id = payment[0]
            keyboard.append([
                InlineKeyboardButton(f"✅ ተቀበል #{payment_id}", callback_data=f"approve_{payment_id}"),
                InlineKeyboardButton(f"❌ ውድቅ #{payment_id}", callback_data=f"reject_{payment_id}")
            ])
            keyboard.append([InlineKeyboardButton(f"📋 ዝርዝር #{payment_id}", callback_data=f"details_{payment_id}")])

        # Pagination
        nav_buttons = []
        if page > 0:
            nav_buttons.append(InlineKeyboardButton("⬅️ ቀደም", callback_data=f"pending_page_{page-1}"))
        if (page + 1) * limit < total_count:
            nav_buttons.append(InlineKeyboardButton("ቀጣይ ➡️", callback_data=f"pending_page_{page+1}"))

        if nav_buttons:
            keyboard.append(nav_buttons)

        keyboard.append([InlineKeyboardButton("🔙 ወደ Dashboard", callback_data="admin_finance")])
        reply_markup = InlineKeyboardMarkup(keyboard)

        text = f"⏳ *በጥያቄ ላይ ያሉ ክፍያዎች* (ገጽ {page + 1})\n\n"

        for payment in payments:
            payment_id, user_id, method, name, phone, account, amount, photo_file_id, created_at, username, first_name, registered_phone = payment

            # Escape all user-generated content
            user_display = self.escape_markdown(first_name or username or f"ID:{user_id}")
            username_display = f"@{self.escape_markdown(username)}" if username else "N/A"
            registered_phone_display = self.escape_markdown(registered_phone) if registered_phone else "N/A"
            safe_method = self.escape_markdown(method) if method else "N/A"
            safe_phone = self.escape_markdown(phone) if phone else None
            safe_account = self.escape_markdown(account) if account else None
            safe_date = self.escape_markdown(created_at[:16]) if created_at else "N/A"

            text += f"🆔 #{payment_id}\n"
            text += f"👤 {user_display}\n"
            text += f"📱 Username: {username_display}\n"
            text += f"📞 የተመዘገበ ስልክ: {registered_phone_display}\n"
            text += f"💳 {safe_method}: *{amount:,} ብር*\n"

            if safe_phone:
                text += f"📱 የክፍያ ስልክ: {safe_phone}\n"
            if safe_account:
                text += f"🏦 አካውንት: {safe_account}\n"

            text += f"📅 {safe_date}\n\n"

        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')

    async def show_payment_details(self, query, context, payment_id):
        """Show full payment details with screenshot"""
        conn = sqlite3.connect(config.USER_DB_PATH)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT p.id, p.user_id, p.method, p.name, p.phone, p.account, p.amount, 
                   p.photo_file_id, p.created_at, p.status, u.username, u.first_name, u.phone_number
            FROM payments p
            LEFT JOIN users u ON p.user_id = u.user_id
            WHERE p.id = ?
        """, (payment_id,))

        payment = cursor.fetchone()
        conn.close()

        if not payment:
            await query.answer("❌ ክፍያ አልተገኘም!", show_alert=True)
            return

        # Unpack payment data properly
        payment_id, user_id, method, name, phone, account, amount, photo_file_id, created_at, status, username, first_name, user_phone = payment

        user_display = self.escape_markdown(first_name or username or f"ID:{user_id}")
        safe_user_phone = self.escape_markdown(user_phone) if user_phone else 'N/A'
        safe_method = self.escape_markdown(method) if method else 'N/A'
        safe_name = self.escape_markdown(name) if name else 'N/A'

        keyboard = [
            [InlineKeyboardButton("✅ ተቀበል", callback_data=f"approve_{payment_id}"),
             InlineKeyboardButton("❌ ውድቅ", callback_data=f"reject_{payment_id}")],
            [InlineKeyboardButton("💬 መልእክት ላክ", callback_data=f"message_user_{user_id}")],
            [InlineKeyboardButton("🔙 ወደ በጥያቄ ላይ", callback_data="pending_payments")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        caption = (
            f"📋 *የክፍያ ዝርዝር #{payment_id}*\n\n"
            f"👤 ተጠቃሚ: {user_display}\n"
            f"🆔 User ID: `{user_id}`\n"
            f"📱 የተጠቃሚ ስልክ: {safe_user_phone}\n"
            f"💳 የክፍያ ዘዴ: {safe_method}\n"
            f"👤 ስም: {safe_name}\n"
        )

        if phone:  # phone
            safe_phone = self.escape_markdown(phone)
            caption += f"📱 የክፍያ ስልክ: {safe_phone}\n"
        if account:  # account
            safe_account = self.escape_markdown(account)
            caption += f"🏦 Account: {safe_account}\n"

        safe_date = self.escape_markdown(created_at[:16]) if created_at else 'N/A'
        safe_status = self.escape_markdown(status) if status else 'pending'

        caption += (
            f"💰 መጠን: *{amount:,} ብር*\n"
            f"📅 ቀን: {safe_date}\n"
            f"🔄 ሁኔታ: {safe_status}"
        )

        # Send screenshot if available
        if photo_file_id:  # photo_file_id
            await context.bot.send_photo(
                chat_id=query.message.chat.id,
                photo=photo_file_id,
                caption=caption,
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
            # Delete the text message
            try:
                await query.message.delete()
            except:
                pass
        else:
            await query.edit_message_text(
                caption + "\n\n📸 Screenshot: ❌ አልተላከም",
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )

    async def show_successful_payments(self, query, context, page=0):
        """Show successful payments"""
        conn = sqlite3.connect(config.USER_DB_PATH)
        cursor = conn.cursor()

        limit = 10
        offset = page * limit

        cursor.execute("""
            SELECT p.id, p.user_id, p.method, p.amount, p.created_at, u.username, u.phone_number
            FROM payments p
            LEFT JOIN users u ON p.user_id = u.user_id
            WHERE p.status = 'approved'
            ORDER BY p.created_at DESC
            LIMIT ? OFFSET ?
        """, (limit, offset))

        payments = cursor.fetchall()

        cursor.execute("SELECT COUNT(*) FROM payments WHERE status = 'approved'")
        total_count = cursor.fetchone()[0]

        cursor.execute("SELECT SUM(amount) FROM payments WHERE status = 'approved'")
        total_amount = cursor.fetchone()[0] or 0

        conn.close()

        if not payments:
            keyboard = [[InlineKeyboardButton("🔙 ወደ Dashboard", callback_data="admin_finance")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(
                "✅ **የተሳኩ ክፍያዎች**\n\nምንም የተሳካ ክፍያ የለም!",
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
            return

        text = f"✅ **የተሳኩ ክፍያዎች** (ገጽ {page + 1})\n"
        text += f"💰 ጠቅላላ መጠን: {total_amount:,} ብር\n\n"

        keyboard = []
        for i, payment in enumerate(payments):
            payment_id, user_id, method, amount, created_at, username, phone_number = payment
            # Escape all user-generated content for Markdown
            safe_username = self.escape_markdown(username) if username else None
            safe_phone = self.escape_markdown(phone_number) if phone_number else None
            user_display = f"@{safe_username}" if safe_username else (safe_phone or f"ID:{user_id}")
            safe_method = self.escape_markdown(method) if method else "N/A"
            safe_date = self.escape_markdown(created_at[:16]) if created_at else "N/A"

            text += f"🆔 #{payment_id} | 👤 {user_display}\n"
            text += f"💳 {safe_method}: *{amount:,} ብር* | 📅 {safe_date}\n\n"

            # Add details button for each payment
            keyboard.append([InlineKeyboardButton(f"📋 ዝርዝር #{payment_id}", callback_data=f"view_payment_{payment_id}")])

        # Pagination
        nav_buttons = []
        if page > 0:
            nav_buttons.append(InlineKeyboardButton("⬅️ ቀደም", callback_data=f"successful_page_{page-1}"))
        if (page + 1) * limit < total_count:
            nav_buttons.append(InlineKeyboardButton("ቀጣይ ➡️", callback_data=f"successful_page_{page+1}"))

        if nav_buttons:
            keyboard.append(nav_buttons)

        keyboard.append([InlineKeyboardButton("🔙 ወደ Dashboard", callback_data="admin_finance")])

        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')

    async def show_failed_payments(self, query, context, page=0):
        """Show failed payments"""
        conn = sqlite3.connect(config.USER_DB_PATH)
        cursor = conn.cursor()

        limit = 10
        offset = page * limit

        cursor.execute("""
            SELECT p.id, p.user_id, p.method, p.amount, p.created_at, u.username, u.phone_number
            FROM payments p
            LEFT JOIN users u ON p.user_id = u.user_id
            WHERE p.status = 'rejected'
            ORDER BY p.created_at DESC
            LIMIT ? OFFSET ?
        """, (limit, offset))

        payments = cursor.fetchall()

        cursor.execute("SELECT COUNT(*) FROM payments WHERE status = 'rejected'")
        total_count = cursor.fetchone()[0]

        cursor.execute("SELECT SUM(amount) FROM payments WHERE status = 'rejected'")
        total_amount = cursor.fetchone()[0] or 0

        conn.close()

        if not payments:
            keyboard = [[InlineKeyboardButton("🔙 ወደ Dashboard", callback_data="admin_finance")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(
                "❌ **ያልተሳኩ ክፍያዎች**\n\nምንም ያልተሳካ ክፍያ የለም!",
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
            return

        text = f"❌ **ያልተሳኩ ክፍያዎች** (ገጽ {page + 1})\n"
        text += f"💸 ጠቅላላ መጠን: {total_amount:,} ብር\n\n"

        keyboard = []
        for payment in payments:
            payment_id, user_id, method, amount, created_at, username, phone_number = payment
            # Escape all user-generated content for Markdown
            safe_username = self.escape_markdown(username) if username else None
            safe_phone = self.escape_markdown(phone_number) if phone_number else None
            user_display = f"@{safe_username}" if safe_username else (safe_phone or f"ID:{user_id}")
            safe_method = self.escape_markdown(method) if method else "N/A"
            safe_date = self.escape_markdown(created_at[:16]) if created_at else "N/A"

            text += f"🆔 #{payment_id} | 👤 {user_display}\n"
            text += f"💳 {safe_method}: *{amount:,} ብር* | 📅 {safe_date}\n\n"

            # Add details button for each payment
            keyboard.append([InlineKeyboardButton(f"📋 ዝርዝር #{payment_id}", callback_data=f"view_payment_{payment_id}")])

        # Pagination
        nav_buttons = []
        if page > 0:
            nav_buttons.append(InlineKeyboardButton("⬅️ ቀደም", callback_data=f"failed_page_{page-1}"))
        if (page + 1) * limit < total_count:
            nav_buttons.append(InlineKeyboardButton("ቀጣይ ➡️", callback_data=f"failed_page_{page+1}"))

        if nav_buttons:
            keyboard.append(nav_buttons)

        keyboard.append([InlineKeyboardButton("🔙 ወደ Dashboard", callback_data="admin_finance")])

        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')

    async def show_payment_reports(self, query, context):
        """Show payment reports by time periods"""
        keyboard = [
            [InlineKeyboardButton("📅 የዛሬ ሪፖርት", callback_data="report_daily")],
            [InlineKeyboardButton("📊 የሳምንት ሪፖርት", callback_data="report_weekly")],
            [InlineKeyboardButton("📈 የወር ሪፖርት", callback_data="report_monthly")],
            [InlineKeyboardButton("📉 የአመት ሪፖርት", callback_data="report_yearly")],
            [InlineKeyboardButton("🔙 ወደ Dashboard", callback_data="admin_finance")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        text = (
            "📊 **የክፍያ ሪፖርቶች**\n\n"
            "የትኛውን የጊዜ ሪፖርት ማየት ይፈልጋሉ?"
        )

        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')

    async def show_daily_report(self, query, context):
        """Show today's payment report"""
        conn = sqlite3.connect(config.USER_DB_PATH)
        cursor = conn.cursor()

        today = datetime.now().strftime('%Y-%m-%d')

        # Today's successful payments
        cursor.execute("""
            SELECT COUNT(*), SUM(amount) FROM payments 
            WHERE status = 'approved' AND DATE(created_at) = ?
        """, (today,))
        success_data = cursor.fetchone()
        success_count = success_data[0] or 0
        success_amount = success_data[1] or 0

        # Today's failed payments
        cursor.execute("""
            SELECT COUNT(*), SUM(amount) FROM payments 
            WHERE status = 'rejected' AND DATE(created_at) = ?
        """, (today,))
        failed_data = cursor.fetchone()
        failed_count = failed_data[0] or 0
        failed_amount = failed_data[1] or 0

        # Today's pending payments
        cursor.execute("""
            SELECT COUNT(*), SUM(amount) FROM payments 
            WHERE status = 'pending' AND DATE(created_at) = ?
        """, (today,))
        pending_data = cursor.fetchone()
        pending_count = pending_data[0] or 0
        pending_amount = pending_data[1] or 0

        conn.close()

        keyboard = [[InlineKeyboardButton("🔙 ወደ ሪፖርቶች", callback_data="payment_reports")]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        text = (
            f"📅 **የዛሬ የክፍያ ሪፖርት** ({today})\n\n"
            f"✅ **የተሳኩ ክፍያዎች:**\n"
            f"• ቁጥር: {success_count:,} ክፍያዎች\n"
            f"• መጠን: {success_amount:,} ብር\n\n"
            f"❌ **ያልተሳኩ ክፍያዎች:**\n"
            f"• ቁጥር: {failed_count:,} ክፍያዎች\n"
            f"• መጠን: {failed_amount:,} ብር\n\n"
            f"⏳ **በጥያቄ ላይ ያሉ ክፍያዎች:**\n"
            f"• ቁጥር: {pending_count:,} ክፍያዎች\n"
            f"• መጠን: {pending_amount:,} ብር\n\n"
            f"💰 **የዛሬ ጠቅላላ የተሳካ ገቢ:** {success_amount:,} ብር"
        )

        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')

    async def show_weekly_report(self, query, context):
        """Show this week's payment report"""
        conn = sqlite3.connect(config.USER_DB_PATH)
        cursor = conn.cursor()

        week_ago = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')

        # This week's successful payments
        cursor.execute("""
            SELECT COUNT(*), SUM(amount) FROM payments 
            WHERE status = 'approved' AND DATE(created_at) >= ?
        """, (week_ago,))
        success_data = cursor.fetchone()
        success_count = success_data[0] or 0
        success_amount = success_data[1] or 0

        # This week's failed payments
        cursor.execute("""
            SELECT COUNT(*), SUM(amount) FROM payments 
            WHERE status = 'rejected' AND DATE(created_at) >= ?
        """, (week_ago,))
        failed_data = cursor.fetchone()
        failed_count = failed_data[0] or 0
        failed_amount = failed_data[1] or 0

        conn.close()

        keyboard = [[InlineKeyboardButton("🔙 ወደ ሪፖርቶች", callback_data="payment_reports")]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        text = (
            f"📊 **የሳምንት የክፍያ ሪፖርት** (ባለፉት 7 ቀናት)\n\n"
            f"✅ **የተሳኩ ክፍያዎች:**\n"
            f"• ቁጥር: {success_count:,} ክፍያዎች\n"
            f"• መጠን: {success_amount:,} ብር\n\n"
            f"❌ **ያልተሳኩ ክፍያዎች:**\n"
            f"• ቁጥር: {failed_count:,} ክፍያዎች\n"
            f"• መጠን: {failed_amount:,} ብር\n\n"
            f"💰 **የሳምንት ጠቅላላ የተሳካ ገቢ:** {success_amount:,} ብር"
        )

        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')

    async def show_monthly_report(self, query, context):
        """Show this month's payment report"""
        conn = sqlite3.connect(config.USER_DB_PATH)
        cursor = conn.cursor()

        month_ago = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')

        # This month's successful payments
        cursor.execute("""
            SELECT COUNT(*), SUM(amount) FROM payments 
            WHERE status = 'approved' AND DATE(created_at) >= ?
        """, (month_ago,))
        success_data = cursor.fetchone()
        success_count = success_data[0] or 0
        success_amount = success_data[1] or 0

        # This month's failed payments
        cursor.execute("""
            SELECT COUNT(*), SUM(amount) FROM payments 
            WHERE status = 'rejected' AND DATE(created_at) >= ?
        """, (month_ago,))
        failed_data = cursor.fetchone()
        failed_count = failed_data[0] or 0
        failed_amount = failed_data[1] or 0

        conn.close()

        keyboard = [[InlineKeyboardButton("🔙 ወደ ሪፖርቶች", callback_data="payment_reports")]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        text = (
            f"📈 **የወር የክፍያ ሪፖርት** (ባለፉት 30 ቀናት)\n\n"
            f"✅ **የተሳኩ ክፍያዎች:**\n"
            f"• ቁጥር: {success_count:,} ክፍያዎች\n"
            f"• መጠን: {success_amount:,} ብር\n\n"
            f"❌ **ያልተሳኩ ክፍያዎች:**\n"
            f"• ቁጥር: {failed_count:,} ክፍያዎች\n"
            f"• መጠን: {failed_amount:,} ብር\n\n"
            f"💰 **የወር ጠቅላላ የተሳካ ገቢ:** {success_amount:,} ብር"
        )

        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')

    async def show_yearly_report(self, query, context):
        """Show this year's payment report"""
        conn = sqlite3.connect(config.USER_DB_PATH)
        cursor = conn.cursor()

        year_ago = (datetime.now() - timedelta(days=365)).strftime('%Y-%m-%d')

        # This year's successful payments
        cursor.execute("""
            SELECT COUNT(*), SUM(amount) FROM payments 
            WHERE status = 'approved' AND DATE(created_at) >= ?
        """, (year_ago,))
        success_data = cursor.fetchone()
        success_count = success_data[0] or 0
        success_amount = success_data[1] or 0

        # This year's failed payments
        cursor.execute("""
            SELECT COUNT(*), SUM(amount) FROM payments 
            WHERE status = 'rejected' AND DATE(created_at) >= ?
        """, (year_ago,))
        failed_data = cursor.fetchone()
        failed_count = failed_data[0] or 0
        failed_amount = failed_data[1] or 0

        conn.close()

        keyboard = [[InlineKeyboardButton("🔙 ወደ ሪፖርቶች", callback_data="payment_reports")]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        text = (
            f"📉 **የአመት የክፍያ ሪፖርት** (ባለፈው አመት)\n\n"
            f"✅ **የተሳኩ ክፍያዎች:**\n"
            f"• ቁጥር: {success_count:,} ክፍያዎች\n"
            f"• መጠን: {success_amount:,} ብር\n\n"
            f"❌ **ያልተሳኩ ክፍያዎች:**\n"
            f"• ቁጥር: {failed_count:,} ክፍያዎች\n"
            f"• መጠን: {failed_amount:,} ብር\n\n"
            f"💰 **የአመት ጠቅላላ የተሳካ ገቢ:** {success_amount:,} ብር"
        )

        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')

    async def handle_user_search(self, query, context, search_type):
        """Handle user search initiation"""
        if search_type == "id":
            await query.edit_message_text(
                "🔍 **በUser ID ፍለጋ**\n\n"
                "እባክዎ የተጠቃሚውን User ID ያስገቡ:",
                parse_mode='Markdown'
            )
            self.user_states[query.from_user.id] = "WAITING_USER_ID"
        elif search_type == "username":
            await query.edit_message_text(
                "👤 **በUsername ፍለጋ**\n\n"
                "እባክዎ የተጠቃሚውን Username ያስገቡ (@ ያለ):"
            )
            self.user_states[query.from_user.id] = "WAITING_USERNAME"
        elif search_type == "phone":
            await query.edit_message_text(
                "📱 **በስልክ ቁጥር ፍለጋ**\n\n"
                "እባክዎ የተጠቃሚውን ስልክ ቁጥር ያስገቡ:"
            )
            self.user_states[query.from_user.id] = "WAITING_PHONE"

    def escape_markdown(self, text):
        """Escape markdown special characters"""
        if not text:
            return text
        # Escape Markdown special characters
        special_chars = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
        text = str(text)
        for char in special_chars:
            text = text.replace(char, '\\' + char)
        return text

    async def search_user_and_show_details(self, update, context, search_value, search_type):
        """Search for user and show their balance management interface"""
        conn = sqlite3.connect(config.USER_DB_PATH)
        cursor = conn.cursor()

        # Select specific columns to avoid confusion
        if search_type == "id":
            cursor.execute("""
                SELECT user_id, username, phone_number, first_name, last_name, balance, joined_date 
                FROM users WHERE user_id = ?
            """, (int(search_value),))
        elif search_type == "username":
            cursor.execute("""
                SELECT user_id, username, phone_number, first_name, last_name, balance, joined_date 
                FROM users WHERE username = ?
            """, (search_value,))
        elif search_type == "phone":
            cursor.execute("""
                SELECT user_id, username, phone_number, first_name, last_name, balance, joined_date 
                FROM users WHERE phone_number = ?
            """, (search_value,))

        user = cursor.fetchone()

        if not user:
            conn.close()
            await update.message.reply_text(f"❌ ተጠቃሚ አልተገኘም: {search_value}")
            return

        # Unpack user data from the specific columns we selected
        user_id, username, phone, first_name, last_name, balance, joined_date = user

        # Ensure balance is not None
        balance = balance if balance is not None else 0

        # Get payment statistics
        cursor.execute("SELECT COUNT(*) FROM payments WHERE user_id = ? AND status = 'approved'", (user_id,))
        successful_payments = cursor.fetchone()[0]

        cursor.execute("SELECT SUM(amount) FROM payments WHERE user_id = ? AND status = 'approved'", (user_id,))
        total_deposited = cursor.fetchone()[0] or 0

        conn.close()

        keyboard = [
            [InlineKeyboardButton("➕ Balance ጨምር", callback_data=f"add_balance_{user_id}")],
            [InlineKeyboardButton("➖ Balance ቀንስ", callback_data=f"reduce_balance_{user_id}")],
            [InlineKeyboardButton("📊 የክፍያ ታሪክ", callback_data=f"user_history_{user_id}")],
            [InlineKeyboardButton("🔙 ወደ User Management", callback_data="user_management")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        # Escape markdown special characters for safe display
        user_display = self.escape_markdown(first_name or username or f"ID:{user_id}")
        # Escape @ symbol separately for username display
        if username:
            safe_username = "@" + self.escape_markdown(username)
        else:
            safe_username = "N/A"
        safe_phone = self.escape_markdown(phone) if phone else 'N/A'
        safe_joined = self.escape_markdown(joined_date[:10]) if joined_date else 'N/A'

        text = (
            f"👤 *የተጠቃሚ ሂሳብ መረጃ*\n\n"
            f"🆔 User ID: `{user_id}`\n"
            f"👤 ስም: {user_display}\n"
            f"📱 Username: {safe_username}\n"
            f"📞 ስልክ: {safe_phone}\n"
            f"📅 የተቀላቀለበት: {safe_joined}\n\n"
            f"💰 *የሂሳብ መረጃ:*\n"
            f"• ወቅታዊ Balance: *{balance:,} ብር*\n"
            f"• ጠቅላላ Deposits: {total_deposited:,} ብር\n"
            f"• የተሳኩ ክፍያዎች: {successful_payments:,}"
        )

        await update.message.reply_text(text, reply_markup=reply_markup, parse_mode='Markdown')

    async def handle_balance_adjustment(self, query, context, action, user_id):
        """Handle balance addition or reduction"""
        if action == "add":
            await query.edit_message_text(
                f"➕ **Balance መጨመር**\n\n"
                f"ለተጠቃሚ {user_id} ምን ያህል ብር መጨመር ይፈልጋሉ?\n"
                "መጠን ያስገቡ:"
            )
            self.user_states[query.from_user.id] = f"ADDING_BALANCE_{user_id}"
        elif action == "reduce":
            await query.edit_message_text(
                f"➖ **Balance መቀነስ**\n\n"
                f"ከተጠቃሚ {user_id} ምን ያህል ብር መቀነስ ይፈልጋሉ?\n"
                "መጠን ያስገቡ:"
            )
            self.user_states[query.from_user.id] = f"REDUCING_BALANCE_{user_id}"

    async def show_user_payment_history(self, query, context, user_id, page=0):
        """Show user's payment history"""
        conn = sqlite3.connect(config.USER_DB_PATH)
        cursor = conn.cursor()

        # Get user info
        cursor.execute('SELECT username, first_name FROM users WHERE user_id = ?', (user_id,))
        user_info = cursor.fetchone()

        if not user_info:
            await query.answer("❌ ተጠቃሚ አልተገኘም!", show_alert=True)
            conn.close()
            return

        username, first_name = user_info
        user_display = self.escape_markdown(first_name or username or f"ID:{user_id}")

        # Get payment history with pagination
        limit = 10
        offset = page * limit

        cursor.execute("""
            SELECT id, method, amount, status, created_at 
            FROM payments 
            WHERE user_id = ?
            ORDER BY created_at DESC
            LIMIT ? OFFSET ?
        """, (user_id, limit, offset))

        payments = cursor.fetchall()

        # Get total count
        cursor.execute('SELECT COUNT(*) FROM payments WHERE user_id = ?', (user_id,))
        total_count = cursor.fetchone()[0]

        # Get statistics
        cursor.execute("""
            SELECT 
                COUNT(CASE WHEN status = 'approved' THEN 1 END) as approved_count,
                COUNT(CASE WHEN status = 'pending' THEN 1 END) as pending_count,
                COUNT(CASE WHEN status = 'rejected' THEN 1 END) as rejected_count,
                SUM(CASE WHEN status = 'approved' THEN amount ELSE 0 END) as total_approved
            FROM payments WHERE user_id = ?
        """, (user_id,))

        stats = cursor.fetchone()
        approved_count, pending_count, rejected_count, total_approved = stats
        total_approved = total_approved or 0

        conn.close()

        # Build payment history text
        history_text = f"📋 *የክፍያ ታሪክ \\- {user_display}*\n\n"
        history_text += f"📊 *ጠቅላላ Statistics:*\n"
        history_text += f"✅ Approved: {approved_count} \\({total_approved:,} ብር\\)\n"
        history_text += f"⏳ Pending: {pending_count}\n"
        history_text += f"❌ Rejected: {rejected_count}\n\n"

        if payments:
            history_text += f"📜 *Recent Payments* \\(ገጽ {page + 1}\\):\n\n"

            for payment in payments:
                payment_id, method, amount, status, created_at = payment

                # Status icon
                if status == 'approved':
                    status_icon = "✅"
                elif status == 'pending':
                    status_icon = "⏳"
                else:
                    status_icon = "❌"

                safe_method = self.escape_markdown(method) if method else "N/A"
                safe_date = self.escape_markdown(created_at[:16]) if created_at else "N/A"

                history_text += f"{status_icon} \\#{payment_id} \\| {safe_method}\n"
                history_text += f"   💰 {amount:,} ብር \\| 📅 {safe_date}\n\n"
        else:
            history_text += "ምንም የክፍያ ታሪክ የለም\\."

        # Pagination buttons
        keyboard = []
        nav_buttons = []

        if page > 0:
            nav_buttons.append(InlineKeyboardButton("⬅️ ቀደም", callback_data=f"history_page_{user_id}_{page-1}"))
        if (page + 1) * limit < total_count:
            nav_buttons.append(InlineKeyboardButton("ቀጣይ ➡️", callback_data=f"history_page_{user_id}_{page+1}"))

        if nav_buttons:
            keyboard.append(nav_buttons)

        keyboard.append([InlineKeyboardButton("🔙 ወደ User Details", callback_data=f"back_to_user_{user_id}")])

        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.edit_message_text(
            history_text,
            reply_markup=reply_markup,
            parse_mode='MarkdownV2'
        )

    async def execute_balance_change(self, update, context, user_id, amount, action):
        """Execute balance change"""
        conn = sqlite3.connect(config.USER_DB_PATH)
        cursor = conn.cursor()

        # Get current balance
        cursor.execute("SELECT balance, first_name, username FROM users WHERE user_id = ?", (int(user_id),))
        user_data = cursor.fetchone()

        if not user_data:
            conn.close()
            await update.message.reply_text("❌ ተጠቃሚ አልተገኘም!")
            return

        # Safely unpack user data
        current_balance = user_data[0] if user_data[0] is not None else 0
        first_name = user_data[1] if len(user_data) > 1 else None
        username = user_data[2] if len(user_data) > 2 else None
        user_display = self.escape_markdown(first_name or username or f"ID:{user_id}")

        if action == "reduce" and current_balance < amount:
            await update.message.reply_text(
                f"❌ ተጠቃሚ {user_display} በቂ Balance የለውም!\n"
                f"ወቅታዊ Balance: {current_balance:,} ብር\n"
                f"መቀነስ የፈለጉት: {amount:,} ብር"
            )
            conn.close()
            return

        # Update balance
        if action == "add":
            cursor.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (amount, int(user_id)))
            new_balance = current_balance + amount
            sign = "+"
        else:
            cursor.execute("UPDATE users SET balance = balance - ? WHERE user_id = ?", (amount, int(user_id)))
            new_balance = current_balance - amount
            sign = "-"

        conn.commit()
        conn.close()

        # Send confirmation to admin
        await update.message.reply_text(
            f"✅ *Balance ተስተካክሏል\\!*\n\n"
            f"👤 ተጠቃሚ: {user_display}\n"
            f"🔄 ለውጥ: {sign}{amount:,} ብር\n"
            f"💰 ቀደም Balance: {current_balance:,} ብር\n"
            f"💰 አዲስ Balance: {new_balance:,} ብር",
            parse_mode='Markdown'
        )

        # Send notification to user
        try:
            if action == "add":
                await context.bot.send_message(
                    user_id,
                    f"✅ ሂሳብዎ ተስተካክሏል!\n💰 {amount:,} ብር ተጨምሯል።\nአዲስ Balance: {new_balance:,} ብር"
                )
            else:
                await context.bot.send_message(
                    user_id,
                    f"⚠️ ሂሳብዎ ተስተካክሏል!\n💸 {amount:,} ብር ተቀንሷል።\nአዲስ Balance: {new_balance:,} ብር"
                )
        except:
            pass  # User might have blocked the bot

    async def approve_payment(self, query, context, payment_id):
        """Approve payment"""
        conn = sqlite3.connect(config.USER_DB_PATH)
        cursor = conn.cursor()

        # Select specific columns to avoid index confusion
        cursor.execute('''
            SELECT id, user_id, method, name, phone, account, amount, photo_file_id, created_at, status 
            FROM payments WHERE id = ?
        ''', (payment_id,))
        payment = cursor.fetchone()

        if not payment:
            await query.answer("❌ ክፍያ አልተገኘም!", show_alert=True)
            conn.close()
            return

        # Unpack with correct indices
        payment_id, user_id, method, name, phone, account, amount, photo_file_id, created_at, status = payment

        # Validate amount is a number
        try:
            amount = int(amount)
        except (ValueError, TypeError):
            logger.error(f"Invalid amount in payment {payment_id}: {amount}")
            await query.answer("❌ የክፍያ መጠን ስህተት አለበት!", show_alert=True)
            conn.close()
            return

        # Update payment status
        cursor.execute('UPDATE payments SET status = ? WHERE id = ?', ('approved', payment_id))

        # Add to user balance - ensure it's added as integer
        cursor.execute('UPDATE users SET balance = COALESCE(balance, 0) + ? WHERE user_id = ?', (amount, user_id))

        conn.commit()

        # Verify the balance was updated
        cursor.execute('SELECT balance FROM users WHERE user_id = ?', (user_id,))
        new_balance = cursor.fetchone()
        conn.close()

        try:
            await context.bot.send_message(
                user_id,
                f"✅ የክፍያ ጥያቄዎ ተቀባይነት አግኝቷል!\n💰 {amount:,} ብር ወደ ሂሳብዎ ተጨምሯል።\n\n💵 አዲስ Balance: {new_balance[0]:,} ብር"
            )
        except Exception as e:
            logger.error(f"Error sending approval message to user: {e}")

        await query.answer("✅ ክፍያ ተቀባይነት አግኝቷል!", show_alert=True)
        # Refresh the pending payments view
        await self.show_pending_payments(query, context)

    async def reject_payment(self, query, context, payment_id):
        """Reject payment"""
        conn = sqlite3.connect(config.USER_DB_PATH)
        cursor = conn.cursor()

        # Select specific columns to avoid index confusion
        cursor.execute('''
            SELECT id, user_id, method, name, phone, account, amount, photo_file_id, created_at, status 
            FROM payments WHERE id = ?
        ''', (payment_id,))
        payment = cursor.fetchone()

        if not payment:
            await query.answer("❌ ክፍያ አልተገኘም!", show_alert=True)
            conn.close()
            return

        # Unpack with correct indices
        payment_id, user_id, method, name, phone, account, amount, photo_file_id, created_at, status = payment

        # Update payment status
        cursor.execute('UPDATE payments SET status = ? WHERE id = ?', ('rejected', payment_id))

        conn.commit()
        conn.close()

        try:
            await context.bot.send_message(
                user_id,
                f"❌ የክፍያ ጥያቄዎ ውድቅ ሆኗል።\n💰 መጠን: {amount:,} ብር\n\nእባክዎ እንደገና ይሞክሩ ወይም አድሚንን ያነጋግሩ።"
            )
        except Exception as e:
            logger.error(f"Error sending rejection message to user: {e}")

        await query.answer("❌ ክፍያ ውድቅ ሆኗል!", show_alert=True)
        # Refresh the pending payments view
        await self.show_pending_payments(query, context)

    async def handle_callback_query(self, query, context):
        """Handle all callback queries"""
        await query.answer()
        data = query.data

        # Main navigation
        if data == "admin_finance":
            await self.show_finance_dashboard(query, context)
        elif data == "user_management":
            await self.show_user_management(query, context)
        elif data == "pending_payments":
            await self.show_pending_payments(query, context)
        elif data == "successful_payments":
            await self.show_successful_payments(query, context)
        elif data == "failed_payments":
            await self.show_failed_payments(query, context)
        elif data == "payment_reports":
            await self.show_payment_reports(query, context)
        elif data == "search_payment_by_id":
            await query.answer()
            await query.edit_message_text(
                "🔍 **በገቢ ID ፈልግ**\n\n"
                "የገቢ ID ያስገቡ (ምሳሌ: 123):",
                parse_mode='Markdown'
            )
            self.user_states[query.from_user.id] = "WAITING_PAYMENT_ID_SEARCH"

        # Search types
        elif data == "search_by_id":
            await self.handle_user_search(query, context, "id")
        elif data == "search_by_username":
            await self.handle_user_search(query, context, "username")
        elif data == "search_by_phone":
            await self.handle_user_search(query, context, "phone")

        # Reports
        elif data == "report_daily":
            await self.show_daily_report(query, context)
        elif data == "report_weekly":
            await self.show_weekly_report(query, context)
        elif data == "report_monthly":
            await self.show_monthly_report(query, context)
        elif data == "report_yearly":
            await self.show_yearly_report(query, context)

        # Pagination
        elif data.startswith("pending_page_"):
            page = int(data.split("_")[-1])
            await self.show_pending_payments(query, context, page)
        elif data.startswith("successful_page_"):
            page = int(data.split("_")[-1])
            await self.show_successful_payments(query, context, page)
        elif data.startswith("failed_page_"):
            page = int(data.split("_")[-1])
            await self.show_failed_payments(query, context, page)

        # Payment actions
        elif data.startswith("approve_"):
            payment_id = data.split("_")[1]
            await self.approve_payment(query, context, payment_id)
        elif data.startswith("reject_"):
            payment_id = data.split("_")[1]
            await self.reject_payment(query, context, payment_id)
        elif data.startswith("details_"):
            await query.answer()
            payment_id = int(data.replace("details_", ""))
            await self.show_payment_details(query, context, payment_id)
        elif data.startswith("view_payment_"):
            payment_id = int(data.split("_")[2])
            await self.view_payment_details_by_id(query, context, payment_id, from_callback=True)

        # Balance management
        elif data.startswith("add_balance_"):
            user_id = data.split("_")[-1]
            await self.handle_balance_adjustment(query, context, "add", user_id)
        elif data.startswith("reduce_balance_"):
            user_id = data.split("_")[-1]
            await self.handle_balance_adjustment(query, context, "reduce", user_id)
        elif data.startswith("user_history_"):
            user_id = int(data.split("_")[-1])
            await self.show_user_payment_history(query, context, user_id)
        elif data.startswith("history_page_"):
            # Format: history_page_{user_id}_{page}
            parts = data.replace("history_page_", "").split("_")
            user_id = int(parts[0])
            page = int(parts[1])
            await self.show_user_payment_history(query, context, user_id, page)
        elif data.startswith("back_to_user_"):
            user_id = int(data.replace("back_to_user_", ""))
            # Re-show user details - we need to search again
            await query.edit_message_text(
                "🔍 የተጠቃሚ መረጃ እየጫን ነው...",
                parse_mode='Markdown'
            )
            # Get user info and show details
            conn = sqlite3.connect(config.USER_DB_PATH)
            cursor = conn.cursor()
            cursor.execute("""
                SELECT user_id, username, phone_number, first_name, last_name, balance, joined_date 
                FROM users WHERE user_id = ?
            """, (user_id,))
            user = cursor.fetchone()

            if user:
                user_id, username, phone, first_name, last_name, balance, joined_date = user
                balance = balance if balance is not None else 0

                cursor.execute("SELECT COUNT(*) FROM payments WHERE user_id = ? AND status = 'approved'", (user_id,))
                successful_payments = cursor.fetchone()[0]

                cursor.execute("SELECT SUM(amount) FROM payments WHERE user_id = ? AND status = 'approved'", (user_id,))
                total_deposited = cursor.fetchone()[0] or 0

                conn.close()

                keyboard = [
                    [InlineKeyboardButton("➕ Balance ጨምር", callback_data=f"add_balance_{user_id}")],
                    [InlineKeyboardButton("➖ Balance ቀንስ", callback_data=f"reduce_balance_{user_id}")],
                    [InlineKeyboardButton("📊 የክፍያ ታሪክ", callback_data=f"user_history_{user_id}")],
                    [InlineKeyboardButton("🔙 ወደ User Management", callback_data="user_management")]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)

                user_display = self.escape_markdown(first_name or username or f"ID:{user_id}")
                # Escape @ symbol separately for username display
                if username:
                    safe_username = "@" + self.escape_markdown(username)
                else:
                    safe_username = "N/A"
                safe_phone = self.escape_markdown(phone) if phone else 'N/A'
                safe_joined = self.escape_markdown(joined_date[:10]) if joined_date else 'N/A'

                text = (
                    f"👤 *የተጠቃሚ ሂሳብ መረጃ*\n\n"
                    f"🆔 User ID: `{user_id}`\n"
                    f"👤 ስም: {user_display}\n"
                    f"📱 Username: {safe_username}\n"
                    f"📞 ስልክ: {safe_phone}\n"
                    f"📅 የተቀላቀለበት: {safe_joined}\n\n"
                    f"💰 *የሂሳብ መረጃ:*\n"
                    f"• ወቅታዊ Balance: *{balance:,} ብር*\n"
                    f"• ጠቅላላ Deposits: {total_deposited:,} ብር\n"
                    f"• የተሳኩ ክፍያዎች: {successful_payments:,}"
                )

                await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
            else:
                conn.close()
                await query.edit_message_text("❌ ተጠቃሚ አልተገኘም!")
                await self.show_user_management(query, context)

    async def handle_admin_message(self, update, context):
        """Handle admin text messages"""
        user = update.effective_user
        text = update.message.text

        if user.id != config.ADMIN_USER_ID:
            return

        if user.id in self.user_states:
            state = self.user_states[user.id]

            # Payment ID search - HANDLE THIS FIRST
            if state == "WAITING_PAYMENT_ID_SEARCH":
                try:
                    payment_id = int(text.strip())
                    
                    # Show searching message
                    search_msg = await update.message.reply_text("🔍 እየፈልጋል...")
                    
                    # Search and display payment details
                    conn = sqlite3.connect(config.USER_DB_PATH)
                    cursor = conn.cursor()

                    cursor.execute("""
                        SELECT p.id, p.user_id, p.method, p.name, p.phone, p.account, p.amount, 
                               p.photo_file_id, p.created_at, p.status, u.username, u.first_name, u.phone_number
                        FROM payments p
                        LEFT JOIN users u ON p.user_id = u.user_id
                        WHERE p.id = ?
                    """, (payment_id,))

                    payment = cursor.fetchone()
                    conn.close()

                    # Delete searching message
                    await search_msg.delete()

                    if not payment:
                        await update.message.reply_text("❌ ገቢ አልተገኘም!")
                        if user.id in self.user_states:
                            del self.user_states[user.id]
                        return

                    # Unpack payment data
                    payment_id, user_id, method, name, phone, account, amount, photo_file_id, created_at, status, username, first_name, user_phone = payment

                    user_display = self.escape_markdown(first_name or username or f"ID:{user_id}")
                    safe_user_phone = self.escape_markdown(user_phone) if user_phone else 'N/A'
                    safe_method = self.escape_markdown(method) if method else 'N/A'
                    safe_name = self.escape_markdown(name) if name else 'N/A'
                    safe_status = self.escape_markdown(status) if status else 'pending'

                    # Status emoji
                    status_emoji = "⏳" if status == "pending" else ("✅" if status == "approved" else "❌")

                    keyboard = [[InlineKeyboardButton("🔙 ወደ Dashboard", callback_data="admin_finance")]]
                    reply_markup = InlineKeyboardMarkup(keyboard)

                    caption = (
                        f"📋 *የገቢ ዝርዝር #{payment_id}*\n\n"
                        f"👤 ተጠቃሚ: {user_display}\n"
                        f"🆔 User ID: `{user_id}`\n"
                        f"📱 የተጠቃሚ ስልክ: {safe_user_phone}\n"
                        f"💳 የክፍያ ዘዴ: {safe_method}\n"
                        f"👤 ስም: {safe_name}\n"
                    )

                    if phone:
                        safe_phone = self.escape_markdown(phone)
                        caption += f"📱 የክፍያ ስልክ: {safe_phone}\n"
                    if account:
                        safe_account = self.escape_markdown(account)
                        caption += f"🏦 Account: {safe_account}\n"

                    safe_date = self.escape_markdown(created_at[:16]) if created_at else 'N/A'

                    caption += (
                        f"💰 መጠን: *{amount:,} ብር*\n"
                        f"📅 ቀን: {safe_date}\n"
                        f"{status_emoji} ሁኔታ: {safe_status}"
                    )

                    # Send screenshot if available
                    if photo_file_id:
                        await update.message.reply_photo(
                            photo=photo_file_id,
                            caption=caption,
                            reply_markup=reply_markup,
                            parse_mode='Markdown'
                        )
                    else:
                        await update.message.reply_text(
                            caption + "\n\n📸 Screenshot: ❌ አልተላከም",
                            reply_markup=reply_markup,
                            parse_mode='Markdown'
                        )
                    
                    # Clear state after successful search
                    if user.id in self.user_states:
                        del self.user_states[user.id]
                        
                except ValueError:
                    await update.message.reply_text("❌ ትክክለኛ የገቢ ID ያስገቡ (ቁጥር)")
                    # Don't delete state so user can try again
                except Exception as e:
                    logger.error(f"Error in payment ID search: {e}", exc_info=True)
                    await update.message.reply_text(f"❌ ስህተት ተፈጥሯል። እባክዎ እንደገና ይሞክሩ።")
                    # Clear state on error
                    if user.id in self.user_states:
                        del self.user_states[user.id]
                return

            # User search
            elif state == "WAITING_USER_ID":
                try:
                    user_id = text.strip()
                    # Try to convert to int to validate it's a number
                    int(user_id)
                    await self.search_user_and_show_details(update, context, user_id, "id")
                except ValueError:
                    await update.message.reply_text("❌ ትክክለኛ User ID ያስገቡ (ቁጥር)")
                except Exception as e:
                    logger.error(f"Error in user ID search: {e}")
                    await update.message.reply_text(f"❌ ስህተት ተፈጥሯል: {str(e)}")
                finally:
                    if user.id in self.user_states:
                        del self.user_states[user.id]

            elif state == "WAITING_USERNAME":
                try:
                    username = text.strip().replace("@", "")
                    await self.search_user_and_show_details(update, context, username, "username")
                except Exception as e:
                    logger.error(f"Error in username search: {e}")
                    await update.message.reply_text(f"❌ ስህተት ተፈጥሯል: {str(e)}")
                finally:
                    if user.id in self.user_states:
                        del self.user_states[user.id]

            elif state == "WAITING_PHONE":
                try:
                    phone = text.strip()
                    await self.search_user_and_show_details(update, context, phone, "phone")
                except Exception as e:
                    logger.error(f"Error in phone search: {e}")
                    await update.message.reply_text(f"❌ ስህተት ተፈጥሯል: {str(e)}")
                finally:
                    if user.id in self.user_states:
                        del self.user_states[user.id]

            # Balance adjustments
            elif state.startswith("ADDING_BALANCE_"):
                user_id = state.split("_")[-1]
                try:
                    amount = int(text.strip())
                    if amount > 0:
                        await self.execute_balance_change(update, context, user_id, amount, "add")
                    else:
                        await update.message.reply_text("❌ ዜሮ ወይም አሉታዊ ቁጥር መጨመር አይቻልም!")
                except ValueError:
                    await update.message.reply_text("❌ ትክክለኛ መጠን ያስገቡ (ቁጥር)")
                del self.user_states[user.id]

            elif state.startswith("REDUCING_BALANCE_"):
                user_id = state.split("_")[-1]
                try:
                    amount = int(text.strip())
                    if amount > 0:
                        await self.execute_balance_change(update, context, user_id, amount, "reduce")
                    else:
                        await update.message.reply_text("❌ ዜሮ ወይም አሉታዊ ቁጥር መቀነስ አይቻልም!")
                except ValueError:
                    await update.message.reply_text("❌ ትክክለኛ መጠን ያስገቡ (ቁጥር)")
                del self.user_states[user.id]

    async def prompt_search_payment_by_id(self, query, context):
        """Prompt admin to enter payment ID"""
        user_id = query.from_user.id
        self.user_states[user_id] = "WAITING_PAYMENT_ID_SEARCH"

        await query.edit_message_text(
            "🔍 **በገቢ ID ፈልግ**\n\n"
            "የገቢ ID ያስገቡ (ምሳሌ: 123):",
            parse_mode='Markdown'
        )

    async def view_payment_details_by_id(self, update_or_query, context, payment_id, from_callback=False):
        """View full payment details including screenshot by payment ID"""
        conn = sqlite3.connect(config.USER_DB_PATH)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT p.id, p.user_id, p.method, p.name, p.phone, p.account, p.amount, 
                   p.photo_file_id, p.created_at, p.status, u.username, u.first_name, u.phone_number
            FROM payments p
            LEFT JOIN users u ON p.user_id = u.user_id
            WHERE p.id = ?
        """, (payment_id,))

        payment = cursor.fetchone()
        conn.close()

        if not payment:
            message_text = "❌ ገቢ አልተገኘም!"
            if from_callback:
                await update_or_query.answer(message_text, show_alert=True)
                # Delete the search prompt message
                try:
                    await update_or_query.message.delete()
                except:
                    pass
            else:
                await update_or_query.message.reply_text(message_text)
            return

        # Unpack payment data
        payment_id, user_id, method, name, phone, account, amount, photo_file_id, created_at, status, username, first_name, user_phone = payment

        user_display = self.escape_markdown(first_name or username or f"ID:{user_id}")
        safe_user_phone = self.escape_markdown(user_phone) if user_phone else 'N/A'
        safe_method = self.escape_markdown(method) if method else 'N/A'
        safe_name = self.escape_markdown(name) if name else 'N/A'
        safe_status = self.escape_markdown(status) if status else 'pending'

        # Status emoji
        status_emoji = "⏳" if status == "pending" else ("✅" if status == "approved" else "❌")

        keyboard = [[InlineKeyboardButton("🔙 ወደ Dashboard", callback_data="admin_finance")]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        caption = (
            f"📋 *የገቢ ዝርዝር #{payment_id}*\n\n"
            f"👤 ተጠቃሚ: {user_display}\n"
            f"🆔 User ID: `{user_id}`\n"
            f"📱 የተጠቃሚ ስልክ: {safe_user_phone}\n"
            f"💳 የክፍያ ዘዴ: {safe_method}\n"
            f"👤 ስም: {safe_name}\n"
        )

        if phone:
            safe_phone = self.escape_markdown(phone)
            caption += f"📱 የክፍያ ስልክ: {safe_phone}\n"
        if account:
            safe_account = self.escape_markdown(account)
            caption += f"🏦 Account: {safe_account}\n"

        safe_date = self.escape_markdown(created_at[:16]) if created_at else 'N/A'

        caption += (
            f"💰 መጠን: *{amount:,} ብር*\n"
            f"📅 ቀን: {safe_date}\n"
            f"{status_emoji} ሁኔታ: {safe_status}"
        )

        # Send screenshot if available
        if photo_file_id:
            if from_callback:
                await context.bot.send_photo(
                    chat_id=update_or_query.message.chat.id,
                    photo=photo_file_id,
                    caption=caption,
                    reply_markup=reply_markup,
                    parse_mode='Markdown'
                )
                # Delete the previous message
                try:
                    await update_or_query.message.delete()
                except:
                    pass
            else:
                await update_or_query.message.reply_photo(
                    photo=photo_file_id,
                    caption=caption,
                    reply_markup=reply_markup,
                    parse_mode='Markdown'
                )
        else:
            message_text = caption + "\n\n📸 Screenshot: ❌ አልተላከም"
            if from_callback:
                await update_or_query.edit_message_text(
                    message_text,
                    reply_markup=reply_markup,
                    parse_mode='Markdown'
                )
            else:
                await update_or_query.message.reply_text(
                    message_text,
                    reply_markup=reply_markup,
                    parse_mode='Markdown'
                )

# Global admin balance manager instance
admin_balance = AdminBalanceManager()