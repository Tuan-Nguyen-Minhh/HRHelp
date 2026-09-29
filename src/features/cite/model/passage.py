"""One retrieved chunk. Cite owns this value; the answer feature layers it."""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class Passage:
    """A chunk that survived the in-force filter, before it is placed in a layer."""

    chunk_id: UUID
    policy_version_id: UUID
    content: str
    article: str | None
    clause: str | None
    point: str | None
    score: float
    policy_type: str | None
    policy_code: str
    policy_name: str
    origin: str = "hybrid"
