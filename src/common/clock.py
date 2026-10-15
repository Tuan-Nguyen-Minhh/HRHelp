"""Naive UTC timestamps for columns declared without time zone."""

from datetime import UTC, date, datetime
from zoneinfo import ZoneInfo


def utc_now() -> datetime:
    """Return the current UTC time without ``tzinfo``."""
    return datetime.now(UTC).replace(tzinfo=None)


def vietnam_date(value: datetime | None) -> date | None:
    """Read a stored UTC timestamp as a calendar date in Vietnam."""
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(ZoneInfo("Asia/Ho_Chi_Minh")).date()
