import os
import time
import asyncio
import secrets
import tempfile
import shutil
import logging

from webapp.telethon_stream import iter_file_chunks

logger = logging.getLogger(__name__)

FFMPEG = "ffmpeg"

_sessions: dict[str, dict] = {}
SESSION_TTL = 3600


async def start_session(file_info: dict, file_name: str) -> str | None:
    """
    Start an FFmpeg HLS transcoding session.
    Blocks until the first 2 segments are ready, then returns session_id.
    Returns None on failure.
    """
    _cleanup_expired()

    session_id = secrets.token_urlsafe(12)
    temp_dir   = tempfile.mkdtemp(prefix=f"ethls_{session_id}_")

    playlist_path = os.path.join(temp_dir, "playlist.m3u8")
    seg_pattern   = os.path.join(temp_dir, "seg%04d.ts")

    cmd = [
        FFMPEG, "-y",
        "-i", "pipe:0",
        "-c:v", "libx264", "-preset", "ultrafast", "-crf", "28",
        "-c:a", "aac", "-ac", "2", "-ar", "44100",
        "-hls_time", "4",
        "-hls_list_size", "0",
        "-hls_flags", "independent_segments",
        "-hls_segment_type", "mpegts",
        "-hls_segment_filename", seg_pattern,
        "-f", "hls",
        playlist_path,
    ]

    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdin=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.DEVNULL,
    )

    async def _feed():
        try:
            async for chunk in iter_file_chunks(
                file_info["document"], 0, file_info["size"] - 1
            ):
                if proc.stdin.is_closing():
                    break
                proc.stdin.write(chunk)
                await proc.stdin.drain()
        except Exception as e:
            logger.debug(f"HLS feed: {e}")
        finally:
            try:
                proc.stdin.close()
            except Exception:
                pass

    feed_task = asyncio.create_task(_feed())

    _sessions[session_id] = {
        "dir":         temp_dir,
        "proc":        proc,
        "feed_task":   feed_task,
        "playlist":    playlist_path,
        "last_access": time.time(),
        "file_name":   file_name,
    }

    # Wait for at least 2 segments to be written (= 8 seconds of video ready)
    seg0 = os.path.join(temp_dir, "seg0000.ts")
    seg1 = os.path.join(temp_dir, "seg0001.ts")
    for _ in range(60):
        await asyncio.sleep(0.5)
        if os.path.exists(seg0) and os.path.exists(seg1):
            logger.info(f"HLS session {session_id} ready ({file_name})")
            return session_id

    if not os.path.exists(playlist_path):
        logger.error(f"HLS failed for {file_name}")
        _cleanup(session_id)
        return None

    logger.info(f"HLS session {session_id} ready (partial) for {file_name}")
    return session_id


def get_session(session_id: str) -> dict | None:
    sess = _sessions.get(session_id)
    if sess:
        sess["last_access"] = time.time()
    return sess


def get_file_path(session_id: str, filename: str) -> str | None:
    """Return absolute path to a file inside session dir (security-checked)."""
    sess = _sessions.get(session_id)
    if not sess:
        return None
    # Security: ensure filename has no path traversal
    safe_name = os.path.basename(filename)
    full_path  = os.path.join(sess["dir"], safe_name)
    if os.path.exists(full_path) and full_path.startswith(sess["dir"]):
        return full_path
    return None


def _cleanup(session_id: str):
    sess = _sessions.pop(session_id, None)
    if not sess:
        return
    try:
        sess["feed_task"].cancel()
    except Exception:
        pass
    try:
        sess["proc"].kill()
    except Exception:
        pass
    try:
        shutil.rmtree(sess["dir"], ignore_errors=True)
    except Exception:
        pass
    logger.info(f"HLS session {session_id} cleaned up")


def _cleanup_expired():
    now     = time.time()
    expired = [sid for sid, s in _sessions.items()
               if now - s["last_access"] > SESSION_TTL]
    for sid in expired:
        _cleanup(sid)
