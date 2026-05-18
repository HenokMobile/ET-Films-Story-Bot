import hashlib
import hmac
import urllib.parse
import json
import os
import time

import jwt

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
JWT_SECRET = os.getenv("JWT_SECRET", "et-films-secret-key")
JWT_EXPIRE_HOURS = 24 * 30


def validate_init_data(init_data: str) -> dict | None:
    if not init_data:
        return None
    try:
        parsed = dict(urllib.parse.parse_qsl(init_data, keep_blank_values=True))
        hash_value = parsed.pop("hash", None)
        if not hash_value:
            return None

        data_check_string = "\n".join(
            f"{k}={v}" for k, v in sorted(parsed.items())
        )

        secret_key = hmac.new(
            b"WebAppData", BOT_TOKEN.encode("utf-8"), hashlib.sha256
        ).digest()
        computed_hash = hmac.new(
            secret_key, data_check_string.encode("utf-8"), hashlib.sha256
        ).hexdigest()

        if not hmac.compare_digest(computed_hash, hash_value):
            return None

        user_data = json.loads(parsed.get("user", "{}"))
        return user_data
    except Exception:
        return None


def create_web_token(user_id: int) -> str:
    payload = {
        "user_id": user_id,
        "exp": time.time() + JWT_EXPIRE_HOURS * 3600,
        "iat": time.time(),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm="HS256")


def validate_web_token(token: str) -> dict | None:
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
        return {"id": int(payload["user_id"])}
    except Exception:
        return None


def validate_auth(request) -> dict | None:
    init_data = (
        request.headers.get("X-Init-Data")
        or request.query.get("initData", "")
    )
    if init_data:
        result = validate_init_data(init_data)
        if result:
            return result

    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header[7:]
        return validate_web_token(token)

    web_token = request.query.get("webToken", "")
    if web_token:
        return validate_web_token(web_token)

    return None
