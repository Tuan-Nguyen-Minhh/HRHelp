"""Cohere v2 reranking with complete index validation and explicit degradation."""

import asyncio
import json
import logging
import time
from dataclasses import dataclass, replace
from typing import Literal

import httpx
from pydantic import BaseModel, ConfigDict, Field, StrictInt

from src.core.config import settings
from src.features.cite.model.passage import Passage

logger = logging.getLogger(__name__)


class RankedItem(BaseModel):
    model_config = ConfigDict(extra="ignore")
    index: StrictInt
    relevance_score: float = Field(ge=0, le=1, allow_inf_nan=False)


class RankedResponse(BaseModel):
    results: list[RankedItem]


@dataclass(frozen=True)
class RerankResult:
    passages: list[Passage]
    status: Literal["OK", "MISSING_KEY", "FAILED"]
    error: str = ""


def document_text(passage: Passage) -> str:
    """Metadata is context; source content is never summarized or truncated."""
    return json.dumps({"document_type": passage.policy_type, "document": passage.policy_name,
                       "article": passage.article, "clause": passage.clause, "point": passage.point,
                       "heading": passage.section_title, "content": passage.content}, ensure_ascii=False)


async def rerank(query: str, passages: list[Passage]) -> RerankResult:
    if not passages:
        return RerankResult([], "OK")
    if not settings.COHERE_API_KEY.strip():
        return RerankResult(list(passages), "MISSING_KEY", "COHERE_API_KEY chưa được cấu hình")
    started = time.perf_counter()
    try:
        documents = [document_text(item) for item in passages]
        # A conservative size bound avoids API-side clipping of legal conditions.
        # This is not presented as an exact Cohere token count.
        query_bytes = len(query.encode("utf-8"))
        if query_bytes > 8000 or any(len(doc.encode("utf-8")) + query_bytes > 32000 for doc in documents):
            raise ValueError("rerank input exceeds conservative per-document bound")
        async with asyncio.timeout(settings.COHERE_RERANK_TIMEOUT_SECONDS):
            async with httpx.AsyncClient(timeout=settings.COHERE_RERANK_TIMEOUT_SECONDS) as client:
                response = await client.post(
                    "https://api.cohere.com/v2/rerank",
                    headers={"Authorization": f"Bearer {settings.COHERE_API_KEY.strip()}"},
                    json={"model": settings.COHERE_RERANK_MODEL, "query": query,
                          "documents": documents, "top_n": len(documents), "max_tokens_per_doc": 32768},
                )
                response.raise_for_status()
                payload = RankedResponse.model_validate(response.json())
        indices = [item.index for item in payload.results]
        if sorted(indices) != list(range(len(passages))):
            raise ValueError("rerank response has missing, duplicate, or out-of-range indices")
        ranked = [replace(passages[item.index], rerank_score=item.relevance_score) for item in payload.results]
        ranked.sort(key=lambda item: item.rerank_score, reverse=True)
        logger.info("agent_stage end stage=rerank model=%s passages=%s latency_ms=%s status=OK",
                    settings.COHERE_RERANK_MODEL, len(passages), int((time.perf_counter() - started) * 1000))
        return RerankResult(ranked, "OK")
    except Exception as exc:
        # Never log response bodies or HTTP objects carrying credentials.
        error = f"HTTP_{exc.response.status_code}" if isinstance(exc, httpx.HTTPStatusError) else type(exc).__name__
        logger.warning("agent_stage error stage=rerank model=%s passages=%s latency_ms=%s error=%s",
                       settings.COHERE_RERANK_MODEL, len(passages), int((time.perf_counter() - started) * 1000), error)
        return RerankResult(list(passages), "FAILED", error)
