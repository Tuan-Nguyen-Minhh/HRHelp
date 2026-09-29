"""Naive UTC timestamps for columns declared without time zone."""

from datetime import UTC, datetime


def utc_now() -> datetime:
    """Return the current UTC time without ``tzinfo``."""
    return datetime.now(UTC).replace(tzinfo=None)
