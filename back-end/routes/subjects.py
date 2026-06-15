"""Subject routes — create a subject, and list subjects (+topics) for the dashboard."""

from __future__ import annotations

import sqlite3

from flask import Blueprint, g, jsonify, request

from auth import require_auth
from db import get_db
from errors import ApiError, require_str

bp = Blueprint("subjects", __name__, url_prefix="/api/subjects")


def subject_public(row: sqlite3.Row) -> dict:
    return {
        "id": row["id"],
        "name": row["name"],
        "emoji": row["emoji"],
        "colour": row["colour"],
    }


def topic_public(row: sqlite3.Row) -> dict:
    return {
        "id": row["id"],
        "subjectId": row["subject_id"],
        "name": row["name"],
        "emoji": row["emoji"],
        "standardNumber": row["standard_number"],
        "reviewCount": row["review_count"],
        "nextDue": row["next_due"],
    }


@bp.post("")
@require_auth
def create_subject():
    data = request.get_json(silent=True) or {}
    name = require_str(data.get("name"), "subject name")
    emoji = (data.get("emoji") or "").strip() or None
    colour = (data.get("colour") or "").strip() or None

    db = get_db()
    dup = db.execute(
        "SELECT 1 FROM subjects WHERE user_id = ? AND name = ? AND archived = 0",
        (g.user_id, name),
    ).fetchone()
    if dup:
        raise ApiError(f"You already have a subject called “{name}”.")

    cur = db.execute(
        "INSERT INTO subjects (user_id, name, emoji, colour) VALUES (?, ?, ?, ?)",
        (g.user_id, name, emoji, colour),
    )
    db.commit()
    row = db.execute("SELECT * FROM subjects WHERE id = ?", (cur.lastrowid,)).fetchone()
    return jsonify(subject=subject_public(row)), 201


@bp.get("")
@require_auth
def list_subjects():
    """Subjects for the current user, each with its (non-archived) topics."""
    db = get_db()
    subjects = db.execute(
        "SELECT * FROM subjects WHERE user_id = ? AND archived = 0 ORDER BY created_at",
        (g.user_id,),
    ).fetchall()

    result = []
    for s in subjects:
        topics = db.execute(
            "SELECT * FROM topics WHERE subject_id = ? AND archived = 0 ORDER BY created_at",
            (s["id"],),
        ).fetchall()
        item = subject_public(s)
        item["topics"] = [topic_public(t) for t in topics]
        result.append(item)

    return jsonify(subjects=result)
