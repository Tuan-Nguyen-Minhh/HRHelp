"""One chat entry point with cross-provider fallback.

Planner and synthesis share this so a 429 / timeout / bad payload on the
primary never crashes the case: each candidate is tried, then the next, and
only when every candidate fails does the caller fall back to its rule-based
decision (fallback_decision / unavailable_assessment).

Mistral is OpenAI-compatible, so every candidate goes through ChatOpenAI with
an explicit base_url. No hidden retries: max_retries=0, failures are logged
with the candidate label.
"""

from __future__ import annotations

import logging
from typing import TypeVar

from langchain_openai import ChatOpenAI
from pydantic import BaseModel

from src.core.config import settings

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


async def acomplete_structured(
    messages: list[dict[str, str]],
    schema: type[T],
    *,
    retry_prompt: str | None = None,
    temperature: float = 0,
    timeout: int = 30,
) -> T:
    """Try each candidate once. The caller retries with a repair prompt on failure."""
    candidates = settings.chat_candidates()
    if not candidates:
        raise RuntimeError("no chat candidate: set OPENAI_API_KEY or MISTRAL_API_KEY")
    prompt = list(messages)
    if retry_prompt:
        prompt.append({"role": "user", "content": retry_prompt})
    last_error: Exception | None = None
    for candidate in candidates:
        try:
            return await _invoke(candidate, prompt, schema, temperature, timeout)
        except Exception as exc:
            last_error = exc
            logger.warning("chat %s failed: %s", candidate["label"], type(exc).__name__)
    assert last_error is not None
    raise last_error


async def _invoke(
    candidate: dict[str, str],
    prompt: list[dict[str, str]],
    schema: type[T],
    temperature: float,
    timeout: int,
) -> T:
    model = ChatOpenAI(
        model=candidate["model"],
        api_key=candidate["api_key"],
        base_url=candidate.get("base_url"),
        temperature=temperature,
        timeout=timeout,
        max_retries=0,
    )
    structured = model.with_structured_output(schema, method="json_schema")
    parsed = await structured.ainvoke(prompt)
    if isinstance(parsed, schema):
        return parsed
    if isinstance(parsed, dict):
        return schema.model_validate(parsed)
    raise TypeError(f"{candidate['label']} returned an unexpected payload")
