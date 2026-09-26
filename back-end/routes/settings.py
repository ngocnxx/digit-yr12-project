"""Settings route- the student's daily review cap (3-8, default 5)."""

from __future__ import annotations

from flask import Blueprint, g, jsonify, request

from auth import require_auth
from db import get_db
from errors import ApiError

bp = Blueprint("settings", __name__, url_prefix="/api")

CAP_MIN = 3
CAP_MAX = 8


@bp.put("/settings")
@require_auth
def update_settings():
    data = request.get_json(silent=True) or {}
    try:
        cap = int(data.get("dailyCap"))
    except (TypeError, ValueError) as err:
        raise ApiError("Daily cap must be a number.") from err
    cap = max(CAP_MIN, min(CAP_MAX, cap))  # clamp, never reject

    db = get_db()
    db.execute("UPDATE users SET daily_cap = ? WHERE id = ?", (cap, g.user_id))
    db.commit()
    return jsonify(dailyCap=cap)
