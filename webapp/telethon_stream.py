import os
import logging
import asyncio

logger = logging.getLogger(__name__)

API_ID = os.getenv("TELEGRAM_API_ID") or os.getenv("API_ID", "0")
API_HASH = os.getenv("TELEGRAM_API_HASH") or os.getenv("API_HASH", "")
BOT_TOKEN = os.getenv("BOT_TOKEN", "")

try:
    _API_ID_INT = int(API_ID)
except (ValueError, TypeError):
    _API_ID_INT = 0

CHUNK_SIZE = 512 * 1024  # 512 KB per request

_client = None
_client_lock = asyncio.Lock()


async def start_client():
    global _client
    if not _API_ID_INT or not API_HASH or not BOT_TOKEN:
        logger.warning("⚠️  Telethon credentials not set or invalid — streaming disabled")
        return

    try:
        from telethon import TelegramClient
        async with _client_lock:
            if _client and _client.is_connected():
                return
            _client = TelegramClient(
                "bot_stream",
                _API_ID_INT,
                API_HASH,
                connection_retries=3,
                retry_delay=2,
            )
            await _client.start(bot_token=BOT_TOKEN)
            logger.info("✅ Telethon streaming client connected")
    except Exception as e:
        logger.error(f"❌ Telethon connection failed: {e}")
        _client = None


async def get_client():
    global _client
    if _client and _client.is_connected():
        return _client
    await start_client()
    return _client


async def get_file_info(channel_id: int, message_id: int) -> dict | None:
    client = await get_client()
    if not client:
        return None
    try:
        message = await client.get_messages(channel_id, ids=message_id)
        if not message or not message.document:
            return None
        mime = message.document.mime_type or "video/mp4"
        return {
            "size": message.document.size,
            "mime_type": mime,
            "document": message.document,
        }
    except Exception as e:
        logger.error(f"get_file_info error: {e}")
        return None


async def iter_file_chunks(document, start: int, end: int):
    client = await get_client()
    if not client:
        return

    aligned_offset = (start // CHUNK_SIZE) * CHUNK_SIZE
    skip = start - aligned_offset
    remaining = end - start + 1

    try:
        async for chunk in client.iter_download(
            document,
            offset=aligned_offset,
            request_size=CHUNK_SIZE,
        ):
            if skip > 0:
                if len(chunk) <= skip:
                    skip -= len(chunk)
                    continue
                chunk = chunk[skip:]
                skip = 0

            if len(chunk) >= remaining:
                yield bytes(chunk[:remaining])
                return

            yield bytes(chunk)
            remaining -= len(chunk)

            if remaining <= 0:
                return
    except Exception as e:
        logger.error(f"Stream chunk error: {e}")
