"""Provider selection must keep text and embedding credentials independent."""

from unittest.mock import AsyncMock

import pytest
from pydantic import ValidationError

from src.core.config import Settings, settings
from src.features.health.model import readiness
from src.services import chat_client


@pytest.mark.parametrize("provider,default_model", [
    ("deepseek", "deepseek-flash"),
    ("mistral", "ministral-8b-2512"),
])
def test_provider_defaults_and_model_override(provider, default_model):
    config = Settings(_env_file=None, DB_USER="test", DB_PASSWORD="test", DB_NAME="test",
                      LLM_PROVIDER=provider, MODEL_NAME="", FALLBACK_MODEL_NAME="")
    assert config.chat_models() == (default_model,)
    assert config.chat_kwargs()["model"] == default_model
    config.MODEL_NAME = "custom-primary"
    config.FALLBACK_MODEL_NAME = "custom-fallback"
    assert config.chat_models() == ("custom-primary", "custom-fallback")
    config.FALLBACK_MODEL_NAME = "custom-primary"
    assert config.chat_models() == ("custom-primary",)


def test_invalid_provider_rejected():
    with pytest.raises(ValidationError):
        Settings(_env_file=None, DB_USER="test", DB_PASSWORD="test", DB_NAME="test",
                 LLM_PROVIDER="unsupported")


def test_mistral_custom_endpoint_and_real_client(monkeypatch):
    monkeypatch.setattr(settings, "LLM_PROVIDER", "mistral")
    monkeypatch.setattr(settings, "MISTRAL_API_KEY", "mistral-test")
    monkeypatch.setattr(settings, "MISTRAL_BASE_URL", "https://mistral.example/v1")
    model = chat_client.create_chat_model("ministral-8b-2512", temperature=0, timeout=30, max_retries=2)
    assert isinstance(model, chat_client.ChatMistralAI)
    assert settings.chat_kwargs()["base_url"] == "https://mistral.example/v1"
    structured = model.with_structured_output(method="json_mode")
    assert structured is not None


@pytest.mark.asyncio
@pytest.mark.parametrize("provider", ["deepseek", "mistral"])
async def test_readiness_uses_selected_credentials(monkeypatch, provider):
    monkeypatch.setattr(settings, "LLM_PROVIDER", provider)
    monkeypatch.setattr(settings, "DEEPSEEK_API_KEY", "")
    monkeypatch.setattr(settings, "MISTRAL_API_KEY", "embedding-key")
    monkeypatch.setattr(settings, "EMBEDDING_MODEL", "mistral-embed")
    monkeypatch.setattr(settings, "COHERE_API_KEY", "cohere-test")
    session = AsyncMock()
    session.scalar.return_value = 1
    ready, checks = await readiness(session)
    assert checks["embedding_configured"] is True
    assert checks["rerank_configured"] is True
    assert checks["llm_configured"] is (provider == "mistral")
    assert ready is (provider == "mistral")
