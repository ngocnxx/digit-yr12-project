"""Authentication primitives — password hashing, JWT, and the @require_auth guard.

Two security invariants this module enforces:
  1. Passwords are only ever stored/compared as werkzeug hashes — plaintext is
     never persisted, logged, or returned.
  2. Sessions are stateless: a signed JWT carried as `Authorization: Bearer <token>`
     is the only proof of identity. There is no server-side session store.
"""

from __future__ import annotations

import datetime as dt
from functools import wraps

import jwt
from flask import current_app, g, jsonify, request
from werkzeug.security import check_password_hash, generate_password_hash

TOKEN_TTL = dt.timedelta(days=30)  # how long a login stays valid before re-auth
_ALGO = "HS256"  # symmetric signing with the app SECRET_KEY


# --- passwords ---------------------------------------------------------------


def hash_password(password: str) -> str:
    # pbkdf2:sha256 is available on every OpenSSL build (werkzeug's newer scrypt
    # default is not), so hashes stay portable across interpreters and containers.
    return generate_password_hash(password, method="pbkdf2:sha256")


def verify_password(password_hash: str, password: str) -> bool:
    # Constant-time comparison inside werkzeug — safe against timing attacks.
    return check_password_hash(password_hash, password)


# --- tokens ------------------------------------------------------------------


def encode_token(user_id: int) -> str:
    """Mint a signed JWT for a user. Claims: sub=user id, iat=issued, exp=expiry."""
    now = dt.datetime.now(dt.timezone.utc)
    payload = {"sub": str(user_id), "iat": now, "exp": now + TOKEN_TTL}
    return jwt.encode(payload, current_app.config["SECRET_KEY"], algorithm=_ALGO)


def decode_token(token: str) -> int:
    """Return the user id from a valid token, or raise jwt.PyJWTError.

    jwt.decode verifies the signature AND the `exp` claim, so an expired or
    tampered token raises here rather than silently authenticating.
    """
    payload = jwt.decode(token, current_app.config["SECRET_KEY"], algorithms=[_ALGO])
    return int(payload["sub"])


def _bearer_token() -> str | None:
    """Pull the raw token out of an `Authorization: Bearer <token>` header."""
    header = request.headers.get("Authorization", "")
    if header.startswith("Bearer "):
        return header[len("Bearer ") :].strip()
    return None


# --- guard -------------------------------------------------------------------


def require_auth(view):
    """Decorator for protected routes.

    Rejects anything without a valid token with **401**; on success stashes the
    caller's id in `g.user_id` so the view can scope every query to that user.
    """

    @wraps(view)
    def wrapper(*args, **kwargs):
        token = _bearer_token()
        if not token:
            return jsonify(error="Authentication required."), 401
        try:
            g.user_id = decode_token(token)
        except jwt.PyJWTError:
            # Covers expired, malformed, and bad-signature tokens alike.
            return jsonify(error="Your session has expired. Please log in again."), 401
        return view(*args, **kwargs)

    return wrapper
