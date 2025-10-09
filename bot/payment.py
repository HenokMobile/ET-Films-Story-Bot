import sqlite3
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import ContextTypes
from config import ADMIN_USER_ID, USER_DB_PATH

logger = logging.getLogger(__name__)

# የክፍያ መረጃዎች
PAYMENT_ACCOUNTS = {
    "Telebirr": {"phone": "0974363991", "name": "Henok Belayneh"},
    "CBEbirr": {"phone": "0974363991", "name": "Henok Belayneh"},
    "CBE": {"account": "1000647265123", "name": "Henok Belayneh"},
    "Card": {"phone": "0974363991", "name": "Ethiotelecom"}
}

MIN_DEPOSIT_REGULAR = 10
MIN_DEPOSIT_CARD = 10

class PaymentSystem:
    def __init__(self):
        self.payment_sessions = {}

    def is_valid_phone(self, phone):
        """የስልክ ቁጥር ማረጋገጫ - ኢትዮቴሌኮም እና ሳፋሪኮም"""
        if not phone:
            return False
        phone = phone.strip()
        return (
            (phone.startswith('+2519') and len(phone) == 13) or  # Ethio Telecom
            (phone.startswith('+2517') and len(phone) == 13) or  # Safaricom
            (phone.startswith('09') and len(phone) == 10) or     # Ethio Telecom
            (phone.startswith('07') and len(phone) == 10)        # Safaricom
        )

    def is_valid_account(self, account):
        """የባንክ አካውንት ቁጥር ማረጋገጫ - CBE ብቻ"""
        if not account:
            return False
        account = account.strip()
        # 1000 በሚል መጀመር እና 13-16 አሃዞች መሆን አለበት
        return account.startswith('1000') and 13 <= len(account) <= 16 and account.isdigit()

    def is_valid_amount(self, amount_str):
        """የገንዘብ መጠን ማረጋገጫ"""
        try:
            amount = float(amount_str.strip())
            return int(amount) if amount > 0 else None
        except:
            return None

    def is_valid_name(self, name):
        """የስም ማረጋገጫ - ቁጥሮች የተከለከሉ፣ ቢያንስ 3 ቁምፊ"""
        if not name or len(name.strip()) < 3:
            return False
        # ቁጥሮች መኖራቸውን መፈተሽ
        if any(char.isdigit() for char in name):
            return False
        return True

    def create_payment_keyboard(self):
        """የክፍያ ዘዴ ምረጃ keyboard"""
        keyboard = [
            ["📱 Telebirr", "🏦 CBE"],
            ["🌐 CBEbirr", "💳 Card"],
            ["↩️ ለመመለስ"]
        ]
        return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

    def create_back_keyboard(self):
        """የመመለስ button keyboard"""
        keyboard = [["↩️ ለመመለስ"]]
        return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

    def create_confirm_keyboard(self):
        """የማረጋገጫ button keyboard"""
        keyboard = [["✅ አረጋግጥ", "↩️ ለመመለስ"]]
        return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

    async def show_payment_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """የክፍያ ዘዴ ምረጫ ማሳያ"""
        user_id = update.effective_user.id

        text = """💰 የክፍያ ዘዴ ይምረጡ

📱 Telebirr  |  🏦 CBE
🌐 CBEbirr  |  💳 Card"""

        self.payment_sessions[user_id] = {
            'step': 'method'
        }

        await update.message.reply_text(
            text,
            reply_markup=self.create_payment_keyboard()
        )

    async def process_payment_method(self, update: Update, context: ContextTypes.DEFAULT_TYPE, method: str):
        """የተመረጠ የክፍያ ዘዴ አፈጻጸም"""
        user_id = update.effective_user.id
        session = self.payment_sessions.get(user_id)

        if not session or session['step'] != 'method':
            return

        session['method'] = method

        if method in ["Telebirr", "CBEbirr"]:
            session['step'] = 'phone'
            await update.message.reply_text(
                f"📌የእርስዎን የ{method} ስልክ ቁጥር ያስገቡ",
                reply_markup=self.create_back_keyboard()
            )

        elif method == "CBE":
            session['step'] = 'account'
            await update.message.reply_text(
                "📌የእርስዎን Account ቁጥር ያስገቡ",
                reply_markup=self.create_back_keyboard()
            )

        elif method == "Card":
            session['step'] = 'phone'
            await update.message.reply_text(
                "📌የእርስዎን ስልክ ቁጥር ያስገቡ",
                reply_markup=self.create_back_keyboard()
            )

    async def process_input(self, update: Update, context: ContextTypes.DEFAULT_TYPE, input_type: str, value: str):
        """የተለያዩ inputs አፈጻጸም"""
        user_id = update.effective_user.id
        session = self.payment_sessions.get(user_id)

        if not session:
            return

        # የእያንዳንዱ input ማረጋገጫ
        if input_type == 'phone' and not self.is_valid_phone(value):
            await update.message.reply_text("❌ ትክክለኛ ስልክ ቁጥር ያስገቡ!\n📱 ምሳሌ: +2519******** ወይም 09********")
            return

        elif input_type == 'account' and not self.is_valid_account(value):
            await update.message.reply_text("❌ ትክክለኛ የCBE አካውንት ቁጥር ያስገቡ!\n🏦 1000 በሚል መጀመር፣ 13-16 አሃዞች")
            return

        elif input_type == 'name' and not self.is_valid_name(value):
            await update.message.reply_text("❌ ትክክለኛ ስም ያስገቡ!\n👤 ቢያንስ 3 ፊደል፣ ቁጥር የለም")
            return

        elif input_type == 'amount':
            amount = self.is_valid_amount(value)
            if not amount:
                await update.message.reply_text("❌ ትክክለኛ መጠን ያስገቡ! ቁጥር ብቻ")
                return

            min_amount = MIN_DEPOSIT_CARD if session['method'] == 'Card' else MIN_DEPOSIT_REGULAR
            if amount < min_amount:
                await update.message.reply_text(f"❌ ዝቅተኛ ማስገባት የምችሉት {min_amount} ብር ነው!")
                return

            session['amount'] = amount

        # input ማስቀመጥ
        session[input_type] = value

        # ወደ ቀጣይ ደረጃ መሄድ
        await self.next_step(update, context)

    async def next_step(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """ወደ ቀጣይ ደረጃ መሄድ"""
        user_id = update.effective_user.id
        session = self.payment_sessions.get(user_id)

        if not session:
            return

        current_step = session['step']

        if current_step in ['phone', 'account', 'card_info']:
            # ወደ ስም input መሄድ
            session['step'] = 'name'
            await update.message.reply_text(
                "📌የእርስዎን ሙሉ ስም ያስገቡ",
                reply_markup=self.create_back_keyboard()
            )

        elif current_step == 'name':
            # ወደ መጠን input መሄድ
            session['step'] = 'amount'
            min_amount = MIN_DEPOSIT_CARD if session['method'] == 'Card' else MIN_DEPOSIT_REGULAR
            await update.message.reply_text(
                f"💵 የገንዘብ መጠን ያስገቡ\n\nዝቅተኛ መጠን: {min_amount} ብር",
                reply_markup=self.create_back_keyboard()
            )

        elif current_step == 'amount':
            # ወደ screenshot ጥያቄ መሄድ
            session['step'] = 'screenshot'
            await self.show_payment_info(update, context)

    async def show_payment_info(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """የክፍያ አካውንት መረጃ ማሳያ እና screenshot ጥያቄ"""
        user_id = update.effective_user.id
        session = self.payment_sessions.get(user_id)

        if not session:
            return

        method = session['method']
        payment_info = PAYMENT_ACCOUNTS[method]

        if method == "Telebirr":
            full_text = f"""💰 ክፍያ ለመፈጸም

📱 Telebirr
• ስልክ ቁጥር: `{payment_info['phone']}`
• ስም: `{payment_info['name']}`

⚠️ ገንዘብ ከላኩ በኋላ የክፍያ 📸Screenshot ማስረጃ ይላኩ"""

        elif method == "CBEbirr":
            full_text = f"""💰 ክፍያ ለመፈጸም

🌐 CBEbirr
• ስልክ ቁጥር: `{payment_info['phone']}`
• ስም: `{payment_info['name']}`

⚠️ ገንዘብ ከላኩ በኋላ የክፍያ 📸Screenshot ማስረጃ ይላኩ"""

        elif method == "CBE":
            full_text = f"""💰 ክፍያ ለመፈጸም

🏦 CBE
• አካውንት ቁጥር: `{payment_info['account']}`
• ስም: `{payment_info['name']}`

⚠️ ገንዘብ ከላኩ በኋላ የክፍያ 📸Screenshot ማስረጃ ይላኩ"""

        elif method == "Card":
            full_text = f"""💰 ክፍያ ለመፈጸም

💳 Card
• ስልክ ቁጥር: `{payment_info['phone']}`
• ስም: `{payment_info['name']}`

⚠️ ገንዘብ ከላኩ በኋላ ከEthiotelecom የመጣ 🗨️ messages 📸Screenshot አንስቶ ይላኩ"""

        # Send main message
        await update.message.reply_text(
            full_text,
            reply_markup=self.create_back_keyboard(),
            parse_mode='Markdown'
        )

    async def process_screenshot(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Screenshot አፈጻጸም - 1 photo ብቻ"""
        user_id = update.effective_user.id
        session = self.payment_sessions.get(user_id)

        if not session or session['step'] != 'screenshot':
            return

        if not update.message.photo:
            await update.message.reply_text(
                "❌ እባክዎ የክፍያ 📸Screenshot (Photo) ያላኩ!"
            )
            return

        # photo file ID ማስቀመጥ (1 photo ብቻ)
        session['photo_file_id'] = update.message.photo[-1].file_id
        session['step'] = 'confirm'

        # ማረጋገጫ ማሳያ
        await self.show_confirmation(update, context)

    async def handle_back_in_screenshot(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """screenshot ደረጃ ላይ back button አፈጻጸም"""
        user_id = update.effective_user.id
        session = self.payment_sessions.get(user_id)
        
        if session and session['step'] == 'screenshot':
            # ወደ amount ደረጃ መመለስ
            session['step'] = 'amount'
            min_amount = MIN_DEPOSIT_CARD if session['method'] == 'Card' else MIN_DEPOSIT_REGULAR
            
            await update.message.reply_text(
                f"💵 የገንዘብ መጠን ያስገቡ\n\nዝቅተኛ መጠን: {min_amount} ብር",
                reply_markup=self.create_back_keyboard()
            )
            return True
        
        return False

    async def show_confirmation(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """የክፍያ ማረጋገጫ ዝርዝር ማሳያ"""
        user_id = update.effective_user.id
        session = self.payment_sessions.get(user_id)

        if not session:
            return

        confirm_text = f"📝 የክፍያ መረጃ አረጋግጥ\n\n💳 የክፍያ ዘዴ: {session['method']}\n👤 ስም: {session.get('name', 'N/A')}"

        if 'phone' in session:
            confirm_text += f"\n📱 ስልክ ቁጥር: {session['phone']}"

        if 'account' in session:
            confirm_text += f"\n🏦 አካውንት ቁጥር: {session['account']}"

        if 'card_info' in session:
            confirm_text += f"\n💳 ስልክ ቁጥር: {session['card_info']}"

        confirm_text += f"\n💰የገንዘብ መጠን: {session['amount']} ብር ነው\n📸 Screenshot: ✅ ተልክዋል\n\nለማረጋገጥ 'አረጋግጥ' የምለውን ይጫኑ\n\nለእገዛ [Admin](https://t.me/Henok_Chat) ያነጋግሩ።"

        await update.message.reply_text(
            confirm_text,
            reply_markup=self.create_confirm_keyboard()
        )

    async def confirm_payment(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """ክፍያ ማረጋገጥ እና አፈጻጸም"""
        user_id = update.effective_user.id
        session = self.payment_sessions.get(user_id)

        if not session or session['step'] != 'confirm':
            return

        # የክፍያ ጥያቄ ወደ database ማስቀመጥ
        conn = sqlite3.connect(USER_DB_PATH)
        cursor = conn.cursor()

        # የክፍያ ጥያቄ ማስገባት
        cursor.execute('''
            INSERT INTO payments (user_id, method, name, phone, account, amount, photo_file_id)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (
            user_id,
            session['method'],
            session.get('name'),
            session.get('phone'),
            session.get('account'),
            session['amount'],
            session.get('photo_file_id')
        ))

        payment_id = cursor.lastrowid
        conn.commit()
        conn.close()

        # Import main keyboard
        from bot import get_main_keyboard

        # ለተጠቃሚ ማረጋገጫ መላክ እና ወደ ዋና menu መመለስ
        await update.message.reply_text(
            "✅ የክፍያ ጥያቄዎ ተልክዋል!\n\n"
            "💰 ገንዘብ በ30ደቂቃ ውስጥ ገቢ ይደረጋል\n\n"
            "🏠 ወደ ዋና ምናሌ ተመልሰዋል",
            reply_markup=get_main_keyboard()
        )

        # ለAdmin ማሳወቂያ መላክ
        try:
            user_data = await context.bot.get_chat(user_id)
            
            # Get user's registered phone from database
            conn = sqlite3.connect(USER_DB_PATH)
            cursor = conn.cursor()
            cursor.execute('SELECT username, phone_number FROM users WHERE user_id = ?', (user_id,))
            user_info = cursor.fetchone()
            conn.close()
            
            username = user_info[0] if user_info and user_info[0] else 'N/A'
            registered_phone = user_info[1] if user_info and user_info[1] else 'N/A'
            
            admin_text = f"""
🔔 አዲስ የገቢ ጥያቄ

👤 ተጠቃሚ: {user_data.first_name or 'Unknown'}
🆔 User ID: {user_id}
👤 Username: @{username}
📱 የተመዘገበ ስልክ: {registered_phone}
💳 የክፍያ ዘዴ: {session['method']}
👤 በክፍያ ስም: {session.get('name', 'N/A')}
"""

            if 'phone' in session:
                admin_text += f"📱 የክፍያ ስልክ: {session['phone']}\n"
            if 'account' in session:
                admin_text += f"🏦 አካውንት: {session['account']}\n"
            if 'card_info' in session:
                admin_text += f"💳 ካርድ: {session['card_info']}\n"

            admin_text += f"💰 መጠን: {session['amount']} ብር\n🆔 Payment ID: {payment_id}"

            # የAdmin ማጽደቂያ keyboard መፍጠር
            keyboard = [
                [InlineKeyboardButton("✅ ተቀብል", callback_data=f"approve_payment_{payment_id}")],
                [InlineKeyboardButton("❌ ውድቅ", callback_data=f"reject_payment_{payment_id}")],
                [InlineKeyboardButton("💬 መልእክት ላክ", callback_data=f"message_user_{user_id}")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)

            # ለAdmin መላክ
            if 'photo_file_id' in session:
                await context.bot.send_photo(
                    ADMIN_USER_ID,
                    session['photo_file_id'],
                    caption=admin_text,
                    reply_markup=reply_markup
                )
            else:
                await context.bot.send_message(ADMIN_USER_ID, admin_text, reply_markup=reply_markup)

        except Exception as e:
            logger.error(f"Error sending to admin: {e}")

        # session ማጽዳት
        if user_id in self.payment_sessions:
            del self.payment_sessions[user_id]

    async def handle_admin_approval(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """የAdmin ማጽደቂያ/ውድቅ አፈጻጸም"""
        query = update.callback_query
        await query.answer()

        if query.from_user.id != ADMIN_USER_ID:
            await query.edit_message_text("❌ እርስዎ አድሚን አይደሉም!")
            return

        data_parts = query.data.split('_')
        action = data_parts[0]  # approve or reject
        payment_id = data_parts[2]

        conn = sqlite3.connect(USER_DB_PATH)
        cursor = conn.cursor()

        # የክፍያ ዝርዝሮች ማግኘት - Select specific columns
        cursor.execute('''
            SELECT id, user_id, method, name, phone, account, amount, photo_file_id, created_at, status 
            FROM payments WHERE id = ?
        ''', (payment_id,))
        payment = cursor.fetchone()

        if not payment:
            await query.edit_message_text("❌ ክፍያ አልተገኘም!")
            conn.close()
            return

        # Unpack with correct indices
        payment_id, user_id, method, name, phone, account, amount, photo_file_id, created_at, status = payment
        
        # Validate amount
        try:
            amount = int(amount)
        except (ValueError, TypeError):
            logger.error(f"Invalid amount in payment {payment_id}: {amount}")
            await query.edit_message_text("❌ የክፍያ መጠን ስህተት አለበት!")
            conn.close()
            return

        if action == "approve":
            # የክፍያ ሁኔታ ማሻሻል
            cursor.execute('UPDATE payments SET status = ? WHERE id = ?', ('approved', payment_id))

            # ለተጠቃሚ ባለንስ መጨመር - ensure balance is never NULL
            cursor.execute('UPDATE users SET balance = COALESCE(balance, 0) + ? WHERE user_id = ?', (amount, user_id))
            conn.commit()
            conn.close()

            try:
                await context.bot.send_message(user_id, f"✅ የክፍያ ጥያቄዎ ተቀባይነት አግኝቷል!\n💰 {amount} ብር ወደ ሂሳብዎ ተጨምሯል።")
            except:
                pass

            # Admin message ማሻሻል
            try:
                if query.message.photo:
                    await query.edit_message_caption(
                        caption=f"✅ ክፍያ ተቀባይነት አግኝቷል!\nተጠቃሚ: {user_id}\nመጠን: {amount} ብር"
                    )
                else:
                    await query.edit_message_text(f"✅ ክፍያ ተቀባይነት አግኝቷል!\nተጠቃሚ: {user_id}\nመጠን: {amount} ብር")
            except Exception as e:
                logger.error(f"Error editing admin message: {e}")

        elif action == "reject":
            # የክፍያ ሁኔታ ማሻሻል
            cursor.execute('UPDATE payments SET status = ? WHERE id = ?', ('rejected', payment_id))
            conn.commit()
            conn.close()

            try:
                await context.bot.send_message(user_id, "❌ የክፍያ ጥያቄዎ ውድቅ ሆኗል። እባክዎ እንደገና ይሞክሩ ወይም አድሚንን ያነጋግሩ። 📩 @Henok_Chat ☑️")
            except:
                pass

            # Admin message ማሻሻል
            try:
                if query.message.photo:
                    await query.edit_message_caption(
                        caption=f"❌ ክፍያ ውድቅ ሆኗል!\nተጠቃሚ: {user_id}\nመጠን: {amount} ብር"
                    )
                else:
                    await query.edit_message_text(f"❌ ክፍያ ውድቅ ሆኗል!\nተጠቃሚ: {user_id}\nመጠን: {amount} ብር")
            except Exception as e:
                logger.error(f"Error editing admin message: {e}")

# Global payment system instance መፍጠር
payment_system = PaymentSystem()
