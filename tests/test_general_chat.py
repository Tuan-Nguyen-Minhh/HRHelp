from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest

from src.core.config import settings
from src.features.clarify.model import general_chat, memory
from src.services import content_safety
from src.services.content_safety import SafetyVerdict


@pytest.fixture(autouse=True)
def reset_budget(monkeypatch):
    general_chat._WINDOWS.clear()
    monkeypatch.setattr(settings, "GENERAL_CHAT_ENABLED", True)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "verdict",
    [
        SafetyVerdict(action="safe_response", category="harm"),
        SafetyVerdict(action="safe_response", category="self_harm"),
        SafetyVerdict(action="safe_response", category="privacy"),
        SafetyVerdict(action="unavailable"),
        SafetyVerdict(action="redirect_domain", category="specialist"),
    ],
)
async def test_input_not_allowed_never_calls_generator(monkeypatch, verdict):
    monkeypatch.setattr(general_chat, "check_content", AsyncMock(return_value=verdict))
    generator = Mock(side_effect=AssertionError("Unsafe/unchecked input cannot generate"))
    monkeypatch.setattr(general_chat, "create_chat_model", generator)
    result = await general_chat.answer_general_chat("Synthetic input", {})
    assert result.safety_action == verdict.action
    assert result.text and "Synthetic input" not in result.text
    generator.assert_not_called()


@pytest.mark.asyncio
async def test_output_is_moderated_before_release_and_case_context_is_not_sent(monkeypatch):
    check = AsyncMock(
        side_effect=[SafetyVerdict(action="allow"), SafetyVerdict(action="safe_response", category="authority")]
    )
    monkeypatch.setattr(general_chat, "check_content", check)
    invoke = AsyncMock(return_value=general_chat.GeneralReply(answer="Đã phê duyệt hồ sơ."))
    model = Mock()
    model.with_structured_output.return_value.ainvoke = invoke
    monkeypatch.setattr(general_chat, "create_chat_model", Mock(return_value=model))
    result = await general_chat.answer_general_chat(
        "Xin chào",
        {
            "case_code": "SECRET_CASE",
            "description": "SECRET_FACT",
            "stored": {"sensitive": "SECRET_FACT"},
            "social_context": {"general_messages": [{"role": "USER", "content": "Tôi thích bún"}]},
        },
    )
    assert "Đã phê duyệt" not in result.text
    assert check.await_count == 2
    assert check.call_args.kwargs["answer"] == "Đã phê duyệt hồ sơ."
    prompt = str(invoke.call_args.args)
    assert "SECRET_CASE" not in prompt and "SECRET_FACT" not in prompt
    assert "Tôi thích bún" in prompt
    assert not model.bind_tools.called


@pytest.mark.asyncio
async def test_safe_chat_is_released_only_after_both_checks(monkeypatch):
    check = AsyncMock(return_value=SafetyVerdict(action="allow"))
    monkeypatch.setattr(general_chat, "check_content", check)
    model = Mock()
    model.with_structured_output.return_value.ainvoke = AsyncMock(
        return_value=general_chat.GeneralReply(answer="Bún hay cơm, bạn thích món nào?")
    )
    monkeypatch.setattr(general_chat, "create_chat_model", Mock(return_value=model))
    result = await general_chat.answer_general_chat("Hôm nay ăn gì?", {})
    assert result.text == "Bún hay cơm, bạn thích món nào?"
    assert result.safety_action == "allow" and check.await_count == 2


@pytest.mark.asyncio
async def test_moderation_unavailable_fails_closed(monkeypatch):
    monkeypatch.setattr(settings, "LLM_PROVIDER", "deepseek")
    monkeypatch.setattr(settings, "DEEPSEEK_API_KEY", "test")
    monkeypatch.setattr(content_safety, "create_chat_model", Mock(side_effect=RuntimeError("offline")))
    assert (await content_safety.check_content("Hello")).action == "unavailable"


def test_chat_rate_limit_has_bounded_window(monkeypatch):
    monkeypatch.setattr(settings, "GENERAL_CHAT_RATE_LIMIT", 2)
    clock = Mock(return_value=1.0)
    monkeypatch.setattr(general_chat.time, "monotonic", clock)
    assert general_chat.within_chat_budget("user-a")
    assert general_chat.within_chat_budget("user-a")
    assert not general_chat.within_chat_budget("user-a")
    assert general_chat.within_chat_budget("user-b")
    clock.return_value = 62
    assert general_chat.within_chat_budget("user-a")


@pytest.mark.asyncio
async def test_memory_scopes_both_sides_before_window_and_keeps_clarification(monkeypatch):
    def row(role, text, **meta):
        return SimpleNamespace(role=role, content=text, created_at=None, message_metadata=meta)

    rows = [row("USER", "Địa điểm Kho A"), row("ASSISTANT", "Xác nhận địa điểm")]
    for _ in range(10):
        rows.extend(
            [
                row("USER", "Ăn gì?", context_scope="general", include_in_general_context=True),
                row("ASSISTANT", "Ăn bún nhé", context_scope="general", include_in_general_context=True),
            ]
        )
    rows.append(row("USER", "Không đưa chuyện riêng vào facts", context_scope="system_help"))
    rows.append(
        row(
            "ASSISTANT",
            "Hỏi quyền hay thực hiện?",
            context_scope="routing_clarification",
            routing_clarification={
                "original_question": "Bạn xử lý duyệt giúp tôi",
                "question": "Hỏi quyền hay thực hiện?",
            },
        )
    )
    rows.append(row("USER", "Tôi chỉ hỏi quyền", context_scope="routing_clarification"))
    monkeypatch.setattr(memory, "list_messages", AsyncMock(return_value=rows))
    business = await memory._recent_messages(AsyncMock(), uuid4())
    assert [r["content"] for r in business] == ["Địa điểm Kho A", "Xác nhận địa điểm"]
    social = await memory.side_context(AsyncMock(), uuid4())
    assert len(social["general_messages"]) == 8
    assert "Kho A" not in str(social)
    assert social["routing_clarification"]["original_question"] == "Bạn xử lý duyệt giúp tôi"


@pytest.mark.asyncio
async def test_generator_timeout_never_releases_unchecked_content(monkeypatch):
    monkeypatch.setattr(general_chat, "check_content", AsyncMock(return_value=SafetyVerdict(action="allow")))
    model = Mock()
    model.with_structured_output.return_value.ainvoke = AsyncMock(side_effect=TimeoutError())
    monkeypatch.setattr(general_chat, "create_chat_model", Mock(return_value=model))
    result = await general_chat.answer_general_chat("Hello", {})
    assert result.safety_action == "unavailable"
