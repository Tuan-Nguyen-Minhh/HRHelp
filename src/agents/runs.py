"""System-wide agent ledger: runs, tool calls, and retrievals.

Features call this module when they open a turn or record a search.
The template graph for ``POST /chat`` stays in ``src.agents.graph``. Its routes are ``src.agents.http``.
"""

from dataclasses import dataclass
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

import src.common.orm  # noqa: F401
from src.common.clock import utc_now
from src.models.agent_retrievals import AgentRetrieval
from src.models.agent_runs import AgentRun
from src.models.tool_calls import ToolCall


@dataclass(frozen=True)
class RetrievalHit:
    """A chunk the search kept, in rank order."""

    chunk_id: UUID
    score: float


async def start_run(session: AsyncSession, conversation_id: UUID, message_id: UUID, model: str) -> AgentRun:
    """Open a RUNNING run for this turn. The caller commits."""
    run = AgentRun(
        id=uuid4(),
        conversation_id=conversation_id,
        message_id=message_id,
        status="RUNNING",
        model=model,
        started_at=utc_now(),
    )
    session.add(run)
    await session.flush()
    return run


def finish_run(run: AgentRun, output_message_id: UUID) -> None:
    """Mark the run succeeded and point it at the assistant message."""
    run.status = "SUCCEEDED"
    run.output_message_id = output_message_id
    run.completed_at = utc_now()
    run.error = None


async def mark_run_failed(session: AsyncSession, run_id: UUID, error: str) -> None:
    """Record a failure on a run that was already committed."""
    run = await session.get(AgentRun, run_id)
    if run is None:
        return
    run.status = "FAILED"
    run.error = error[:2000]
    run.completed_at = utc_now()


async def begin_search(session: AsyncSession, run_id: UUID, payload: dict) -> ToolCall:
    """Record that ``search_policy`` has started."""
    tool = ToolCall(
        id=uuid4(),
        agent_run_id=run_id,
        tool_name="search_policy",
        status="RUNNING",
        started_at=utc_now(),
    )
    tool.input = payload
    session.add(tool)
    await session.flush()
    return tool


async def complete_search(session: AsyncSession, tool: ToolCall, payload: dict) -> None:
    """Record the chunks the search returned."""
    tool.output = payload
    tool.status = "SUCCEEDED"
    tool.completed_at = utc_now()
    await session.flush()


async def save_retrievals(session: AsyncSession, run_id: UUID, hits: list[RetrievalHit]) -> None:
    """One retrieval row per kept chunk. Rank starts at 1."""
    for rank, hit in enumerate(hits, start=1):
        session.add(
            AgentRetrieval(
                id=uuid4(),
                agent_run_id=run_id,
                chunk_id=hit.chunk_id,
                score=hit.score,
                rank=rank,
            )
        )
    await session.flush()
