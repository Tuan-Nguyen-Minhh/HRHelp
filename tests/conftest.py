import json
from unittest.mock import AsyncMock, Mock

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from src.main import app


@pytest_asyncio.fixture
async def client():
    """Async HTTP client for testing API endpoints."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture
def approved_help_reply(monkeypatch):
    """Keep graph/routing regressions offline; formatter behavior has its own tests."""
    formatter = AsyncMock(side_effect=lambda question, answer, state, **kwargs: answer)
    monkeypatch.setattr("src.agents.case_graph.format_help_reply", formatter)
    return formatter


@pytest.fixture
def dialogue_model(monkeypatch):
    """Exercise the semantic pipeline and persistence without a network call."""

    def interpret(messages):
        payload = json.loads(messages[1]["content"])
        latest = payload["latest_user_message"]
        note = {"text": latest["content"], "source_ids": [latest["id"]]}
        previous = next((turn for turn in reversed(payload["source_turns"]) if turn["role"] == "ASSISTANT"), None)
        return {
            "current_goal": note,
            "interpreted_question": note,
            "topic_transition": "follow_up",
            "links": (
                [
                    {
                        "from_id": latest["id"],
                        "to_id": previous["id"],
                        "relation": "follow_up",
                        "meaning": "Current user follows the previous response.",
                    }
                ]
                if previous
                else []
            ),
            "context_summary": [],
            "corrections": [],
            "open_questions": [],
            "uncertainty": "",
        }

    invoke = AsyncMock(side_effect=interpret)
    model = Mock()
    model.with_structured_output.return_value.ainvoke = invoke
    monkeypatch.setattr("src.features.clarify.model.dialogue_context.create_chat_model", Mock(return_value=model))
    return invoke


@pytest.fixture
def mock_llm():
    """Mock LLM to avoid calling OpenAI during tests.

    Usage in test:
        def test_something(mock_llm):
            # LLM calls will return mock response instead of hitting OpenAI
            ...
    """
    mock = AsyncMock()
    mock.ainvoke.return_value = AsyncMock(content="Mocked LLM response")
    return mock
