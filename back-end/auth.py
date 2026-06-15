"""Authentication primitives — password hashing, JWT, and the @require_auth guard.

Passwords are always hashed with werkzeug; plaintext is never stored, logged, or
returned. Sessions are stateless JWTs sent as `Authorization: Bearer <token>`.
"""

from __future__ import annotations

import datetime as dt
from functools import wraps

import jwt
from flask import current_app, g, jsonify, request
from werkzeug.security import check_password_hash, generate_password_hash

TOKEN_TTL = dt.timedelta(days=30)
_ALGO = "HS256"


# --- passwords ---------------------------------------------------------------


def hash_password(password: str) -> str:
    # pbkdf2:sha256 is available on every OpenSSL build (werkzeug's scrypt
    # default is not), so hashing is portable across interpreters/containers.
    return generate_password_hash(password, method="pbkdf2:sha256")


def verify_password(password_hash: str, password: str) -> bool:
    return check_password_hash(password_hash, password)


# --- tokens ------------------------------------------------------------------


def encode_token(user_id: int) -> str:
    now = dt.datetime.now(dt.timezone.utc)
    payload = {"sub": str(user_id), "iat": now, "exp": now + TOKEN_TTL}
    return jwt.encode(payload, current_app.config["SECRET_KEY"], algorithm=_ALGO)


def decode_token(token: str) -> int:
    """Return the user id from a valid token, or raise jwt.PyJWTError."""
    payload = jwt.decode(token, current_app.config["SECRET_KEY"], algorithms=[_ALGO])
    return int(payload["sub"])


def _bearer_token() -> str | None:
    header = request.headers.get("Authorization", "")
    if header.startswith("Bearer "):
        return header[len("Bearer ") :].strip()
    return None


# --- guard -------------------------------------------------------------------


def require_auth(view):
    """Decorator: reject unauthenticated requests with 401, else set g.user_id."""

    @wraps(view)
    def wrapper(*args, **kwargs):
        token = _bearer_token()
        if not token:
            return jsonify(error="Authentication required."), 401
        try:
            g.user_id = decode_token(token)
        except jwt.PyJWTError:
            return jsonify(error="Your session has expired. Please log in again."), 401
        return view(*args, **kwargs)

    return wrapper
