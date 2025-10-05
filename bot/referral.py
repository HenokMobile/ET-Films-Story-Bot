import logging
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes
from database import db
import config

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

REFERRAL_REWARD = 2

class ReferralSystem:
    def __init__(self, reward_amount=REFERRAL_REWARD):
        self.reward_amount = reward_amount
    
    async def process_referral(self, new_user_id, referrer_id, context: ContextTypes.DEFAULT_TYPE):
        """Process a new referral and reward the referrer"""
        try:
            if new_user_id == referrer_id:
                logger.warning(f"User {new_user_id} tried to refer themselves")
                return False
            
            if not db.user_exists(referrer_id):
                logger.warning(f"Referrer {referrer_id} does not exist")
                return False
            
            existing_referrer = db.get_referrer(new_user_id)
            if existing_referrer is not None:
                logger.warning(f"User {new_user_id} already has a referrer: {existing_referrer}")
                return False
            
            db.set_referrer(new_user_id, referrer_id)
            db.increment_referral_count(referrer_id)
            db.add_referral_earnings(referrer_id, self.reward_amount)
            
            referrer_stats = db.get_referral_stats(referrer_id)
            
            # Send notification to referrer
            await context.bot.send_message(
                chat_id=referrer_id,
                text=f"🎉 እንኳን ደስ አለዎ!\n\n"
                     f"አዲስ ጓደኛ በእርስዎ ሊንክ ተቀላቅሏል! 🎁\n\n"
                     f"💰 ሽልማት: +{self.reward_amount} ብር\n"
                     f"👥 ጠቅላላ ግብዣዎች: {referrer_stats['referral_count']}\n"
                     f"💵 ጠቅላላ ገቢ: {referrer_stats['total_earnings']} ብር"
            )
            
            logger.info(f"Referral processed: User {new_user_id} referred by {referrer_id}. Reward: {self.reward_amount} Birr")
            return True
            
        except Exception as e:
            logger.error(f"Error processing referral: {e}")
            return False
    
    async def show_referral_info(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show referral link and statistics for the referrer"""
        from bot import get_main_keyboard
        user = update.effective_user
        
        try:
            # Get bot info to get username
            bot_info = await context.bot.get_me()
            logger.info(f"DEBUG: Bot info = {bot_info}")
            logger.info(f"DEBUG: Bot username = {bot_info.username if bot_info else 'bot_info is None'}")
            
            bot_username = bot_info.username if bot_info else None
            
            # Validate bot username
            if not bot_username:
                logger.error(f"Bot username is None or empty! Bot info: {bot_info}")
                await update.message.reply_text(
                    "❌ የBot መረጃ ማግኘት አልተቻለም። እባክዎ እንደገና ይሞክሩ።",
                    reply_markup=get_main_keyboard()
                )
                return
            
            invite_link = f"https://t.me/{bot_username}?start=invite_{user.id}"
            
            stats = db.get_referral_stats(user.id)
            
            message = (
                f"🎁 *ጓደኞችዎን ይጋብዙ!*\n\n"
                f"📊 *የእርስዎ ሁነታ:*\n"
                f"👥 የጋበዙዋቸው ጓደኞች: *{stats['referral_count']}*\n"
                f"💰 ጠቅላላ ገቢ: *{stats['total_earnings']} ብር*\n\n"
                f"💡 *እያንዳንዱ ጓደኛ ሲቀላቀል {self.reward_amount} ብር ያገኛሉ!*\n\n"
                f"━━━━━━━━━━━━━━━━━━━\n\n"
                f"📱 *የእርስዎ የግብዣ ሊንክ:*\n"
                f"`{invite_link}`\n\n"
                f"👇 *ቀጥሎ ያለውን ቁልፍ ይጠቀሙ ለጓደኞችዎ ለመላክ!*"
            )
            
            import urllib.parse
            
            share_message_text = (
                "🎬 ET Films Story Bot\n"
                "ሁሉም ፊልም በአንድ ቦታ! 🎥\n\n"
                "━━━━━━━━━━━━━━━━━━━\n\n"
                "🎁 አሁን ተቀላቀል - 5 ብር ነፃ ያግኙ!\n"
                "✨ እስከ 2 ፊልሞች ነፃ ይመልከቱ!\n\n"
                "━━━━━━━━━━━━━━━━━━━\n\n"
                "🌍 ከየትኛው ሀገር ፊልም ብትፈልግ!\n"
                "Hollywood • Bollywood • Korean\n"
                "Ethiopian • Turkish • Egyptian\n"
                "African • European • Chinese... እና ሌሎች!\n\n"
                "🎭 ማንኛውም የፊልም ዓይነት!\n"
                "Action • Comedy • Romance\n"
                "Horror • Sci-Fi • Superhero\n"
                "Animation • Documentary... እና ሌሎች!\n\n"
                "✅ በአማርኛ ትርጉም እና ያለትርጉም በሁለቱም!\n\n"
                "━━━━━━━━━━━━━━━━━━━\n\n"
                "💰 ዋጋ:\n"
                "📽 ተከታታይ = 2 ብር | 🎬 ነጠላ = 3 ብር\n\n"
                "━━━━━━━━━━━━━━━━━━━\n\n"
                "👇 ይህን Link በመንካት አሁኑኑ ይግቡ!\n\n"
                f"{invite_link}\n\n"
                "🍿 በተለያዩ ፊልም ይደሰቱ!\n"
                "እናመሰግናለን፣ ET Films Story Bot 🎥"
            )
            
            share_url = f"https://t.me/share/url?url={urllib.parse.quote(invite_link)}&text={urllib.parse.quote(share_message_text)}"
            
            keyboard = [
                [InlineKeyboardButton("📤 ሊንክን ለጓደኞች ላክ", url=share_url)]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(
                message,
                parse_mode='Markdown',
                reply_markup=reply_markup
            )
            
            # Send main menu keyboard separately
            await update.message.reply_text(
                "🏠 ዋና ምናሌ:",
                reply_markup=get_main_keyboard()
            )
            
        except Exception as e:
            logger.error(f"Error showing referral info: {e}")
            await update.message.reply_text(
                "❌ የግብዣ መረጃ ማሳየት አልተቻለም። እባክዎ እንደገና ይሞክሩ።",
                reply_markup=get_main_keyboard()
            )

referral_system = ReferralSystem()
