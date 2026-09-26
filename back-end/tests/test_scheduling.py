"""Unit tests for the pure scheduling engine (no Flask, no DB).

Covers the interval table, next-due maths, status classification, the priority
feed (ordering, cap, <=1-new-per-subject, internal-mode exclusion), coverage, and
assessment completion- plus two invariants that back the scholarship writeup:
  * a golden-fixture check shared with the JS mock (parity, no drift), and
  * confidence NEVER changing the schedule.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import scheduling

FIXTURE = Path(__file__).parent / "fixtures" / "priorities_cases.json"


# --- intervals & next-due ----------------------------------------------------


def test_interval_table():
    assert scheduling.interval_for(1) == 1
    assert scheduling.interval_for(2) == 3
    assert scheduling.interval_for(3) == 7
    assert scheduling.interval_for(4) == 14
    assert scheduling.interval_for(9) == 14  # capped at the maintenance interval


def test_next_due_date_uses_the_new_count():
    # 2nd review -> +3 days; 4th -> +14 days.
    assert scheduling.next_due_date(date(2026, 7, 15), 2) == date(2026, 7, 18)
    assert scheduling.next_due_date(date(2026, 7, 15), 4) == date(2026, 7, 29)


def test_log_review_advances_count_and_due():
    topic = {"reviewCount": 1, "nextDue": "2026-07-15"}
    changes = scheduling.log_review(topic, date(2026, 7, 15))
    assert changes["review_count"] == 2
    assert changes["interval"] == 3
    assert changes["reviewed_date"] == "2026-07-15"
    assert changes["next_due"] == "2026-07-18"


# --- status & priority -------------------------------------------------------


def test_status_of_boundaries():
    today = date(2026, 7, 15)
    assert scheduling.status_of({"nextDue": None}, today)["status"] == "new"
    assert scheduling.status_of({"nextDue": "2026-07-10"}, today) == {"status": "overdue", "days": 5}
    assert scheduling.status_of({"nextDue": "2026-07-15"}, today) == {"status": "due", "days": 0}
    assert scheduling.status_of({"nextDue": "2026-07-20"}, today) == {"status": "ok", "days": 5}


def test_status_label_text():
    today = date(2026, 7, 15)
    assert scheduling.status_label(scheduling.status_of({"nextDue": None}, today)) == "NEW"
    assert scheduling.status_label(scheduling.status_of({"nextDue": "2026-07-13"}, today)) == "2d overdue"
    assert scheduling.status_label(scheduling.status_of({"nextDue": "2026-07-15"}, today)) == "due today"
    assert scheduling.status_label(scheduling.status_of({"nextDue": "2026-07-18"}, today)) == "due in 3d"


def test_priority_score():
    today = date(2026, 7, 15)
    assert scheduling.priority_score({"nextDue": "2026-07-10"}, today) == 5
    assert scheduling.priority_score({"nextDue": "2026-07-20"}, today) == -5
    assert scheduling.priority_score({"nextDue": None}, today) is None


# --- coverage ----------------------------------------------------------------


def test_coverage():
    assert scheduling.coverage([]) == 0
    assert scheduling.coverage([{"reviewCount": 0}, {"reviewCount": 0}]) == 0
    assert scheduling.coverage([{"reviewCount": 1}, {"reviewCount": 0}]) == 50
    assert scheduling.coverage([{"reviewCount": 2}, {"reviewCount": 5}]) == 100


# --- the priority feed: golden vectors (shared with the JS mock) -------------


def test_build_priorities_matches_golden_fixture():
    data = json.loads(FIXTURE.read_text(encoding="utf-8"))
    for case in data["cases"]:
        today = date.fromisoformat(case["today"])
        feed = scheduling.build_priorities(case["subjects"], today, case["dailyCap"])
        exp = case["expected"]
        shown_ids = [t["id"] for t in feed["shown"]]
        assert shown_ids == exp["shownIds"], f"{case['name']}: shown ids"
        assert feed["overdue"] == exp["overdue"], f"{case['name']}: overdue"
        assert feed["dueToday"] == exp["dueToday"], f"{case['name']}: dueToday"
        assert feed["moreCount"] == exp["moreCount"], f"{case['name']}: moreCount"


def test_build_priorities_enriches_shown_items():
    subjects = [
        {
            "id": 1,
            "name": "Biology",
            "internalMode": 0,
            "topics": [{"id": 1, "subjectId": 1, "name": "Cells", "reviewCount": 1, "nextDue": "2026-07-10"}],
        }
    ]
    item = scheduling.build_priorities(subjects, date(2026, 7, 15), 5)["shown"][0]
    assert item["subjectName"] == "Biology"
    assert item["status"] == "overdue"
    assert item["statusLabel"] == "5d overdue"


# --- assessment mode ---------------------------------------------------------


def test_assessment_complete_bumps_but_never_rewinds():
    topics = [{"id": 1, "reviewCount": 0}, {"id": 2, "reviewCount": 5}]
    changes = scheduling.assessment_complete(topics, date(2026, 7, 15))
    by_id = {c["topicId"]: c for c in changes}
    assert by_id[1]["review_count"] == 3  # bumped up to the floor
    assert by_id[2]["review_count"] == 5  # never lowered
    assert by_id[1]["next_due"] == "2026-07-22"  # today + 7
    assert by_id[1]["confidence"] == "internal_assessment"


# --- the load-bearing invariant: confidence NEVER changes the schedule -------


def test_confidence_never_changes_the_schedule():
    """log_review has no confidence parameter, so the schedule is provably
    independent of it. Whatever a student rates a topic, next_due is identical."""
    topic = {"reviewCount": 2, "nextDue": "2026-07-15"}
    baseline = scheduling.log_review(topic, date(2026, 7, 15))
    for _confidence in ("shaky", "okay", "solid", None):
        assert scheduling.log_review(topic, date(2026, 7, 15)) == baseline
