"""System-wide agent ledger: runs, tool calls, and retrievals.

Features call this module when they open a turn or record a search.
The template graph for ``POST /chat`` stays in ``src.agents.graph``. Its routes are ``src.agents.http``.
"""

from dataclasses import dataclass
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

import src.common.orm  # noqa: F401
from src.common.clock import utc_now
from src.common.redact import redact
from src.models.agent_retrievals import AgentRetrieval
from src.models.agent_runs import AgentRun
from src.models.tool_calls import ToolCall

_AGENT_NAMES = {
    "hr-help-standalone": ("hr-help-standalone", "case_graph_standalone"),
    "hr-help-rules": ("hr-help-rules", "case_graph"),
    "hr-help-retrieval": ("hr-help-retrieval", "retrieval_graph"),
    "hr-help-recommendation": ("hr-help-assessment", "recommend_graph"),
    "hr-help-dispatch": ("hr-help-dispatch", "dispatch_graph"),
}


@dataclass(frozen=True)
class RetrievalHit:
    """A chunk the search kept, in rank order."""

    chunk_id: UUID
    score: float
    retrieval_method: str | None = None


async def start_run(session: AsyncSession, conversation_id: UUID, message_id: UUID, model: str) -> AgentRun:
    """Open a RUNNING run for this turn. The caller commits."""
    agent_name, graph_name = _AGENT_NAMES.get(model, (model, None))
    run = AgentRun(
        id=uuid4(),
        conversation_id=conversation_id,
        message_id=message_id,
        status="RUNNING",
        model=model,
        agent_name=agent_name,
        graph_name=graph_name,
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
    if run.prompt_tokens is not None or run.completion_tokens is not None:
        run.total_tokens = (run.prompt_tokens or 0) + (run.completion_tokens or 0)


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
    tool.input = redact(payload)
    session.add(tool)
    await session.flush()
    return tool


async def complete_search(session: AsyncSession, tool: ToolCall, payload: dict) -> None:
    """Record the chunks the search returned."""
    tool.output = redact(payload)
    tool.status = "SUCCEEDED"
    tool.completed_at = utc_now()
    if tool.started_at is not None and tool.completed_at is not None:
        tool.duration_ms = max(0, int((tool.completed_at - tool.started_at).total_seconds() * 1000))
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
                retrieval_method=hit.retrieval_method,
            )
        )
    await session.flush()
