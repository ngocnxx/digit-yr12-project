"""Topic routes- create a topic inside one of the user's subjects."""

from __future__ import annotations

from flask import Blueprint, g, jsonify, request

from auth import require_auth
from db import get_db
from errors import ApiError, require_str
from routes.subjects import topic_public

bp = Blueprint("topics", __name__, url_prefix="/api/topics")


@bp.post("")
@require_auth
def create_topic():
    data = request.get_json(silent=True) or {}
    subject_id = data.get("subjectId")
    name = require_str(data.get("name"), "topic name")
    emoji = (data.get("emoji") or "").strip() or None
    standard_number = (data.get("standardNumber") or "").strip() or None

    db = get_db()
    # Ownership check: the subject must exist and belong to the current user.
    owns = db.execute(
        "SELECT 1 FROM subjects WHERE id = ? AND user_id = ? AND archived = 0",
        (subject_id, g.user_id),
    ).fetchone()
    if not owns:
        raise ApiError("That subject could not be found.", status=404)

    cur = db.execute(
        "INSERT INTO topics (subject_id, name, emoji, standard_number) VALUES (?, ?, ?, ?)",
        (subject_id, name, emoji, standard_number),
    )
    db.commit()
    row = db.execute("SELECT * FROM topics WHERE id = ?", (cur.lastrowid,)).fetchone()
    return jsonify(topic=topic_public(row)), 201
