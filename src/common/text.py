"""Small text helpers shared by retrieval and the answer."""


def clip_quote(content: str, limit: int = 500) -> str:
    """Collapse whitespace and clip a passage to the citation quote."""
    compact = " ".join(content.split())
    if len(compact) <= limit:
        return compact
    cut = compact[: limit - 1].rsplit(" ", 1)[0]
    if not cut:
        cut = compact[: limit - 1]
    return f"{cut}…"
