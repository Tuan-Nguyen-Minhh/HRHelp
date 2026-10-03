"""Call the clarify planner. A failed call becomes a clarification decision, never retrieval."""

import logging
import time
from dataclasses import dataclass

import httpx
from langchain_mistralai import ChatMistralAI

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
    model_names = settings.mistral_chat_models()
    primary_model = model_names[0]
    if not settings.MISTRAL_API_KEY:
        return PlannerResult(fallback_decision(), True, "missing_api_key", 0, primary_model)
    messages = _messages(state)
    started = time.perf_counter()
    last_error = "invalid_decision"
    for attempt in range(MAX_RETRIES + 1):
        for model_name in model_names:
            try:
                decision = await _complete(messages, attempt, model_name)
                elapsed = int((time.perf_counter() - started) * 1000)
                return PlannerResult(decision, False, None, elapsed, model_name)
            except Exception as exc:
                last_error = f"{model_name}: {_error_name(exc)}"
                logger.warning("clarify planner attempt %s failed: %s", attempt + 1, last_error)
    elapsed = int((time.perf_counter() - started) * 1000)
    return PlannerResult(fallback_decision(), True, last_error, elapsed, primary_model)


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


async def _complete(messages: list[dict[str, str]], attempt: int, model_name: str) -> ClarifyDecision:
    prompt = list(messages)
    if attempt:
        prompt.append(
            {
                "role": "user",
                "content": "The previous response did not match the schema. Return one valid decision.",
            }
        )
    model = ChatMistralAI(
        **settings.mistral_chat_kwargs(model_name),
        temperature=0,
        timeout=30,
        max_retries=2,
    )
    structured = model.with_structured_output(ClarifyDecision)
    parsed = await structured.ainvoke(prompt)
    if isinstance(parsed, ClarifyDecision):
        return parsed
    if isinstance(parsed, dict):
        return ClarifyDecision.model_validate(parsed)
    raise TypeError("planner returned an unexpected payload")


def _error_name(exc: Exception) -> str:
    if isinstance(exc, httpx.HTTPStatusError):
        response = exc.response
        body = response.text.replace("\n", " ")[:500]
        return f"HTTP {response.status_code}: {body}"
    return type(exc).__name__
