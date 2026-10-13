"""Create text models using the provider selected in the environment."""

from langchain_mistralai import ChatMistralAI
from langchain_openai import ChatOpenAI

from src.core.config import settings


def create_chat_model(model_name: str | None = None, **kwargs):
    client = ChatOpenAI if settings.LLM_PROVIDER == "deepseek" else ChatMistralAI
    return client(**settings.chat_kwargs(model_name), **kwargs)
