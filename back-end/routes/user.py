"""User routes- onboarding completion flag."""

from __future__ import annotations

from flask import Blueprint, g, jsonify

from auth import require_auth
from db import get_db

bp = Blueprint("user", __name__, url_prefix="/api/user")


@bp.put("/onboarding")
@require_auth
def complete_onboarding():
    db = get_db()
    db.execute("UPDATE users SET onboarding_done = 1 WHERE id = ?", (g.user_id,))
    db.commit()
    return jsonify(ok=True)
