#!/usr/bin/env python3
import asyncio
import logging
import sys
import signal
import os
from aiohttp import web

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "bot"))

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


async def health_check(request):
    return web.Response(text="ET Films Bot is running! 🎬", status=200)


async def run_health_server():
    app = web.Application()
    app.router.add_get("/", health_check)
    app.router.add_get("/health", health_check)

    from webapp.api import setup_webapp_routes
    setup_webapp_routes(app)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", 8080)
    await site.start()
    logger.info("✅ Server running on port 8080 (health + mini-app)")


async def run_telethon():
    try:
        from webapp.telethon_stream import start_client
        await start_client()
    except Exception as e:
        logger.warning(f"Telethon start skipped: {e}")


async def run_main_bot():
    try:
        logger.info("🎬 Starting ET Films Story Bot...")
        from bot import main as bot_main
        await bot_main()
    except Exception as e:
        logger.error(f"❌ ET Films Story Bot error: {e}")


async def main():
    print("🚀 Starting ET Films Story Bot...")
    print("=" * 50)
    print("🎬 ET Films Story Bot")
    print("=" * 50)

    try:
        await asyncio.gather(
            run_health_server(),
            run_telethon(),
            run_main_bot(),
        )
    except KeyboardInterrupt:
        print("\n🛑 Stopping bot...")
    except Exception as e:
        logger.error(f"❌ Fatal error: {e}")


def signal_handler(signum, frame):
    print(f"\n📡 Signal {signum} received, shutting down...")
    sys.exit(0)


if __name__ == "__main__":
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Bot stopped by user!")
    except Exception as e:
        print(f"❌ Fatal error: {e}")
