import os
import json
import sqlite3
import logging
from pathlib import Path
from aiohttp import web

from webapp.validate import validate_init_data
from webapp.telethon_stream import get_file_info, iter_file_chunks

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).parent.parent
STATIC_DIR = Path(__file__).parent / "static"
SINGLE_DB = str(BASE_DIR / "single.db")
SERIES_DB = str(BASE_DIR / "series.db")
USER_DB = str(BASE_DIR / "user.db")


def _auth(request) -> dict | None:
    init_data = (
        request.headers.get("X-Init-Data")
        or request.query.get("initData", "")
    )
    return validate_init_data(init_data)


async def serve_app(request):
    return web.FileResponse(STATIC_DIR / "index.html")


async def serve_static(request):
    filename = request.match_info["filename"]
    filepath = STATIC_DIR / filename
    if filepath.exists() and filepath.is_file():
        return web.FileResponse(filepath)
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

    film_type = request.query.get("type", "all")
    query = request.query.get("q", "").strip()
    page = max(1, int(request.query.get("page", 1)))
    limit = 20
    offset = (page - 1) * limit

    films = []

    if film_type in ("single", "all"):
        try:
            with sqlite3.connect(SINGLE_DB) as conn:
                if query:
                    rows = conn.execute(
                        """SELECT id, file_id, message_id, file_name, file_title,
                                  channel_id, file_size
                           FROM single_movies
                           WHERE file_name LIKE ? OR file_title LIKE ?
                           LIMIT ? OFFSET ?""",
                        (f"%{query}%", f"%{query}%", limit, offset),
                    ).fetchall()
                else:
                    rows = conn.execute(
                        """SELECT id, file_id, message_id, file_name, file_title,
                                  channel_id, file_size
                           FROM single_movies ORDER BY id DESC LIMIT ? OFFSET ?""",
                        (limit, offset),
                    ).fetchall()
            for r in rows:
                title = r[4] if r[4] else r[3]
                films.append(
                    {
                        "id": f"single_{r[0]}",
                        "db_id": r[0],
                        "type": "single",
                        "name": r[3] or "",
                        "title": (title or r[3] or "")[:120],
                        "channel_id": r[5],
                        "message_id": r[2],
                        "size": r[6] or 0,
                    }
                )
        except Exception as e:
            logger.error(f"single db error: {e}")

    if film_type in ("series", "all"):
        try:
            with sqlite3.connect(SERIES_DB) as conn:
                if query:
                    rows = conn.execute(
                        """SELECT id, file_id, message_id, file_name, file_title,
                                  channel_id, file_size
                           FROM series
                           WHERE file_name LIKE ? OR file_title LIKE ?
                           LIMIT ? OFFSET ?""",
                        (f"%{query}%", f"%{query}%", limit, offset),
                    ).fetchall()
                else:
                    rows = conn.execute(
                        """SELECT id, file_id, message_id, file_name, file_title,
                                  channel_id, file_size
                           FROM series ORDER BY id DESC LIMIT ? OFFSET ?""",
                        (limit, offset),
                    ).fetchall()
            for r in rows:
                title = r[4] if r[4] else r[3]
                films.append(
                    {
                        "id": f"series_{r[0]}",
                        "db_id": r[0],
                        "type": "series",
                        "name": r[3] or "",
                        "title": (title or r[3] or "")[:120],
                        "channel_id": r[5],
                        "message_id": r[2],
                        "size": r[6] or 0,
                    }
                )
        except Exception as e:
            logger.error(f"series db error: {e}")

    return web.json_response({"films": films, "page": page})


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
            text="Streaming unavailable. Please set TELEGRAM_API_ID and TELEGRAM_API_HASH."
        )

    total_size = file_info["size"]
    mime_type = file_info["mime_type"]
    start = 0
    end = total_size - 1
    status = 200

    range_header = request.headers.get("Range", "")
    if range_header and range_header.startswith("bytes="):
        try:
            spec = range_header[6:].split("-")
            start = int(spec[0]) if spec[0] else 0
            end = int(spec[1]) if len(spec) > 1 and spec[1] else total_size - 1
            status = 206
        except Exception:
            pass

    end = min(end, total_size - 1)
    content_length = end - start + 1

    headers = {
        "Content-Type": mime_type,
        "Content-Length": str(content_length),
        "Accept-Ranges": "bytes",
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
        logger.debug(f"Stream interrupted: {e}")

    return response


def setup_webapp_routes(app: web.Application):
    app.router.add_get("/webapp", serve_app)
    app.router.add_get("/webapp/", serve_app)
    app.router.add_get("/webapp/static/{filename}", serve_static)
    app.router.add_get("/api/me", get_me)
    app.router.add_get("/api/films", get_films)
    app.router.add_get("/stream/{film_id}", stream_film)
