"""Routes for pausing a subject during an internal assessment, then catching it up."""

from __future__ import annotations

from flask import Blueprint, g, jsonify, request

import scheduling
from auth import require_auth
from clock import today
from db import get_db
from errors import ApiError

bp = Blueprint("assessment", __name__, url_prefix="/api")


def _owned_subject(db, subject_id, user_id):
   owns = db.execute(
       "SELECT 1 FROM subjects WHERE id = ? AND user_id = ? AND archived = 0",
       (subject_id, user_id),
    ).fetchone()
   if not owns:
        raise ApiError("That subject could not be found.", status=404)


@bp.post("/assessment-mode-start")
@require_auth
def start():
    data = request.get_json(silent=True) or {}
    subject_id = data.get("subjectId")
    db = get_db()
    _owned_subject(db, subject_id, g.user_id)
    db.execute("UPDATE subjects SET internal_mode = 1 WHERE id = ?", (subject_id,))
    db.commit()
    return jsonify(ok=True)


@bp.post("/assessment-mode-end")
@require_auth
def end():
    data = request.get_json(silent=True) or {}
    subject_id = data.get("subjectId")
    db = get_db()
    _owned_subject(db, subject_id, g.user_id)

    topics = db.execute(
        "SELECT * FROM topics WHERE subject_id = ? AND archived = 0",
        (subject_id,),
    ).fetchall()
    topic_dicts = [{"id": t["id"], "reviewCount": t["review_count"]} for t in topics]

    for change in scheduling.assessment_complete(topic_dicts, today()):
        db.execute(
            "UPDATE topics SET review_count = ?, next_due = ? WHERE id = ?",
            (change["review_count"], change["next_due"], change["topicId"]),
        )
        db.execute(
            """INSERT INTO reviews (topic_id, reviewed_date, confidence, interval, next_due)
               VALUES (?, ?, ?, ?, ?)""",
            (
                change["topicId"],
                change["reviewed_date"],
                change["confidence"],
                change["interval"],
                change["next_due"],
            ),
        )
    db.execute("UPDATE subjects SET internal_mode = 0 WHERE id = ?", (subject_id,))
    db.commit()
    return jsonify(ok=True)
