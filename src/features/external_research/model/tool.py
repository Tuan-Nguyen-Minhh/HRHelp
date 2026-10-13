"""External research tool adapter.

This module is intentionally transport-light. The case graph calls one safe
function and the function can be backed by a search API or by an MCP HTTP
bridge. The graph never lets the model invent a tool call on its own.
"""

from collections.abc import Awaitable, Callable
from typing import Any
from urllib.parse import urlparse

import httpx
from pydantic import BaseModel, ConfigDict, Field

from src.core.config import settings


class ExternalResearchQuery(BaseModel):
    """Question sent to the external research tool."""

    model_config = ConfigDict(str_strip_whitespace=True)

    question: str
    description: str = ""
    domains: list[str] = Field(default_factory=list)
    max_results: int = Field(default=5, ge=1, le=10)


class ExternalSource(BaseModel):
    """One external source returned by a search/MCP tool."""

    model_config = ConfigDict(str_strip_whitespace=True)

    title: str = ""
    url: str
    snippet: str = ""
    published_at: str = ""
    source_type: str = "external_web"


class ExternalResearchResult(BaseModel):
    """Normalized external research result."""

    query: str
    provider: str
    sources: list[ExternalSource] = Field(default_factory=list)
    disabled: bool = False
    error: str = ""


ExternalResearchFn = Callable[[ExternalResearchQuery], Awaitable[ExternalResearchResult]]


async def research_external(query: ExternalResearchQuery) -> ExternalResearchResult:
    """Call the configured external research provider.

    Disabled or misconfigured providers return a structured empty result so the
    chat can fail closed with a clear disclaimer.
    """
    provider = settings.EXTERNAL_RESEARCH_PROVIDER.strip().lower() or "disabled"
    if not settings.EXTERNAL_RESEARCH_ENABLED or provider == "disabled":
        return ExternalResearchResult(query=query.question, provider=provider, disabled=True)
    domains = query.domains or _allowed_domains()
    max_results = min(query.max_results, settings.EXTERNAL_RESEARCH_MAX_RESULTS)
    try:
        if provider == "brave":
            return await _search_brave(query.question, domains, max_results)
        if provider == "tavily":
            return await _search_tavily(query.question, domains, max_results)
        if provider == "mcp_http":
            return await _search_mcp_http(query.question, domains, max_results)
    except httpx.HTTPError as exc:
        return ExternalResearchResult(query=query.question, provider=provider, error=type(exc).__name__)
    return ExternalResearchResult(query=query.question, provider=provider, disabled=True, error="unsupported_provider")


async def _search_brave(query: str, domains: list[str], max_results: int) -> ExternalResearchResult:
    if not settings.BRAVE_SEARCH_API_KEY:
        return ExternalResearchResult(query=query, provider="brave", disabled=True, error="missing_brave_key")
    params = {"q": _domain_query(query, domains), "count": max_results, "text_decorations": "false"}
    headers = {"X-Subscription-Token": settings.BRAVE_SEARCH_API_KEY, "Accept": "application/json"}
    async with httpx.AsyncClient(timeout=settings.EXTERNAL_RESEARCH_TIMEOUT_SECONDS) as client:
        response = await client.get("https://api.search.brave.com/res/v1/web/search", params=params, headers=headers)
        response.raise_for_status()
    web = response.json().get("web") or {}
    sources = [
        ExternalSource(
            title=str(item.get("title") or ""),
            url=str(item.get("url") or ""),
            snippet=str(item.get("description") or ""),
        )
        for item in web.get("results") or []
        if item.get("url")
    ]
    return ExternalResearchResult(query=query, provider="brave", sources=_filter_sources(sources, domains, max_results, query))


async def _search_tavily(query: str, domains: list[str], max_results: int) -> ExternalResearchResult:
    if not settings.TAVILY_API_KEY:
        return ExternalResearchResult(query=query, provider="tavily", disabled=True, error="missing_tavily_key")
    payload: dict[str, Any] = {
        "api_key": settings.TAVILY_API_KEY,
        "query": query,
        "max_results": max_results,
        "include_answer": False,
        "search_depth": "advanced",
    }
    if domains:
        payload["include_domains"] = domains
    async with httpx.AsyncClient(timeout=settings.EXTERNAL_RESEARCH_TIMEOUT_SECONDS) as client:
        response = await client.post("https://api.tavily.com/search", json=payload)
        response.raise_for_status()
    sources = [
        ExternalSource(
            title=str(item.get("title") or ""),
            url=str(item.get("url") or ""),
            snippet=str(item.get("content") or ""),
        )
        for item in response.json().get("results") or []
        if item.get("url")
    ]
    return ExternalResearchResult(query=query, provider="tavily", sources=_filter_sources(sources, domains, max_results, query))


async def _search_mcp_http(query: str, domains: list[str], max_results: int) -> ExternalResearchResult:
    base_url = settings.EXTERNAL_RESEARCH_MCP_URL.strip().rstrip("/")
    if not base_url:
        return ExternalResearchResult(query=query, provider="mcp_http", disabled=True, error="missing_mcp_url")
    payload = {
        "name": settings.EXTERNAL_RESEARCH_MCP_TOOL_NAME,
        "arguments": {"query": query, "domains": domains, "max_results": max_results},
    }
    async with httpx.AsyncClient(timeout=settings.EXTERNAL_RESEARCH_TIMEOUT_SECONDS) as client:
        response = await client.post(f"{base_url}/tools/call", json=payload)
        response.raise_for_status()
    sources = _sources_from_mcp_payload(response.json())
    return ExternalResearchResult(query=query, provider="mcp_http", sources=_filter_sources(sources, domains, max_results, query))


def _sources_from_mcp_payload(payload: Any) -> list[ExternalSource]:
    raw_results = payload.get("results") if isinstance(payload, dict) else payload
    if isinstance(raw_results, dict):
        raw_results = raw_results.get("results") or raw_results.get("sources")
    if not isinstance(raw_results, list):
        return []
    sources = []
    for item in raw_results:
        if not isinstance(item, dict) or not item.get("url"):
            continue
        sources.append(
            ExternalSource(
                title=str(item.get("title") or item.get("name") or ""),
                url=str(item.get("url") or ""),
                snippet=str(item.get("snippet") or item.get("content") or item.get("description") or ""),
                published_at=str(item.get("published_at") or item.get("date") or ""),
                source_type=str(item.get("source_type") or "external_web"),
            )
        )
    return sources


def _allowed_domains() -> list[str]:
    return [item.strip().lower() for item in settings.EXTERNAL_RESEARCH_ALLOWED_DOMAINS.split(",") if item.strip()]


def _domain_query(query: str, domains: list[str]) -> str:
    if not domains:
        return query
    domain_filter = " OR ".join(f"site:{domain}" for domain in domains)
    return f"({domain_filter}) {query}"


def _filter_sources(
    sources: list[ExternalSource],
    domains: list[str],
    max_results: int,
    query: str = "",
) -> list[ExternalSource]:
    filtered = [
        source
        for source in sources
        if source.url and _domain_allowed(source.url, domains) and _relevant_to_hr_labor(source, query)
    ]
    return filtered[:max_results]


def _domain_allowed(url: str, domains: list[str]) -> bool:
    if not domains:
        return True
    host = (urlparse(url).hostname or "").lower()
    return any(host == domain or host.endswith(f".{domain}") for domain in domains)


def _relevant_to_hr_labor(source: ExternalSource, query: str) -> bool:
    """Reject official but off-topic pages that broad search often returns."""
    haystack = _fold(" ".join((source.title, source.snippet, source.url)))
    if not haystack:
        return False
    labor_terms = (
        "lao dong",
        "nguoi lao dong",
        "nguoi su dung lao dong",
        "ky luat lao dong",
        "xu ly ky luat",
        "noi quy lao dong",
        "tranh chap lao dong",
        "bo luat lao dong",
        "hop dong lao dong",
        "giai trinh",
        "bien ban",
        "sa thai",
        "bao mat thong tin",
        "thong tin khach hang",
    )
    if any(term in haystack for term in labor_terms):
        return True

    # Keep a narrow fallback for pages whose snippets omit labor phrasing but
    # still overlap with a specific case phrase. Generic words such as "quy
    # trinh" or "quy dinh" are intentionally ignored.
    query_terms = _query_terms(query)
    overlap = sum(1 for term in query_terms if term in haystack)
    return overlap >= 2


def _query_terms(query: str) -> set[str]:
    folded = _fold(query)
    blocked = {
        "research",
        "external",
        "nguon",
        "cong khai",
        "chinh thong",
        "viet nam",
        "quy trinh",
        "quy dinh",
        "thong tin",
        "ho so",
        "can cu",
        "phap luat",
        "tra cuu",
    }
    phrases = {
        "bao mat thong tin",
        "thong tin khach hang",
        "khach hang",
        "chung cu",
        "bien ban",
        "giai trinh",
        "tranh chap",
        "khoi kien",
        "ky luat",
        "sa thai",
        "nghi khong phep",
        "di muon",
    }
    return {phrase for phrase in phrases if phrase in folded and phrase not in blocked}


def _fold(text: str) -> str:
    table = str.maketrans(
        {
            "à": "a",
            "á": "a",
            "ả": "a",
            "ã": "a",
            "ạ": "a",
            "ă": "a",
            "ằ": "a",
            "ắ": "a",
            "ẳ": "a",
            "ẵ": "a",
            "ặ": "a",
            "â": "a",
            "ầ": "a",
            "ấ": "a",
            "ẩ": "a",
            "ẫ": "a",
            "ậ": "a",
            "è": "e",
            "é": "e",
            "ẻ": "e",
            "ẽ": "e",
            "ẹ": "e",
            "ê": "e",
            "ề": "e",
            "ế": "e",
            "ể": "e",
            "ễ": "e",
            "ệ": "e",
            "ì": "i",
            "í": "i",
            "ỉ": "i",
            "ĩ": "i",
            "ị": "i",
            "ò": "o",
            "ó": "o",
            "ỏ": "o",
            "õ": "o",
            "ọ": "o",
            "ô": "o",
            "ồ": "o",
            "ố": "o",
            "ổ": "o",
            "ỗ": "o",
            "ộ": "o",
            "ơ": "o",
            "ờ": "o",
            "ớ": "o",
            "ở": "o",
            "ỡ": "o",
            "ợ": "o",
            "ù": "u",
            "ú": "u",
            "ủ": "u",
            "ũ": "u",
            "ụ": "u",
            "ư": "u",
            "ừ": "u",
            "ứ": "u",
            "ử": "u",
            "ữ": "u",
            "ự": "u",
            "ỳ": "y",
            "ý": "y",
            "ỷ": "y",
            "ỹ": "y",
            "ỵ": "y",
            "đ": "d",
        }
    )
    return text.casefold().translate(table)
