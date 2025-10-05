from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Sends usage menu with inline keyboard."""
    keyboard = [
        [InlineKeyboardButton("🎬 የፊልም ፍለጋ", callback_data='usage_film_search')],
        [InlineKeyboardButton("💰 የገቢ ማድረግ", callback_data='usage_payment')],
        [InlineKeyboardButton("🎁 የመጋበዝ መረጃ", callback_data='usage_referral')],
        [InlineKeyboardButton("❓ FAQ", callback_data='usage_faq')],
        [InlineKeyboardButton("📞 እገዛ & ድጋፍ", callback_data='usage_help')],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    sent_message = await update.message.reply_text(
        '📚 የአጠቃቀም መመሪያ & መረጃ\n\nእባክዎ ከታች ካሉት አማራጮች በመምረጥ ዝርዝር መረጃ ያግኙ።',
        reply_markup=reply_markup
    )

    # Store the message ID in user_data to delete it later
    context.user_data['usage_message_id'] = sent_message.message_id

async def handle_usage_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Sends a message with inline keyboard for usage instructions and stores its ID."""
    keyboard = [
        [InlineKeyboardButton("🎬 የፊልም ፍለጋ", callback_data='usage_film_search')],
        [InlineKeyboardButton("💰 የገቢ ማድረግ", callback_data='usage_payment')],
        [InlineKeyboardButton("🎁 የመጋበዝ መረጃ", callback_data='usage_referral')],
        [InlineKeyboardButton("❓ FAQ", callback_data='usage_faq')],
        [InlineKeyboardButton("📞 እገዛ & ድጋፍ", callback_data='usage_help')],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    # Send the message and get the sent message object
    sent_message = await update.message.reply_text(
        '📚 የአጠቃቀም መመሪያ & መረጃ\n\nእባክዎ ከታች ካሉት አማራጮች በመምረጥ ዝርዝር መረጃ ያግኙ።',
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

• ወደ ዋና ምናሌ ለመመለስ: 🏠 ወደ ዋና ምናሌ
• ሂሳብዎን ለማየት: ቀር ሂሳብ 💰
• ገንዘብ ለመጨመር: ገቢ ለማድረግ 🏦

ℹ️ ለተጨማሪ እገዛ ➽ @Henok_Chat ✅"""
        # Add back to main menu button
        keyboard = [
            [InlineKeyboardButton("🔙 ወደ አጠቃቀም ምናሌ", callback_data="usage_menu")],
            [InlineKeyboardButton("🏠 ወደ ዋና ምናሌ", callback_data="usage_back_to_menu")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(text=text, reply_markup=reply_markup)

    elif query.data == 'usage_payment':
        text = """💰 የገቢ ማድረግ አጠቃቀም መመሪያ

📋 የክፍያ ዘዴዎች:

1️⃣ **Telebirr 📱**
2️⃣ **CBEbirr 🌐**
3️⃣ **CBE Bank 🏦**
4️⃣ **Card 💳**

💵 **ዝቅተኛ ገቢ መጠን: 10 ብር**

━━━━━━━━━━━━━━━━━━━━━━
📖 የገቢ ደረጃዎች:

**1️⃣ የክፍያ ዘዴ መምረጥ**
   ▪️ "ገቢ ለማድረግ 🏦" ይጫኑ
   ▪️ የሚመችዎትን ዘዴ ይምረጡ

**2️⃣ መረጃ ማስገባት**
   ▪️ **ስልክ ቁጥር** (Telebirr/CBEbirr/Card):
      ✅ +2519XXXXXXXX ወይም 09XXXXXXXX
      ✅ +2517XXXXXXXX ወይም 07XXXXXXXX

   ▪️ **አካውንት ቁጥር** (CBE ብቻ):
      ✅ 1000 በሚል ይጀምር
      ✅ 13-16 አሃዞች

**3️⃣ ሙሉ ስም ማስገባት**
   ⚠️ ቢያንስ 3 ፊደል
   ⚠️ ቁጥር መጻፍ የለበትም

**4️⃣ የገንዘብ መጠን ማስገባት**
   💵 ዝቅተኛ: 10 ብር

**5️⃣ የክፍያ መረጃ መቀበል**
   📱 Bot የክፍያ አካውንት ይልካል
   ⚡️ ወደዚህ አካውንት ገንዘብ ይላኩ

**6️⃣ Screenshot ማስረጃ መላክ**
   📸 የክፍያ Screenshot (Photo) ይላኩ
   💳 Card: የEthiotelecom መልእክት screenshot

**7️⃣ ማረጋገጥ**
   ✅ "አረጋግጥ" የሚለውን ይጫኑ

**8️⃣ Admin ማጽደቅ መጠበቅ**
   ⏱ በ30 ደቂቃ ውስጥ
   ✅ በተቀበለ → ገንዘብ ወደ ሂሳብዎ ይገባል
   ❌ ውድቅ ከሆነ → መልእክት ይደርሰዎታል

━━━━━━━━━━━━━━━━━━━━━━
💡 ጠቃሚ ምክሮች:

• Screenshot ግልጽ መሆን አለበት
• ትክክለኛ መጠን ማስገባት
• ከላኩ በኋላ ብቻ Screenshot ይላኩ

ℹ️ ለእገዛ ➽ @Henok_Chat ✅"""
        # Add back to main menu button
        keyboard = [
            [InlineKeyboardButton("🔙 ወደ አጠቃቀም ምናሌ", callback_data="usage_menu")],
            [InlineKeyboardButton("🏠 ወደ ዋና ምናሌ", callback_data="usage_back_to_menu")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(text=text, reply_markup=reply_markup)

    elif query.data == 'usage_referral':
        text = """🎁 የመጋበዝ ስርዓት መረጃ

💡 የመጋበዝ ስርዓት እንዴት ይሰራል?

**📋 ደረጃዎች:**

1️⃣ **የእርስዎን የመጋበዝ ሊንክ ያግኙ**
   ▪️ "ለመጋበዝ 🎁" የሚለውን ይጫኑ
   ▪️ የእርስዎ የመጋበዝ ሊንክ ይመጣል

2️⃣ **ሊንክ ለጓደኞቻቸው ያጋሩ**
   ▪️ WhatsApp, Telegram, Facebook...
   ▪️ ጓደኛዎ በሊንክ ሲመዘገብ

3️⃣ **ሽልማት ያገኛሉ**
   ✨ እያንዳንዱ የመጣ ጓደኛ
   💰 የተወሰነ ገንዘብ ይቀበላሉ

━━━━━━━━━━━━━━━━━━━━━━
💡 ጠቃሚ ምክሮች:

• ብዙ ጓደኞችን ያጋብዙ
• የመጋበዝ ሊንክዎን ያጋሩ
• ሽልማትዎን በፊልም ለመግዛት ይጠቀሙ

ℹ️ ለተጨማሪ መረጃ "ለመጋበዝ 🎁" ይጫኑ።"""
        # Add back to main menu button
        keyboard = [
            [InlineKeyboardButton("🔙 ወደ አጠቃቀም ምናሌ", callback_data="usage_menu")],
            [InlineKeyboardButton("🏠 ወደ ዋና ምናሌ", callback_data="usage_back_to_menu")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(text=text, reply_markup=reply_markup)


    elif query.data == 'usage_faq':
        text = """❓ ተደጋጋሚ ጥያቄዎች (FAQ)

**💵 ፊልም ስንት ወጪ ያስከፍላል?**
   🎬 ነጠላ ፊልም: 3 ብር
   📽 ተከታታይ ፊልም: 2 ብር

**💰 እንዴት ገንዘብ ማድረግ እችላለሁ?**
   • "ገቢ ለማድረግ 🏦" ይጫኑ
   • Telebirr/CBE/CBEbirr/Card ይምረጡ
   • መመሪያውን ይከተሉ
   • ዝቅተኛ: 10 ብር

**🔍 ፊልም ካላገኘሁ?**
   • ትክክለኛ ስም መጻፉን ያረጋግጡ
   • ቢያንስ 3 ፊደል ይጻፉ
   • "🎞 ሁሉንም ፊልም" ይሞክሩ
   • Admin ያናግሩ: @Henok_Chat

**💳 ገንዘብ መቼ ይገባል?**
   ⏱ በ30 ደቂቃ ውስጥ
   ✅ Admin ካረጋገጠ በኋላ

**📸 Screenshot ካልኖረኝ?**
   • ገንዘብ ካስተላለፉ በኋላ
   • የክፍያ መልእክት screenshot ያንሱ
   • ግልጽ መሆን አለበት

**🎁 የመጋበዝ ሽልማት ስንት ነው?**
   • "ለመጋበዝ 🎁" ላይ ይመልከቱ
   • እያንዳንዱ ጓደኛ ሲመጣ
   • ሽልማት ይቀበላሉ

━━━━━━━━━━━━━━━━━━━━━━
💡 ለተጨማሪ ጥያቄዎች Admin ያነጋግሩ!

📩 @Henok_Chat ✅"""
        # Add back to main menu button
        keyboard = [
            [InlineKeyboardButton("🔙 ወደ አጠቃቀም ምናሌ", callback_data="usage_menu")],
            [InlineKeyboardButton("🏠 ወደ ዋና ምናሌ", callback_data="usage_back_to_menu")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(text=text, reply_markup=reply_markup)

    elif query.data == 'usage_help':
        text = """📞 እገዛ & ድጋፍ

🛠 **ችግር ካጋጠመዎ:**

**1️⃣ የቴክኒክ ችግሮች**
   ▪️ Bot መልስ የለውም?
   ▪️ ፊልም አይላክም?
   ▪️ ገንዘብ አልገባም?
   → Admin ያናግሩ

**2️⃣ የክፍያ ችግሮች**
   ▪️ Screenshot ተቸግረዋል?
   ▪️ ገንዘብ ላኩ ግን አልገባም?
   ▪️ የተሳሳተ መጠን አስገብተዋል?
   → Screenshot ጋር Admin ያናግሩ

**3️⃣ የፊልም ጥያቄዎች**
   ▪️ የተወሰነ ፊልም ይፈልጋሉ?
   ▪️ ፊልም ጥራት ችግር?
   ▪️ ፊልም ስም ስህተት?
   → Admin ያሳውቁ

━━━━━━━━━━━━━━━━━━━━━━
📱 **የAdmin መገናኛ:**

💬 Telegram: @Henok_Chat
⏰ የምላሽ ጊዜ: በቅርቡ
✅ ሁሌም ድጋፍ ዝግጁ ነው!

━━━━━━━━━━━━━━━━━━━━━━
💡 **ጠቃሚ መረጃ:**

• Bot 24/7 ይሰራል
• ፊልም ወዲያውኑ ይላካል (ሂሳብ ካለ)
• ገንዘብ በ30 ደቂቃ ውስጥ ይገባል
• የመጋበዝ ስርዓት ሽልማት አለው

ℹ️ ለማንኛውም ጥያቄ ➽ @Henok_Chat ✅"""
        # Add back to main menu button
        keyboard = [
            [InlineKeyboardButton("🔙 ወደ አጠቃቀም ምናሌ", callback_data="usage_menu")],
            [InlineKeyboardButton("🏠 ወደ ዋና ምናሌ", callback_data="usage_back_to_menu")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(text=text, reply_markup=reply_markup)

    elif query.data == 'usage_back' or query.data == 'usage_menu':
        # This brings the user back to the main usage menu
        keyboard = [
            [InlineKeyboardButton("🎬 የፊልም ፍለጋ", callback_data='usage_film_search')],
            [InlineKeyboardButton("💰 የገቢ ማድረግ", callback_data='usage_payment')],
            [InlineKeyboardButton("🎁 የመጋበዝ መረጃ", callback_data='usage_referral')],
            [InlineKeyboardButton("❓ FAQ", callback_data='usage_faq')],
            [InlineKeyboardButton("📞 እገዛ & ድጋፍ", callback_data='usage_help')],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(
            '📚 የአጠቃቀም መመሪያ & መረጃ\n\nእባክዎ ከታች ካሉት አማራጮች በመምረጥ ዝርዝር መረጃ ያግኙ።',
            reply_markup=reply_markup
        )
        # We also need to store the ID again if they go back to the menu
        context.user_data['usage_message_id'] = query.message.message_id

    elif query.data == "usage_back_to_menu":
        # Return to main menu
        from bot import get_main_keyboard
        try:
            await query.message.delete()
        except:
            pass
        await context.bot.send_message(
            chat_id=query.message.chat.id,
            text="🏠 ወደ ዋና ምናሌ ተመልሰዋል",
            reply_markup=get_main_keyboard()
        )


# Placeholder functions for other usage callbacks
async def show_single_movie_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
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

• ወደ ዋና ምናሌ ለመመለስ: 🏠 ወደ ዋና ምናሌ
• ሂሳብዎን ለማየት: ቀር ሂሳብ 💰
• ገንዘብ ለመጨመር: ገቢ ለማድረግ 🏦

ℹ️ ለተጨማሪ እገዛ ➽ @Henok_Chat ✅"""
    keyboard = [
        [InlineKeyboardButton("🔙 ወደ አጠቃቀም ምናሌ", callback_data="usage_menu")],
        [InlineKeyboardButton("🏠 ወደ ዋና ምናሌ", callback_data="usage_back_to_menu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    if update.message:
        await update.message.reply_text(text, parse_mode='Markdown', reply_markup=reply_markup)
    else:
        await update.callback_query.edit_message_text(text, parse_mode='Markdown', reply_markup=reply_markup)

async def show_series_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = """📽 ተከታታይ ፊልሞች አጠቃቀም መመሪያ

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

• ወደ ዋና ምናሌ ለመመለስ: 🏠 ወደ ዋና ምናሌ
• ሂሳብዎን ለማየት: ቀር ሂሳብ 💰
• ገንዘብ ለመጨመር: ገቢ ለማድረግ 🏦

ℹ️ ለተጨማሪ እገዛ ➽ @Henok_Chat ✅"""
    keyboard = [
        [InlineKeyboardButton("🔙 ወደ አጠቃቀም ምናሌ", callback_data="usage_menu")],
        [InlineKeyboardButton("🏠 ወደ ዋና ምናሌ", callback_data="usage_back_to_menu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    if update.message:
        await update.message.reply_text(text, parse_mode='Markdown', reply_markup=reply_markup)
    else:
        await update.callback_query.edit_message_text(text, parse_mode='Markdown', reply_markup=reply_markup)

async def show_all_films_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = """🎞 ሁሉንም ፊልሞች አጠቃቀም መመሪያ

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

• ወደ ዋና ምናሌ ለመመለስ: 🏠 ወደ ዋና ምናሌ
• ሂሳብዎን ለማየት: ቀር ሂሳብ 💰
• ገንዘብ ለመጨመር: ገቢ ለማድረግ 🏦

ℹ️ ለተጨማሪ እገዛ ➽ @Henok_Chat ✅"""
    keyboard = [
        [InlineKeyboardButton("🔙 ወደ አጠቃቀም ምናሌ", callback_data="usage_menu")],
        [InlineKeyboardButton("🏠 ወደ ዋና ምናሌ", callback_data="usage_back_to_menu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    if update.message:
        await update.message.reply_text(text, parse_mode='Markdown', reply_markup=reply_markup)
    else:
        await update.callback_query.edit_message_text(text, parse_mode='Markdown', reply_markup=reply_markup)

async def show_balance_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = """💰 ሂሳብ እና ገቢ አጠቃቀም መመሪያ

💡 **የሂሳብዎ ሁኔታ:**
   • እርስዎ ያሎትን ቀሪ ሂሳብ ያሳያል

💡 **ገቢ የማድረግ መንገዶች:**
   • "ገቢ ለማድረግ 🏦" የሚለውን ይጫኑ
   • Telebirr, CBEbirr, CBE Bank, Card

━━━━━━━━━━━━━━━━━━━━━━
📖 **የገቢ ሂደት:**
   1. የክፍያ ዘዴ ይምረጡ
   2. አስፈላጊውን መረጃ ያስገቡ
   3. የገንዘብ መጠን ይጻፉ
   4. Bot የላከውን አካውንት ይቅዱ
   5. ገንዘብ ይላኩ
   6. የክፍያ Screenshot ይላኩ
   7. "አረጋግጥ" የሚለውን ይጫኑ
   8. Admin እስኪያጸድቅ ይጠብቁ (በ30 ደቂቃ)

━━━━━━━━━━━━━━━━━━━━━━
💡 ጠቃሚ ምክሮች:

• ትክክለኛውን የክፍያ አካውንት ይጠቀሙ
• Screenshot ግልጽ መሆን አለበት
• ዝቅተኛ ገቢ 10 ብር ነው

ℹ️ ለተጨማሪ ጥያቄ Admin ን ያነጋግሩ።"""
    keyboard = [
        [InlineKeyboardButton("🔙 ወደ አጠቃቀም ምናሌ", callback_data="usage_menu")],
        [InlineKeyboardButton("🏠 ወደ ዋና ምናሌ", callback_data="usage_back_to_menu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    if update.message:
        await update.message.reply_text(text, parse_mode='Markdown', reply_markup=reply_markup)
    else:
        await update.callback_query.edit_message_text(text, parse_mode='Markdown', reply_markup=reply_markup)

async def show_referral_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = """🎁 የመጋበዝ ስርዓት መረጃ

💡 የመጋበዝ ስርዓት እንዴት ይሰራል?

**📋 ደረጃዎች:**

1️⃣ **የእርስዎን የመጋበዝ ሊንክ ያግኙ**
   ▪️ "ለመጋበዝ 🎁" የሚለውን ይጫኑ
   ▪️ የእርስዎ የመጋበዝ ሊንክ ይመጣል

2️⃣ **ሊንክ ለጓደኞቻቸው ያጋሩ**
   ▪️ WhatsApp, Telegram, Facebook...
   ▪️ ጓደኛዎ በሊንክ ሲመዘገብ

3️⃣ **ሽልማት ያገኛሉ**
   ✨ እያንዳንዱ የመጣ ጓደኛ
   💰 የተወሰነ ገንዘብ ይቀበላሉ

━━━━━━━━━━━━━━━━━━━━━━
💡 ጠቃሚ ምክሮች:

• ብዙ ጓደኞችን ያጋብዙ
• የመጋበዝ ሊንክዎን ያጋሩ
• ሽልማትዎን በፊልም ለመግዛት ይጠቀሙ

ℹ️ ለተጨማሪ መረጃ "ለመጋበዝ 🎁" ይጫኑ።"""
    keyboard = [
        [InlineKeyboardButton("🔙 ወደ አጠቃቀም ምናሌ", callback_data="usage_menu")],
        [InlineKeyboardButton("🏠 ወደ ዋና ምናሌ", callback_data="usage_back_to_menu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    if update.message:
        await update.message.reply_text(text, parse_mode='Markdown', reply_markup=reply_markup)
    else:
        await update.callback_query.edit_message_text(text, parse_mode='Markdown', reply_markup=reply_markup)

async def show_menu_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles the callback for returning to the usage menu."""
    keyboard = [
        [InlineKeyboardButton("🎬 የፊልም ፍለጋ", callback_data='usage_film_search')],
        [InlineKeyboardButton("💰 የገቢ ማድረግ", callback_data='usage_payment')],
        [InlineKeyboardButton("🎁 የመጋበዝ መረጃ", callback_data='usage_referral')],
        [InlineKeyboardButton("❓ FAQ", callback_data='usage_faq')],
        [InlineKeyboardButton("📞 እገዛ & ድጋፍ", callback_data='usage_help')],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.callback_query.edit_message_text(
        '📚 የአጠቃቀም መመሪያ & መረጃ\n\nእባክዎ ከታች ካሉት አማራጮች በመምረጥ ዝርዝር መረጃ ያግኙ።',
        reply_markup=reply_markup
    )