"""Verify all chat paths use DeepSeek's OpenAI-compatible JSON output."""
import pytest
from src.core.config import settings
from src.services import chat_client
from src.features.clarify.model import intent, case_qa
from src.features.external_research.model import answer as external_answer
from src.features.clarify.model import planner
from src.features.cite.model import policy_answer
from src.features.answer.model import synthesis


@pytest.mark.asyncio
@pytest.mark.parametrize("module,schema", [
    (planner, planner.ClarifyDecision),
    (policy_answer, policy_answer.PolicyAnswer),
    (synthesis, synthesis.Assessment),
    (intent, intent.IntentDecision),
    (case_qa, case_qa.CaseMemoryAnswer),
    (external_answer, external_answer.ExternalResearchAnswer),
])
@pytest.mark.parametrize("provider", ["deepseek", "mistral"])
async def test_chat_request(monkeypatch, module, schema, provider):
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

    monkeypatch.setattr(settings, "LLM_PROVIDER", provider)
    monkeypatch.setattr(settings, "DEEPSEEK_API_KEY", "deepseek-test")
    monkeypatch.setattr(settings, "MISTRAL_API_KEY", "mistral-test")
    monkeypatch.setattr(settings, "MISTRAL_BASE_URL", "")
    monkeypatch.setattr(settings, "DEEPSEEK_BASE_URL", "https://api.deepseek.com")
    monkeypatch.setattr(chat_client, "ChatOpenAI" if provider == "deepseek" else "ChatMistralAI", Client)
    model_name = "deepseek-flash" if provider == "deepseek" else "ministral-8b-2512"
    result = await module._complete([{"role": "user", "content": "test"}], 0, model_name)
    assert isinstance(result, schema)
    assert captured["api_key"] == f"{provider}-test"
    if provider == "deepseek":
        assert captured["base_url"] == "https://api.deepseek.com"
    else:
        assert "base_url" not in captured
    assert captured["model"] == model_name
