#!/usr/bin/env python3
import asyncio
import logging
import sys
import signal
import os

# Add bot directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'bot'))

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

async def run_main_bot():
    """Run the main ET Films Story Bot"""
    try:
        logger.info("🎬 Starting ET Films Story Bot...")
        from bot import main as bot_main
        await bot_main()
    except Exception as e:
        logger.error(f"❌ ET Films Story Bot error: {e}")

async def main():
    """Main function to run the bot"""
    print("🚀 Starting ET Films Story Bot...")
    print("=" * 50)
    print("🎬 ET Films Story Bot")
    print("=" * 50)

    try:
        # Run only the main bot
        await run_main_bot()
    except KeyboardInterrupt:
        print("\n🛑 Stopping bot...")
        print("👋 Bot stopped!")
    except Exception as e:
        logger.error(f"❌ Fatal error: {e}")

def signal_handler(signum, frame):
    """Handle shutdown signals"""
    print(f"\n📡 Signal {signum} received, shutting down...")
    sys.exit(0)

if __name__ == "__main__":
    # Register signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Bot stopped by user!")
    except Exception as e:
        print(f"❌ Fatal error: {e}")
