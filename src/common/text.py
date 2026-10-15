"""Small text helpers shared by case contracts, retrieval, and the answer."""

from typing import Annotated

from pydantic import BeforeValidator


def _uppercase_text(value: object) -> object:
    return value.strip().upper() if isinstance(value, str) else value


UppercaseText = Annotated[str, BeforeValidator(_uppercase_text)]


def clip_quote(content: str, limit: int = 500) -> str:
    """Collapse whitespace and clip a passage to the citation quote."""
    compact = " ".join(content.split())
    if len(compact) <= limit:
        return compact
    cut = compact[: limit - 1].rsplit(" ", 1)[0]
    if not cut:
        cut = compact[: limit - 1]
    return f"{cut}…"
