"""Call the clarify planner. A failed call becomes a clarification decision, never retrieval."""

import logging
import time
from dataclasses import dataclass

from langchain_openai import ChatOpenAI

from src.core.config import settings
from src.features.clarify.model.decision import (
    CaseFamily,
    ClarifyDecision,
    RequestedAction,
    UserIntent,
)
from src.features.clarify.model.prompt import PROMPT_VERSION, SYSTEM_PROMPT, render_case_prompt

logger = logging.getLogger(__name__)

MAX_RETRIES = 1


@dataclass(frozen=True)
class PlannerResult:
    """One planner attempt, including the safe decision used after a failure."""

    decision: ClarifyDecision
    fallback: bool
    reason: str | None
    latency_ms: int
    model: str
    prompt_version: str = PROMPT_VERSION


def fallback_decision() -> ClarifyDecision:
    """Decision that adds no facts and does not ask for retrieval."""
    return ClarifyDecision(
        family=CaseFamily.GENERAL,
        family_confidence=0,
        extracted_facts=[],
        confirmation_updates=[],
        corrections=[],
        user_intent=UserIntent.UNKNOWN,
        requested_action=RequestedAction.NEED_CLARIFICATION,
        ambiguities=[],
        confidence=0,
        reasoning_summary=None,
    )


async def plan_turn(state: dict) -> PlannerResult:
    """Read one narrative. Timeout, invalid JSON, and schema errors fall back after one retry."""
    model_name = settings.MODEL_NAME
    if not settings.OPENAI_API_KEY:
        return PlannerResult(fallback_decision(), True, "missing_api_key", 0, model_name)
    messages = _messages(state)
    started = time.perf_counter()
    last_error = "invalid_decision"
    for attempt in range(MAX_RETRIES + 1):
        try:
            decision = await _complete(messages, attempt)
            elapsed = int((time.perf_counter() - started) * 1000)
            return PlannerResult(decision, False, None, elapsed, model_name)
        except Exception as exc:
            last_error = type(exc).__name__
            logger.warning("clarify planner attempt %s failed: %s", attempt + 1, last_error)
    elapsed = int((time.perf_counter() - started) * 1000)
    return PlannerResult(fallback_decision(), True, last_error, elapsed, model_name)


def _messages(state: dict) -> list[dict[str, str]]:
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": render_case_prompt(state.get("text") or "", _stored_lines(state))},
    ]


def _stored_lines(state: dict) -> list[str]:
    lines = []
    for key, item in (state.get("stored") or {}).items():
        value = getattr(item, "value", "")
        if not value:
            continue
        mark = "confirmed" if getattr(item, "confirmed", False) else "pending"
        lines.append(f"{key} = {value} [{mark}]")
    return lines


async def _complete(messages: list[dict[str, str]], attempt: int) -> ClarifyDecision:
    prompt = list(messages)
    if attempt:
        prompt.append(
            {
                "role": "user",
                "content": "The previous response did not match the schema. Return one valid decision.",
            }
        )
    model = ChatOpenAI(
        model=settings.MODEL_NAME,
        api_key=settings.OPENAI_API_KEY,
        temperature=0,
        timeout=30,
        max_retries=0,
    )
    structured = model.with_structured_output(ClarifyDecision, method="json_schema")
    parsed = await structured.ainvoke(prompt)
    if isinstance(parsed, ClarifyDecision):
        return parsed
    if isinstance(parsed, dict):
        return ClarifyDecision.model_validate(parsed)
    raise TypeError("planner returned an unexpected payload")
