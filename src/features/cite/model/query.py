"""Input of one policy search."""

from dataclasses import dataclass
from datetime import date
from uuid import UUID


@dataclass(frozen=True)
class SearchQuery:
    """What the retrieve node asks the corpus."""

    text: str
    incident_date: date
    agent_run_id: UUID
    family: str
    fact_lines: list[str]
    description: str
    embedding: tuple[float, ...] | None = None
