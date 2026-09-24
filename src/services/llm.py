from langchain_openai import ChatOpenAI

from src.core.config import settings


def get_llm() -> ChatOpenAI:
    return ChatOpenAI(
        model=settings.MODEL_NAME,
        api_key=settings.OPENAI_API_KEY,
        temperature=settings.LLM_TEMPERATURE,
    )
