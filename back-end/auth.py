"""Authentication: password hashing, JWT, and the @require_auth guard.

Two security  this module have:
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


# passwords 

  #scramble the passwords (sign up)
def hash_password(password: str) -> str:
    
    return generate_password_hash(password, method="pbkdf2:sha256")

 #compare plain passsword to the hash (log in to allow access)
def verify_password(password_hash: str, password: str) -> bool:
    # Constant-time comparison inside werkzeug which safe against timing attacks.
    return check_password_hash(password_hash, password)


# tokens 
 #mapping users data + UTC time 
def encode_token(user_id: int) -> str:
    now = dt.datetime.now(dt.timezone.utc)
    payload = {"sub": str(user_id), "iat": now, "exp": now + TOKEN_TTL} #creating data package  then signs in the secret key
    return jwt.encode(payload, current_app.config["SECRET_KEY"], algorithm=_ALGO)

 #unlocks the otken
def decode_token(token: str) -> int:
    """Return the user id from a valid token, or raise jwt.PyJWTError.

    jwt.decode verifies the signature and the `exp` claim, so an expired or
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


#guard 


def require_auth(view):
    """Decorator for protected routes.

    Rejects anything without a valid token with **401**; on success stashes the
    caller's id in `g.user_id` so the view can scope every query to that user.
    """

    @wraps(view)
    def wrapper(*args, **kwargs):
        if request.method == "OPTIONS":
            return "", 200
        token = _bearer_token()
        # Trace the auth GATE every protected request passes through. We log only
        # the outcome + user id, never the token or password.
        where = f"{request.method} {request.path}"
        if not token:
            print(f"[trace] require_auth: {where} → 401 (no token)")
            return jsonify(error="Authentication required."), 401
        try:
            g.user_id = decode_token(token)
        except jwt.PyJWTError:
            # Covers expired, malformed, and bad-signature tokens alike.
            print(f"[trace] require_auth: {where} → 401 (bad/expired token)")
            return jsonify(error="Your session has expired. Please log in again."), 401
        print(f"[trace] require_auth: {where} → OK as user {g.user_id}")
        return view(*args, **kwargs)

    return wrapper
