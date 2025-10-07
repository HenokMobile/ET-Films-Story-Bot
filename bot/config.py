
# Bot Configuration
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")

# Admin settings
ADMIN_USER_ID = 6918848131  # Replace with your user ID

# Channel IDs (to be set via admin panel)
SINGLE_MOVIE_CHANNEL_IDS = [-1003169574565]
SERIES_CHANNEL_IDS = [-1002955565679]

# Database paths
SINGLE_DB_PATH = "single.db"
SERIES_DB_PATH = "series.db"
USER_DB_PATH = "user.db"

# Welcome Bonus Configuration
WELCOME_BONUS = 5  # Birr given to new users

# AI Configuration - Disabled
GEMINI_API_KEY = None  # AI search disabled
