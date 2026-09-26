"""Routes for creating and listing subjects."""

from __future__ import annotations

import sqlite3

from flask import Blueprint, g, jsonify, request

import scheduling
from auth import require_auth
from clock import today
from db import get_db
from errors import ApiError, require_str

bp = Blueprint("subjects", __name__, url_prefix="/api/subjects")


def subject_public(row: sqlite3.Row) -> dict:
    return {
        "id": row["id"],
        "name": row["name"],
        "emoji": row["emoji"],
        "colour": row["colour"],
        "internalMode": row["internal_mode"],
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


def review_public(row: sqlite3.Row) -> dict:
    return {
        "reviewedDate": row["reviewed_date"],
        "confidence": row["confidence"],
        "evidence": row["evidence"],
        "reflection": row["reflection"],
        "attachment": row["attachment"],
        "attachmentName": row["attachment_name"],
        "nextDue": row["next_due"],
    }


def load_subjects(db: sqlite3.Connection, user_id: int) -> list[dict]:
    """Load all subjects and their topics for this user."""
    rows = db.execute(
        "SELECT * FROM subjects WHERE user_id = ? AND archived = 0 ORDER BY created_at, id",
        (user_id,),
    ).fetchall()
    subjects = []
    for s in rows:
        topics = db.execute(
            "SELECT * FROM topics WHERE subject_id = ? AND archived = 0 ORDER BY created_at, id",
            (s["id"],),
        ).fetchall()
        item = subject_public(s)
        item["topics"] = [topic_public(t) for t in topics]
        subjects.append(item)
    return subjects


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
    """Return all subjects with their topics and review history."""
    db = get_db()
    subjects = load_subjects(db, g.user_id)
    now = today()
    for s in subjects:
        for t in s["topics"]:
            st = scheduling.status_of(t, now)
            t["status"] = st["status"]
            t["statusLabel"] = scheduling.status_label(st)
            history = db.execute(
                "SELECT * FROM reviews WHERE topic_id = ? ORDER BY id",
                (t["id"],),
            ).fetchall()
            t["reviews"] = [review_public(r) for r in history]
        s["coverage"] = scheduling.coverage(s["topics"])
    return jsonify(subjects=subjects)
