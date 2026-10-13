"""Verify all chat paths use DeepSeek's OpenAI-compatible JSON output."""
import pytest
from src.core.config import settings
from src.features.clarify.model import planner
from src.features.cite.model import policy_answer
from src.features.answer.model import synthesis


@pytest.mark.asyncio
@pytest.mark.parametrize("module,schema", [
    (planner, planner.ClarifyDecision),
    (policy_answer, policy_answer.PolicyAnswer),
    (synthesis, synthesis.Assessment),
])
async def test_deepseek_chat_request(monkeypatch, module, schema):
    captured = {}

    class Client:
        def __init__(self, **kwargs):
            captured.update(kwargs)

        def with_structured_output(self, output_schema, *, method):
            assert output_schema is schema
            assert method == "json_mode"
            return self

        async def ainvoke(self, messages):
            assert "JSON schema" in messages[-1]["content"]
            return schema.model_construct()

    monkeypatch.setattr(settings, "DEEPSEEK_API_KEY", "deepseek-test")
    monkeypatch.setattr(settings, "DEEPSEEK_BASE_URL", "https://api.deepseek.com")
    monkeypatch.setattr(module, "ChatOpenAI", Client)
    result = await module._complete([{"role": "user", "content": "test"}], 0, "deepseek-flash")
    assert isinstance(result, schema)
    assert captured["api_key"] == "deepseek-test"
    assert captured["base_url"] == "https://api.deepseek.com"
    assert captured["model"] == "deepseek-flash"
