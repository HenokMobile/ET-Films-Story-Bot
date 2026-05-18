import os
import re
import json
import sqlite3
import logging
import asyncio
from pathlib import Path
from urllib.parse import quote
import aiohttp
from aiohttp import web

from webapp.validate import validate_init_data, validate_auth, create_web_token
from webapp.telethon_stream import get_file_info, iter_file_chunks

FFMPEG = "ffmpeg"
_NATIVE_TYPES = {"video/mp4", "video/webm", "video/ogg"}
_NATIVE_EXTS  = {".mp4", ".webm", ".m4v", ".ogv"}

TMDB_IMAGE_BASE = "https://image.tmdb.org/t/p/w500"
_TMDB_SEARCH    = "https://api.themoviedb.org/3/search/{kind}?api_key={key}&query={q}&language=en-US&page=1"

# In-memory cache: key "ftype:name" → (poster_url, popularity)
# Survives for the lifetime of the process (cleared on restart)
_tmdb_cache: dict = {}
_TMDB_SEM   = None   # asyncio.Semaphore created lazily (needs running loop)
_EXT_RE      = re.compile(r'\.(mkv|mp4|avi|mov|wmv|flv|webm|m4v|ts|m2ts)$', re.I)
_AMHARIC_RE  = re.compile(r'[\u1200-\u137F\u1380-\u139F\u2D80-\u2DDF\uAB01-\uAB2F]+')
_CHANNEL_RE  = re.compile(r'@\w+')
_QUALITY_RE  = re.compile(r'\b(1080p|720p|480p|4k|hdr|bluray|webrip|hdtv|x264|x265|hevc|aac|ac3|phonofilm)\b|HD\+?', re.I)
_YEAR_RE     = re.compile(r'[\[\(]?\b(19|20)\d{2}\b[\]\)]?')
_EP_RE       = re.compile(r'\s+[-]?\d+\s*[A-Za-z]?\s*$')  # handles "24 -2A", "24 1A"
_PAREN_RE    = re.compile(r'[\(\[].*?[\)\]]')
_UNDER_RE    = re.compile(r'[_]+')
_LEAD_NUM_RE = re.compile(r'^0\d\.')   # strip ONLY leading-zero indices: "01." "02." … "09." (not "12.", "13.")
_DOT_SEP_RE  = re.compile(r'(?<=[a-zA-Z0-9])\.(?=[a-zA-Z])')  # dot-as-separator
_UUID_RE     = re.compile(r'^[0-9a-f\-]{20,}$', re.I)
_URL_ENC_RE  = re.compile(r'^%[0-9A-Fa-f]{2}')
# Remove emojis and misc symbols: ★ ✔️ ☆ ✓ etc.
# NOTE: emoji above U+FFFF need \U (8-digit) not \u (4-digit)
_SYMBOL_RE   = re.compile('[\u2600-\u27BF\u2B00-\u2BFF\U0001F000-\U0001FFFF\uFE00-\uFE0F\u200D\uFFFD]+')
# "1A CRISIS" → "CRISIS"  (leading episode marker: digit+letter+space)
_LEAD_EP_RE   = re.compile(r'^\d+[A-Za-z]\s+')
# "KGF1" → "KGF 1"  (letter stuck to trailing digit with no space)
_STUCK_NUM_RE = re.compile(r'([a-zA-Z])(\d+)$')


def _is_amharic_only(text: str) -> bool:
    """Returns True if the text contains only Amharic characters (no Latin letters or digits)."""
    latin = re.sub(r'[\u1200-\u137F\u1380-\u139F\u2D80-\u2DDF\uAB01-\uAB2F\s]', '', text)
    return len(latin.strip()) == 0


def _clean_title(name: str, strip_episode: bool = False) -> str:
    t = _EXT_RE.sub('', name or '').strip()
    # Skip garbage: UUIDs, URL-encoded strings, hashtag-only names
    if _UUID_RE.match(t) or _URL_ENC_RE.match(t) or t.startswith('#'):
        return ''
    # If title is purely Amharic with no Latin chars, skip TMDB search
    if _is_amharic_only(t):
        return ''
    t = _CHANNEL_RE.sub('', t)        # remove @channel BEFORE underscore expansion
    t = _UNDER_RE.sub(' ', t)         # underscores → spaces
    t = _AMHARIC_RE.sub('', t)        # remove Amharic text (keep Latin parts)
    t = _SYMBOL_RE.sub('', t)         # remove ★ ✔️ emojis and misc symbols
    t = _QUALITY_RE.sub('', t)
    t = _PAREN_RE.sub('', t)
    t = _YEAR_RE.sub('', t)
    t = _LEAD_NUM_RE.sub('', t)       # "01.Home" → "Home" (before dot expansion)
    t = _DOT_SEP_RE.sub(' ', t)       # "Home.alone" → "Home alone"
    t = _STUCK_NUM_RE.sub(r'\1 \2', t)   # "Again13" → "Again 13" FIRST (so EP_RE can strip)
    t = _LEAD_EP_RE.sub('', t)        # "1A CRISIS" → "CRISIS" (leading ep marker)
    if strip_episode:
        t = _EP_RE.sub('', t)         # "18 Again 13" → "18 Again"
    t = re.sub(r'\s+', ' ', t).strip(' .-_')
    return t


async def _fetch_tmdb_data(session: aiohttp.ClientSession, title: str, ftype: str) -> tuple:
    """Return (poster_url, popularity). Uses in-memory cache + semaphore rate-limiter."""
    global _TMDB_SEM
    if _TMDB_SEM is None:
        _TMDB_SEM = asyncio.Semaphore(15)   # max 15 concurrent TMDB requests

    cache_key = f"{ftype}:{title}"
    if cache_key in _tmdb_cache:
        return _tmdb_cache[cache_key]

    key = os.getenv("TMDB_API_KEY", "")
    if not key or not title:
        return ("", 0.0)

    clean = _clean_title(title, strip_episode=(ftype == "series"))
    if not clean:
        _tmdb_cache[cache_key] = ("", 0.0)
        return ("", 0.0)

    kind = "tv" if ftype == "series" else "movie"
    url  = _TMDB_SEARCH.format(kind=kind, key=key, q=quote(clean))

    result = ("", 0.0)
    try:
        async with _TMDB_SEM:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=8)) as resp:
                if resp.status != 200:
                    logger.warning(f"TMDB {resp.status} for '{clean}'")
                else:
                    data = await resp.json()
                    results = data.get("results", [])
                    query_words = clean.lower().split()
                    single_word = len(query_words) == 1
                    for hit in results:
                        if hit.get("poster_path"):
                            result_title = (hit.get("title") or hit.get("name") or "").strip()
                            result_lower = result_title.lower()
                            if single_word and result_lower != query_words[0]:
                                logger.info(f"TMDB skipped (single-word mismatch): '{clean}' ≠ '{result_title}'")
                                continue
                            poster     = TMDB_IMAGE_BASE + hit["poster_path"]
                            popularity = float(hit.get("popularity", 0))
                            result     = (poster, popularity)
                            logger.info(f"TMDB found: '{clean}' → '{result_title}' pop={popularity:.1f}")
                            break
    except Exception as e:
        logger.warning(f"TMDB fetch error for '{clean}': {e}")

    _tmdb_cache[cache_key] = result
    return result


# Keep thin wrapper for backward compat (detail endpoint still uses session directly)
async def _fetch_tmdb_poster(session: aiohttp.ClientSession, title: str, ftype: str) -> str:
    poster, _ = await _fetch_tmdb_data(session, title, ftype)
    return poster


def _natural_sort_key(film: dict) -> list:
    return [int(c) if c.isdigit() else c.lower()
            for c in re.split(r'(\d+)', film.get("name") or "")]


def _needs_transcode(mime: str, fname: str) -> bool:
    if mime in _NATIVE_TYPES:
        return False
    ext = os.path.splitext(fname or "")[-1].lower()
    return ext not in _NATIVE_EXTS

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).parent.parent
STATIC_DIR = Path(__file__).parent / "static"
SINGLE_DB = str(BASE_DIR / "single.db")
SERIES_DB = str(BASE_DIR / "series.db")
USER_DB = str(BASE_DIR / "user.db")


import random
import time as _time

_otp_store: dict = {}

def _auth(request) -> dict | None:
    return validate_auth(request)


async def serve_app(request):
    return web.FileResponse(STATIC_DIR / "index.html",
                            headers={"Cache-Control": "no-cache, no-store, must-revalidate"})


async def serve_static(request):
    filename = request.match_info["filename"]
    filepath = STATIC_DIR / filename
    if filepath.exists() and filepath.is_file():
        return web.FileResponse(filepath,
                                headers={"Cache-Control": "no-cache, no-store, must-revalidate"})
    raise web.HTTPNotFound()


async def get_me(request):
    user = _auth(request)
    if not user:
        raise web.HTTPUnauthorized()

    user_id = user.get("id")
    row = None
    try:
        with sqlite3.connect(USER_DB) as conn:
            row = conn.execute(
                """SELECT username, phone_number, first_name, last_name,
                          balance, referral_count, total_referral_earnings, joined_date
                   FROM users WHERE user_id = ?""",
                (user_id,),
            ).fetchone()
    except Exception as e:
        logger.error(f"get_me db error: {e}")

    result = {
        "id": user_id,
        "first_name": user.get("first_name", ""),
        "last_name": user.get("last_name", ""),
        "username": user.get("username", ""),
        "language_code": user.get("language_code", "am"),
        "is_registered": row is not None,
    }

    if row:
        result.update(
            {
                "phone_number": row[1] or "",
                "balance": row[4] or 0,
                "referral_count": row[5] or 0,
                "total_referral_earnings": row[6] or 0,
                "joined_date": row[7] or "",
            }
        )

    return web.json_response(result)


async def get_films(request):
    user = _auth(request)
    if not user:
        raise web.HTTPUnauthorized()

    query = request.query.get("q", "").strip()
    page  = max(1, int(request.query.get("page", 1)))
    limit = 21
    cap   = 5000

    all_films = []

    db_configs = [
        (SINGLE_DB, "single_movies", "single"),
        (SERIES_DB, "series",        "series"),
    ]

    for db_path, table, ftype in db_configs:
        try:
            with sqlite3.connect(db_path) as conn:
                if query:
                    rows = conn.execute(
                        f"""SELECT id, file_id, message_id, file_name, file_title,
                                   channel_id, file_size
                            FROM {table}
                            WHERE file_name LIKE ? OR file_title LIKE ?
                            LIMIT ?""",
                        (f"%{query}%", f"%{query}%", cap),
                    ).fetchall()
                else:
                    rows = conn.execute(
                        f"""SELECT id, file_id, message_id, file_name, file_title,
                                   channel_id, file_size
                            FROM {table}
                            LIMIT ?""",
                        (cap,),
                    ).fetchall()
            for r in rows:
                all_films.append({
                    "id":         f"{ftype}_{r[0]}",
                    "db_id":      r[0],
                    "type":       ftype,
                    "name":       r[3] or "",
                    "title":      (r[4] or r[3] or "")[:120],
                    "channel_id": r[5],
                    "message_id": r[2],
                    "size":       r[6] or 0,
                })
        except Exception as e:
            logger.error(f"{ftype} db error: {e}")

    tmdb_key = os.getenv("TMDB_API_KEY", "")

    if tmdb_key and all_films:
        # ── Fetch TMDB data for ALL films before sorting ─────────────────
        async with aiohttp.ClientSession() as session:
            tmdb_results = await asyncio.gather(*[
                _fetch_tmdb_data(session, f.get("name", ""), f["type"])
                for f in all_films
            ])

        for film, (poster, popularity) in zip(all_films, tmdb_results):
            film["poster_url"]  = poster
            film["_popularity"] = popularity

        if query:
            # Search: sort by popularity then name
            matched   = [f for f in all_films if f["_popularity"] > 0]
            unmatched = [f for f in all_films if f["_popularity"] == 0]
            matched.sort(key=lambda f: f["_popularity"], reverse=True)
            unmatched.sort(key=_natural_sort_key)
            all_films = matched + unmatched
        else:
            # Home: shuffle daily so different films appear each day
            import random as _rnd
            day_seed = int(__import__("datetime").date.today().strftime("%Y%j"))
            _rnd.seed(day_seed)
            _rnd.shuffle(all_films)

        found = sum(1 for f in all_films if f.get("poster_url"))
        logger.info(f"TMDB posters: {found}/{len(all_films)}")
    else:
        if query:
            all_films.sort(key=_natural_sort_key)
        else:
            import random as _rnd
            day_seed = int(__import__("datetime").date.today().strftime("%Y%j"))
            _rnd.seed(day_seed)
            _rnd.shuffle(all_films)
        for film in all_films:
            film["poster_url"]  = ""
            film["_popularity"] = 0

    # Paginate after ordering
    offset = (page - 1) * limit
    films  = all_films[offset: offset + limit]

    # Strip internal field before sending
    for f in films:
        f.pop("_popularity", None)

    return web.json_response({"films": films, "page": page})


async def _stream_direct(request, file_info, file_name):
    """MP4/WebM: serve with byte-range support (seeking works)."""
    total_size = file_info["size"]
    mime_type  = file_info["mime_type"]
    start, end, status = 0, total_size - 1, 200

    range_header = request.headers.get("Range", "")
    if range_header and range_header.startswith("bytes="):
        try:
            spec  = range_header[6:].split("-")
            start = int(spec[0]) if spec[0] else 0
            end   = int(spec[1]) if len(spec) > 1 and spec[1] else total_size - 1
            status = 206
        except Exception:
            pass

    end = min(end, total_size - 1)
    headers = {
        "Content-Type":        mime_type,
        "Content-Length":      str(end - start + 1),
        "Accept-Ranges":       "bytes",
        "Content-Disposition": f'inline; filename="{file_name}"',
    }
    if status == 206:
        headers["Content-Range"] = f"bytes {start}-{end}/{total_size}"

    response = web.StreamResponse(status=status, headers=headers)
    await response.prepare(request)
    try:
        async for chunk in iter_file_chunks(file_info["document"], start, end):
            await response.write(chunk)
    except (ConnectionResetError, ConnectionAbortedError):
        pass
    except Exception as e:
        logger.debug(f"Direct stream interrupted: {e}")
    return response


def _make_ffmpeg_cmd(copy_video: bool) -> list:
    """Build FFmpeg command for pipe-based transcoding to fragmented MP4."""
    video_args = (
        ["-c:v", "copy"]
        if copy_video
        else ["-c:v", "libx264", "-preset", "superfast", "-crf", "28"]
    )
    return [
        FFMPEG, "-y",
        "-i", "pipe:0",
        *video_args,
        "-c:a", "aac", "-ac", "2", "-ar", "44100",
        "-movflags", "frag_keyframe+empty_moov+default_base_moof",
        "-f", "mp4",
        "pipe:1",
    ]


async def _run_ffmpeg(file_info, cmd):
    """Start FFmpeg, feed input from Telethon, return (proc, feed_task, first_chunk).
    Returns (None, None, None) if FFmpeg produced no output within timeout."""
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.DEVNULL,
    )

    async def feed():
        try:
            async for chunk in iter_file_chunks(
                file_info["document"], 0, file_info["size"] - 1
            ):
                if proc.stdin.is_closing():
                    break
                proc.stdin.write(chunk)
                await proc.stdin.drain()
        except Exception as fe:
            logger.debug(f"FFmpeg feed: {fe}")
        finally:
            try:
                proc.stdin.close()
            except Exception:
                pass

    feed_task = asyncio.create_task(feed())

    try:
        first_chunk = await asyncio.wait_for(proc.stdout.read(131072), timeout=25)
        if not first_chunk:
            raise ValueError("empty output")
        return proc, feed_task, first_chunk
    except Exception:
        feed_task.cancel()
        try:
            proc.kill()
        except Exception:
            pass
        return None, None, None


async def _stream_transcode(request, file_info, file_name):
    """AVI/MKV/etc.: pipe through FFmpeg → fragmented MP4 (no seeking)."""
    response = web.StreamResponse(
        status=200,
        headers={
            "Content-Type":        "video/mp4",
            "Cache-Control":       "no-cache, no-store",
            "Content-Disposition": f'inline; filename="{os.path.splitext(file_name)[0]}.mp4"',
            "X-Transcode":         "1",
        },
    )
    await response.prepare(request)

    # Try fast path: remux only (works when video is already H.264)
    proc, feed_task, first_chunk = await _run_ffmpeg(file_info, _make_ffmpeg_cmd(copy_video=True))

    # Fallback: full libx264 encode (handles XviD / DivX / MPEG-4 ASP)
    if proc is None:
        logger.info(f"FFmpeg copy failed for '{file_name}', retrying with libx264 encode")
        proc, feed_task, first_chunk = await _run_ffmpeg(file_info, _make_ffmpeg_cmd(copy_video=False))

    if proc is None:
        logger.error(f"FFmpeg failed entirely for '{file_name}'")
        return response

    # Write the first chunk that was used for detection
    try:
        await response.write(first_chunk)
        # Stream the rest
        while True:
            chunk = await proc.stdout.read(65536)
            if not chunk:
                break
            await response.write(chunk)
    except (ConnectionResetError, ConnectionAbortedError):
        pass
    except Exception as e:
        logger.debug(f"Transcode stream write: {e}")
    finally:
        feed_task.cancel()
        try:
            proc.kill()
        except Exception:
            pass

    return response


async def stream_film(request):
    user = _auth(request)
    if not user:
        raise web.HTTPUnauthorized()

    film_id = request.match_info["film_id"]
    parts = film_id.split("_", 1)
    if len(parts) != 2:
        raise web.HTTPBadRequest()

    film_type, db_id_str = parts
    try:
        db_id = int(db_id_str)
    except ValueError:
        raise web.HTTPBadRequest()

    if film_type == "single":
        db_path, table = SINGLE_DB, "single_movies"
    elif film_type == "series":
        db_path, table = SERIES_DB, "series"
    else:
        raise web.HTTPBadRequest()

    try:
        with sqlite3.connect(db_path) as conn:
            row = conn.execute(
                f"SELECT channel_id, message_id, file_name FROM {table} WHERE id = ?",
                (db_id,),
            ).fetchone()
    except Exception as e:
        logger.error(f"stream db error: {e}")
        raise web.HTTPInternalServerError()

    if not row:
        raise web.HTTPNotFound()

    channel_id, message_id, file_name = row
    file_info = await get_file_info(channel_id, message_id)
    if not file_info:
        raise web.HTTPServiceUnavailable(
            text="Streaming unavailable. Please set API_ID and API_HASH."
        )

    mime_type = file_info["mime_type"]
    if _needs_transcode(mime_type, file_name):
        logger.info(f"Transcoding {file_name} (mime={mime_type})")
        return await _stream_transcode(request, file_info, file_name)
    else:
        return await _stream_direct(request, file_info, file_name)


async def stream_start(request):
    """GET /api/stream/start/{film_id}
    Returns {type:'direct'|'hls', url, session_id?}.
    Blocks until HLS segments are ready (for non-MP4).
    """
    user = _auth(request)
    if not user:
        raise web.HTTPUnauthorized()

    film_id = request.match_info["film_id"]
    parts   = film_id.split("_", 1)
    if len(parts) != 2:
        raise web.HTTPBadRequest()

    film_type, db_id_str = parts
    try:
        db_id = int(db_id_str)
    except ValueError:
        raise web.HTTPBadRequest()

    if film_type == "single":
        db_path, table = SINGLE_DB, "single_movies"
    elif film_type == "series":
        db_path, table = SERIES_DB, "series"
    else:
        raise web.HTTPBadRequest()

    try:
        with sqlite3.connect(db_path) as conn:
            row = conn.execute(
                f"SELECT channel_id, message_id, file_name FROM {table} WHERE id = ?",
                (db_id,),
            ).fetchone()
    except Exception as e:
        logger.error(f"stream_start db error: {e}")
        raise web.HTTPInternalServerError()

    if not row:
        raise web.HTTPNotFound()

    channel_id, message_id, file_name = row
    file_info = await get_file_info(channel_id, message_id)
    if not file_info:
        raise web.HTTPServiceUnavailable(text="Telethon unavailable")

    mime_type = file_info["mime_type"]

    if not _needs_transcode(mime_type, file_name):
        init_data = (
            request.headers.get("X-Init-Data")
            or request.query.get("initData", "")
        )
        direct_url = f"/stream/{film_id}?initData={quote(init_data, safe='')}"
        return web.json_response({"type": "direct", "url": direct_url})

    from webapp import hls_manager
    session_id = await hls_manager.start_session(file_info, file_name)
    if not session_id:
        raise web.HTTPInternalServerError(text="HLS session failed")

    return web.json_response({
        "type":       "hls",
        "session_id": session_id,
        "url":        f"/hls/{session_id}/playlist.m3u8",
    })


async def serve_hls_playlist(request):
    """GET /hls/{session_id}/playlist.m3u8"""
    session_id = request.match_info["session_id"]
    from webapp import hls_manager
    path = hls_manager.get_file_path(session_id, "playlist.m3u8")
    if not path:
        raise web.HTTPNotFound()
    return web.FileResponse(
        path,
        headers={"Content-Type": "application/vnd.apple.mpegurl",
                 "Cache-Control": "no-cache"}
    )


async def serve_hls_segment(request):
    """GET /hls/{session_id}/{segment}"""
    session_id = request.match_info["session_id"]
    seg        = request.match_info["segment"]
    from webapp import hls_manager
    path = hls_manager.get_file_path(session_id, seg)
    if not path:
        # Segment not yet written — wait up to 8 s
        from webapp import hls_manager as hm
        for _ in range(16):
            await asyncio.sleep(0.5)
            path = hm.get_file_path(session_id, seg)
            if path:
                break
    if not path:
        raise web.HTTPNotFound()
    return web.FileResponse(
        path,
        headers={"Content-Type": "video/mp2t",
                 "Cache-Control": "no-cache"}
    )


async def tmdb_detail(request):
    """Return full TMDB detail for a film: overview, rating, year, genres, cast, images."""
    title = request.rel_url.query.get("title", "").strip()
    ftype = request.rel_url.query.get("type", "movie")
    key   = os.getenv("TMDB_API_KEY", "")
    if not key or not title:
        return web.json_response({})

    clean = _clean_title(title, strip_episode=(ftype == "series"))
    if not clean:
        return web.json_response({})

    kind = "tv" if ftype == "series" else "movie"
    search_url = f"https://api.themoviedb.org/3/search/{kind}?api_key={key}&query={quote(clean)}&language=en-US&page=1"

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(search_url, timeout=aiohttp.ClientTimeout(total=8)) as resp:
                if resp.status != 200:
                    return web.json_response({})
                data    = await resp.json()
                results = data.get("results", [])
                if not results:
                    return web.json_response({})
                # Single-word guard: prevent "CRISIS" → "Classroom Crisis" mismatches
                query_words = clean.lower().split()
                if len(query_words) == 1:
                    matched = next(
                        (r for r in results
                         if (r.get("title") or r.get("name") or "").lower().strip() == query_words[0]),
                        None
                    )
                    if not matched:
                        return web.json_response({})
                    hit = matched
                else:
                    hit = results[0]
                tmdb_id = hit.get("id")

            detail_url = (
                f"https://api.themoviedb.org/3/{kind}/{tmdb_id}"
                f"?api_key={key}&language=en-US&append_to_response=images,credits"
                f"&include_image_language=en,null"
            )
            async with session.get(detail_url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status != 200:
                    return web.json_response({})
                detail = await resp.json()

        IMG_BASE_W  = "https://image.tmdb.org/t/p/w780"
        IMG_BASE_OR = "https://image.tmdb.org/t/p/original"

        images    = detail.get("images", {})
        backdrops = [IMG_BASE_W + b["file_path"] for b in images.get("backdrops", [])[:6] if b.get("file_path")]
        posters   = [IMG_BASE_OR + p["file_path"] for p in images.get("posters", [])[:4] if p.get("file_path")]

        # Merge: backdrops first then portrait posters
        all_images = backdrops + posters
        if not all_images and detail.get("poster_path"):
            all_images = [IMG_BASE_OR + detail["poster_path"]]

        genres    = [g["name"] for g in detail.get("genres", [])]
        credits   = detail.get("credits", {})
        cast      = [c["name"] for c in credits.get("cast", [])[:6]]
        directors = [c["name"] for c in credits.get("crew", []) if c.get("job") == "Director"][:2]

        runtime   = detail.get("runtime") or (detail.get("episode_run_time") or [None])[0]
        rating    = detail.get("vote_average")
        year      = (detail.get("release_date") or detail.get("first_air_date") or "")[:4]
        overview  = detail.get("overview") or ""

        # Country of origin
        prod_countries = detail.get("production_countries", [])
        orig_countries = detail.get("origin_country", [])
        countries = [c.get("name", "") for c in prod_countries if c.get("name")]
        if not countries and orig_countries:
            countries = orig_countries[:2]
        country = ", ".join(countries[:2]) if countries else ""

        # Content kind (movie vs series) for UI display
        content_kind = "TV Series" if kind == "tv" else "Movie"

        return web.json_response({
            "tmdb_title":    detail.get("title") or detail.get("name") or clean,
            "overview":      overview,
            "rating":        round(rating, 1) if rating else None,
            "year":          year,
            "runtime":       runtime,
            "genres":        genres,
            "cast":          cast,
            "directors":     directors,
            "images":        all_images,
            "poster":        (IMG_BASE_OR + detail["poster_path"]) if detail.get("poster_path") else "",
            "country":       country,
            "content_kind":  content_kind,
        })
    except Exception as e:
        logger.warning(f"tmdb_detail error: {e}")
        return web.json_response({})


async def request_otp(request):
    try:
        body = await request.json()
    except Exception:
        raise web.HTTPBadRequest(text="Invalid JSON")

    phone = (body.get("phone") or "").strip().replace(" ", "").replace("-", "")
    if not phone:
        return web.json_response({"error": "ስልክ ቁጥር ያስፈልጋል"}, status=400)

    phone_variants = [phone]
    if phone.startswith("0"):
        phone_variants.append("+251" + phone[1:])
        phone_variants.append("251" + phone[1:])
    elif phone.startswith("+251"):
        phone_variants.append("0" + phone[4:])
    elif phone.startswith("251"):
        phone_variants.append("0" + phone[3:])
        phone_variants.append("+" + phone)

    user_id = None
    try:
        with sqlite3.connect(USER_DB) as conn:
            placeholders = ",".join("?" * len(phone_variants))
            row = conn.execute(
                f"SELECT user_id FROM users WHERE phone_number IN ({placeholders}) LIMIT 1",
                phone_variants,
            ).fetchone()
            if row:
                user_id = row[0]
    except Exception as e:
        logger.error(f"OTP lookup error: {e}")

    if not user_id:
        return web.json_response({"error": "ይህ ስልክ ቁጥር Bot ላይ አልተመዘገበም"}, status=404)

    otp = str(random.randint(100000, 999999))
    _otp_store[phone] = {"otp": otp, "user_id": user_id, "expires": _time.time() + 300}

    try:
        from webapp.shared import get_bot_app
        bot_app = get_bot_app()
        if bot_app:
            await bot_app.bot.send_message(
                chat_id=user_id,
                text=(
                    "🔐 *ET Films — Web Login*\n\n"
                    f"የእርስዎ ኮድ: `{otp}`\n\n"
                    "⏱ ይህ ኮድ *5 ደቂቃ* ብቻ ይሰራል።\n"
                    "ኮዱን ከሌሎች አይጋሩ!"
                ),
                parse_mode="Markdown",
            )
        else:
            logger.error("Bot app not ready for OTP sending")
            return web.json_response({"error": "Bot አልተዘጋጀም። ቆይተው ይሞክሩ"}, status=503)
    except Exception as e:
        logger.error(f"OTP send error: {e}")
        return web.json_response({"error": "ኮዱን መላክ አልተቻለም"}, status=500)

    return web.json_response({"ok": True, "message": "ኮዱ ወደ Telegram ተልኳል"})


async def verify_otp(request):
    try:
        body = await request.json()
    except Exception:
        raise web.HTTPBadRequest(text="Invalid JSON")

    phone = (body.get("phone") or "").strip().replace(" ", "").replace("-", "")
    otp = str(body.get("otp") or "").strip()

    if not phone or not otp:
        return web.json_response({"error": "ስልክ ቁጥር እና ኮድ ያስፈልጋሉ"}, status=400)

    record = _otp_store.get(phone)
    if not record:
        return web.json_response({"error": "ኮድ አልተላከም። እንደገና ይሞክሩ"}, status=400)

    if _time.time() > record["expires"]:
        _otp_store.pop(phone, None)
        return web.json_response({"error": "ኮዱ ጊዜው አልፏል። እንደገና ይላኩ"}, status=400)

    if record["otp"] != otp:
        return web.json_response({"error": "ኮዱ ትክክል አይደለም"}, status=400)

    _otp_store.pop(phone, None)
    token = create_web_token(int(record["user_id"]))
    return web.json_response({"ok": True, "token": token})


def setup_webapp_routes(app: web.Application):
    app.router.add_get("/webapp", serve_app)
    app.router.add_get("/webapp/", serve_app)
    app.router.add_get("/webapp/static/{filename}", serve_static)
    app.router.add_get("/api/me", get_me)
    app.router.add_get("/api/films", get_films)
    app.router.add_get("/api/tmdb_detail", tmdb_detail)
    app.router.add_get("/api/stream/start/{film_id}", stream_start)
    app.router.add_get("/stream/{film_id}", stream_film)
    app.router.add_get("/hls/{session_id}/playlist.m3u8", serve_hls_playlist)
    app.router.add_get("/hls/{session_id}/{segment}", serve_hls_segment)
    app.router.add_post("/api/auth/request-otp", request_otp)
    app.router.add_post("/api/auth/verify-otp", verify_otp)
