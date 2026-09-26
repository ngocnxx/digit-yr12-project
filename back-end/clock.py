"""Gets today's date in the app timezone (New Zealand)."""

from __future__ import annotations

import os
from datetime import date, datetime
from zoneinfo import ZoneInfo

APP_TIMEZONE = os.environ.get("APP_TIMEZONE", "Pacific/Auckland")


def today() -> date:
    """Returns today's date in NZ time."""
    return datetime.now(ZoneInfo(APP_TIMEZONE)).date()
