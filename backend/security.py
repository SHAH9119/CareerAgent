import base64
import hashlib
import hmac
import json
import os
import re
import time
from typing import Annotated

from fastapi import Depends, Header, HTTPException, status

from storage.db import get_user_by_id

TOKEN_TTL_SECONDS = int(os.getenv("AUTH_TOKEN_TTL_SECONDS", "604800"))
EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def auth_secret() -> str:
    secret = os.getenv("AUTH_SECRET", "").strip()
    if secret:
        return secret
    # Development fallback only. Deployments must set AUTH_SECRET.
    return "careeragent-dev-secret-change-before-deploy"


def _b64_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _b64_decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode((value + padding).encode("ascii"))


def create_access_token(user: dict) -> str:
    header = {"alg": "HS256", "typ": "JWT"}
    payload = {
        "sub": str(user["id"]),
        "email": user["email"],
        "name": user.get("name", ""),
        "iat": int(time.time()),
        "exp": int(time.time()) + TOKEN_TTL_SECONDS,
    }
    signing_input = ".".join(
        [
            _b64_encode(json.dumps(header, separators=(",", ":")).encode("utf-8")),
            _b64_encode(json.dumps(payload, separators=(",", ":")).encode("utf-8")),
        ]
    )
    signature = hmac.new(auth_secret().encode("utf-8"), signing_input.encode("ascii"), hashlib.sha256).digest()
    return f"{signing_input}.{_b64_encode(signature)}"


def verify_access_token(token: str) -> dict:
    try:
        header_part, payload_part, signature_part = token.split(".", 2)
        signing_input = f"{header_part}.{payload_part}"
        expected = hmac.new(auth_secret().encode("utf-8"), signing_input.encode("ascii"), hashlib.sha256).digest()
        if not hmac.compare_digest(_b64_encode(expected), signature_part):
            raise ValueError("bad signature")
        payload = json.loads(_b64_decode(payload_part).decode("utf-8"))
        if int(payload.get("exp", 0)) < int(time.time()):
            raise ValueError("expired token")
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired session. Please log in again.",
        ) from exc

    user = get_user_by_id(int(payload.get("sub", 0)))
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User no longer exists.")
    return user


def current_user(authorization: Annotated[str | None, Header()] = None) -> dict:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Login required.")
    return verify_access_token(authorization.split(" ", 1)[1].strip())


CurrentUser = Annotated[dict, Depends(current_user)]


def validate_email(value: str) -> str:
    email = value.strip().lower()
    if not EMAIL_PATTERN.match(email):
        raise HTTPException(status_code=400, detail="Enter a valid email address.")
    return email


def validate_password(value: str) -> str:
    if len(value or "") < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters.")
    if len(value) > 128:
        raise HTTPException(status_code=400, detail="Password is too long.")
    return value
