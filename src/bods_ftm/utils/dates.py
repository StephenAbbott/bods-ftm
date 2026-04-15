from __future__ import annotations

from datetime import date, datetime


def today_iso() -> str:
    """Return today's date as an ISO 8601 string."""
    return date.today().isoformat()


def now_iso() -> str:
    """Return the current datetime as an ISO 8601 string."""
    return datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")


def normalise_date(value: str | None) -> str | None:
    """Pass through a date string if it looks like a valid ISO date, else None.

    FTM accepts partial dates (YYYY, YYYY-MM, YYYY-MM-DD). BODS accepts
    YYYY-MM-DD only. If the value is a year or year-month, return as-is for
    FTM use; callers that need full BODS compliance should validate separately.
    """
    if not value:
        return None
    value = value.strip()
    if len(value) >= 4:
        return value
    return None
