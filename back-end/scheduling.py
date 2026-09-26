"""Works out when each topic should be reviewed next."""

from __future__ import annotations

from datetime import date, timedelta

# Review schedule: wait this many days after each review
INTERVALS = {1: 1, 2: 3, 3: 7}  # 1st review = 1 day, 2nd = 3 days, 3rd = 7 days
INTERVAL_MAX = 14  # every 14 days after the 3rd review


def interval_for(review_count: int) -> int:
    """How many days until the next review."""
    return INTERVALS.get(review_count, INTERVAL_MAX)


def _parse_due(next_due: str | None) -> date | None:
    """Turn the due date string into a date object. Returns None if never reviewed."""
    return date.fromisoformat(next_due) if next_due else None


def next_due_date(reviewed: date, new_review_count: int) -> date:
    """Calculate the next review date after today's review."""
    return reviewed + timedelta(days=interval_for(new_review_count))


def log_review(topic: dict, today: date) -> dict:
    """Move a topic one step forward, return what changed.

    Takes no confidence argument on purpose. How well the student felt the
    review went is recorded, but it never changes the next due date.
    """
    new_count = int(topic.get("reviewCount") or 0) + 1
    interval = interval_for(new_count)
    return {
        "review_count": new_count,
        "interval": interval,
        "reviewed_date": today.isoformat(),
        "next_due": next_due_date(today, new_count).isoformat(),
    }


def status_of(topic: dict, today: date) -> dict:
    """Check if a topic is new, overdue, due today, or fine."""
    nd = _parse_due(topic.get("nextDue"))
    if nd is None:
        return {"status": "new", "days": 0}
    diff = (today - nd).days  # today - nextDue
    if diff > 0:
        return {"status": "overdue", "days": diff}
    if diff == 0:
        return {"status": "due", "days": 0}
    return {"status": "ok", "days": -diff}


def status_label(status: dict) -> str:
    """Short label for display, e.g. '2d overdue'."""
    kind = status["status"]
    if kind == "new":
        return "NEW"
    if kind == "overdue":
        return f"{status['days']}d overdue"
    if kind == "due":
        return "due today"
    return f"due in {status['days']}d"


def priority_score(topic: dict, today: date) -> int | None:
    """How many days overdue. None if the topic is new."""
    nd = _parse_due(topic.get("nextDue"))
    return None if nd is None else (today - nd).days


def coverage(topics: list) -> int:
    """Percentage of topics reviewed at least once."""
    if not topics:
        return 0
    reviewed = sum(1 for t in topics if int(t.get("reviewCount") or 0) >= 1)
    return round(reviewed / len(topics) * 100)


def build_priorities(subjects: list, today: date, daily_cap: int = 5) -> dict:
    """Build today's review list. Overdue first, then due, then one new topic per subject."""
    active: list[dict] = []
    news: list[dict] = []
    for s in subjects:
        if s.get("internalMode"):
            continue  # paused while the student focuses on the internal
        for t in s.get("topics") or []:
            st = status_of(t, today)
            item = {
                **t,
                "subjectName": s["name"],
                "subjectId": s.get("id", t.get("subjectId")),
                "status": st["status"],
                "days": st["days"],
                "statusLabel": status_label(st),
            }
            if st["status"] in ("overdue", "due"):
                active.append(item)
            elif st["status"] == "new":
                news.append(item)

    overdue = sum(1 for i in active if i["status"] == "overdue")
    due_today = sum(1 for i in active if i["status"] == "due")

    active.sort(key=lambda i: -i["days"])  # most overdue first

    # At most 1 topic per subject
    news.sort(key=lambda i: (i["subjectId"], i.get("id", 0)))
    first_per_subject: list[dict] = []
    seen: set = set()
    for i in news:
        if i["subjectId"] not in seen:
            seen.add(i["subjectId"])
            first_per_subject.append(i)
    first_per_subject.sort(key=lambda i: i.get("id", 0))  # deterministic oldest-first

    display = active + first_per_subject
    shown = display[:daily_cap]

    # Everything the student could review today, in the same ranked order.
    # "rest" is what is left after the daily cap, so the dashboard can offer it.
    first_ids = {i.get("id") for i in first_per_subject}
    everything = display + [i for i in news if i.get("id") not in first_ids]
    rest = everything[len(shown) :]

    total_reviewable = len(active) + len(news)  # everything overdue/due/new
    return {
        "shown": shown,
        "rest": rest,
        "moreCount": total_reviewable - len(shown),
        "overdue": overdue,
        "dueToday": due_today,
    }


def assessment_complete(topics: list, today: date) -> list[dict]:
    """Catch up all topics after an internal assessment is finished."""
    changes = []
    next_due = (today + timedelta(days=7)).isoformat()
    for t in topics:
        new_count = max(int(t.get("reviewCount") or 0), 3)
        changes.append(
            {
                "topicId": t["id"],
                "review_count": new_count,
                "reviewed_date": today.isoformat(),
                "interval": 7,
                "next_due": next_due,
                "confidence": "internal_assessment",
            }
        )
    return changes
