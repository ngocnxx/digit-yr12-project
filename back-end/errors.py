"""Shared error type + tiny validation helpers used across routes.

"""

from __future__ import annotations

MAX_NAME_LEN = 80


class ApiError(Exception):
    """ Default 400 (validation) + friendly mesage"""

    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.message = message
        self.status = status


def require_str(value, field: str, *, max_len: int = MAX_NAME_LEN) -> str:
    """Validate and normalise a required, non-empty, length-bounded string."""
    text = (value or "").strip() if isinstance(value, str) else ""
    if not text:
        raise ApiError(f"Please enter a {field}.")
    if len(text) > max_len:
        raise ApiError(f"That {field} is too long (max {max_len} characters).")
    return text
