from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Sends a simple help message."""
    await update.message.reply_text("ℹ️ ለተጨማሪ እገዛ እኛን ያግኙ ➲ @Henok_Chat ✅")

async def handle_usage_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Sends a message with inline keyboard for usage instructions and stores its ID."""
    keyboard = [
        [InlineKeyboardButton("🍿 የፊልም ፍለጋ አጠቃቀም", callback_data='usage_film_search')],
        [InlineKeyboardButton("🏦 የገቢ ማድረግ አጠቃቀም", callback_data='usage_payment')],
        [InlineKeyboardButton("❓ እገዛ", callback_data='usage_help')],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # Send the message and get the sent message object
    sent_message = await update.message.reply_text(
        '❓ የአጠቃቀም መመሪያ\n\nእባክዎ ከታች ካሉት አማራጮች በመምረጥ ዝርዝር መረጃ ያግኙ።\n\n ወደ menu ለመመለስ',
        reply_markup=reply_markup
    )
    
    # Store the message ID in user_data to delete it later
    context.user_data['usage_message_id'] = sent_message.message_id

async def handle_usage_callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles callbacks from the usage inline keyboard."""
    query = update.callback_query
    await query.answer()

    # When a button is clicked, we should clear the stored message_id
    # so the message isn't deleted if the user types something after clicking.
    if 'usage_message_id' in context.user_data:
        del context.user_data['usage_message_id']

    # Keyboard for the back button - consistent across all detail views
    back_keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ ወደ ኋላ", callback_data='usage_back')]])

    if query.data == 'usage_film_search':
        text = """🎬 የፊልም ፍለጋ አጠቃቀም መመሪያ

📚 የፍለጋ ዓይነቶች:

1️⃣ **ነጠላ ፊልም 🎬**
   💵 ዋጋ: 3 ብር
   ✅ የነጠላ ፊልሞችን ብቻ ይፈልጋል
   
2️⃣ **ተከታታይ ፊልም 📽**
   💵 ዋጋ: 2 ብር
   ✅ የተከታታይ ፊልሞችን ብቻ ይፈልጋል
   
3️⃣ **ሁሉንም ፊልም 🎞**
   💵 ዋጋ: እንደ ዓይነቱ (3 ብር ወይም 2 ብር)
   ✅ በሁለቱም ዳታቤዝ ውስጥ ይፈልጋል

━━━━━━━━━━━━━━━━━━━━━━
📖 እንዴት መጠቀም እንደሚቻል:

▪️ የፊልም ዓይነት ይምረጡ (ከላይ ከተጠቀሱት)

▪️ የፊልም ስም ይጻፉ:
   ⚠️ ቢያንስ 3 ፊደል ይጻፉ
   ⚠️ ከ60 ፊደል በላይ አይጻፉ
   💡 የትክክለኛውን ስም መጻፍ ይሞክሩ

▪️ ከውጤቱ የሚፈልጉትን ፊልም ይምረጡ
   📄 በገጽ 5 ፊልሞች ብቻ ይታያሉ
   ◀️ "ቀድሞ" / "ቀጣይ" ▶️ ለማለፍ

▪️ ፊልም ሲጫኑ:
   ✅ በቂ ሂሳብ ካለ ፊልም ይላካል
   ❌ ሂሳብ ካልበቃ ገቢ ማድረግ ያስፈልጋል

━━━━━━━━━━━━━━━━━━━━━━
💡 ጠቃሚ ምክሮች:

• ወደ ዋና ምናሌ ለመመለስ: ⬅️ ለመመለስ
• ሂሳብዎን ለማየት: ቀር ሂሳብ 💰
• ገንዘብ ለመጨመር: ገቢ ለማድረግ 🏦

ℹ️ ለተጨማሪ እገዛ ➽ @Henok_Chat ✅"""
        await query.edit_message_text(text=text, reply_markup=back_keyboard)

    elif query.data == 'usage_payment':
        text = """🏦 የገቢ ማድረግ አጠቃቀም

1. ገቢ ለማድረግ "ገቢ ለማድረግ 🏦" የምል ይጫኑ

2. 💰 የክፍያ ዘዴ ይምረጡ
📱 Telebirr  |  🏦 CBE
🌐 CBEbirr  |  💳 Card

3.🧾 አንዱን በመምረጥ እርሱ ስም ስጠይቅ ያስገቡ 

4.♻️ የእርሱ ስልክ ቁጥር ወይንም Account ቁጥር ስጠይቅ ያስገቡ

5.✳️ ገቢ ለማድረግ የፈለጉትን የብር መጠን ያስገቡ

6.❇️ የክፍያ Account ወይንም ስልክ ቁጥር ስመጣ በዚህ ቁጥር ገቢ በማድረግ Screenshot photo ይላኩ

7.➰ የክፍያ መረጃ በማየት አረጋግጥ የምል ይጫኑ

8.✔️ ከዚህያ በኋላ ብር ወደ Account ገቢ ይሆናል

                  📩 @Henok_Chat ☑️"""
        await query.edit_message_text(text=text, reply_markup=back_keyboard)

    elif query.data == 'usage_help':
        text ="ℹ️ ለተጨማሪ እገዛ እኛን ያግኙ ➲ @Hnok_Chat✅"
        await query.edit_message_text(text=text, reply_markup=back_keyboard)

    elif query.data == 'usage_back':
        # This brings the user back to the main usage menu
        keyboard = [
            [InlineKeyboardButton("🍿 የፊልም ፍለጋ አጠቃቀም", callback_data='usage_film_search')],
            [InlineKeyboardButton("🏦 የገቢ ማድረግ አጠቃቀም", callback_data='usage_payment')],
            [InlineKeyboardButton("❓ እገዛ", callback_data='usage_help')],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        sent_message = await query.edit_message_text(
            '❓ የአጠቃቀም መመሪያ\n\nእባክዎ ከታች ካሉት አማራጮች በመምረጥ ዝርዝር መረጃ ያግኙ።\n\n ወደ menu ለመመለስ',
            reply_markup=reply_markup
        )
        # We also need to store the ID again if they go back to the menu
        context.user_data['usage_message_id'] = query.message.message_id
