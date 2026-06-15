"""Spaced-repetition scheduling engine — the heart of the app.

PURE PYTHON: this module must never import Flask or sqlite3. Plain data in,
plain data out, so it stays trivially unit-testable in isolation (see CLAUDE.md).

Binding spec (Carpenter 2012 intervals):
    INTERVALS = {1: 1, 2: 3, 3: 7}   # days, keyed by review_count
    INTERVAL_MAX = 14                # days, for review_count >= 4

NOTE: Feature F1 (auth -> onboarding -> subjects/topics) does not use the engine.
The full implementation — log_review, priority scoring, daily-cap selection,
coverage, and assessment mode — lands in slice 2. This file fixes the constants
now so the spec has a single home.
"""

from __future__ import annotations

INTERVALS = {1: 1, 2: 3, 3: 7}
INTERVAL_MAX = 14


def interval_for(review_count: int) -> int:
    """Days until the next review for a topic at the given review_count."""
    return INTERVALS.get(review_count, INTERVAL_MAX)
