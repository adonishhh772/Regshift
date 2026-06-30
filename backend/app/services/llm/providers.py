from typing import Any

from langchain_core.language_models.chat_models import BaseChatModel

from app.config import settings
from app.services.llm.constants import LlmProviderName


def provider_is_configured(provider: str) -> bool:
    if provider == LlmProviderName.OPENAI:
        return bool(settings.openai_api_key)
    if provider == LlmProviderName.GATEWAY:
        return bool(settings.llm_gateway_url and settings.llm_gateway_api_key)
    if provider == LlmProviderName.AZURE_OPENAI:
        return bool(settings.azure_openai_api_key and settings.azure_openai_endpoint)
    if provider == LlmProviderName.ANTHROPIC:
        return bool(settings.anthropic_api_key)
    return False


def build_chat_model(provider: str, model: str) -> BaseChatModel:
    timeout = settings.llm_request_timeout_seconds
    temperature = settings.llm_temperature

    if provider == LlmProviderName.OPENAI:
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(
            model=model,
            api_key=settings.openai_api_key,
            base_url=settings.openai_api_base,
            temperature=temperature,
            timeout=timeout,
            max_retries=settings.llm_max_retries,
        )

    if provider == LlmProviderName.GATEWAY:
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(
            model=model,
            api_key=settings.llm_gateway_api_key,
            base_url=settings.llm_gateway_url,
            temperature=temperature,
            timeout=timeout,
            max_retries=settings.llm_max_retries,
        )

    if provider == LlmProviderName.AZURE_OPENAI:
        from langchain_openai import AzureChatOpenAI

        return AzureChatOpenAI(
            azure_deployment=model,
            api_key=settings.azure_openai_api_key,
            azure_endpoint=settings.azure_openai_endpoint,
            api_version=settings.azure_openai_api_version,
            temperature=temperature,
            timeout=timeout,
            max_retries=settings.llm_max_retries,
        )

    if provider == LlmProviderName.ANTHROPIC:
        from langchain_anthropic import ChatAnthropic

        return ChatAnthropic(
            model=model,
            api_key=settings.anthropic_api_key,
            temperature=temperature,
            timeout=timeout,
            max_retries=settings.llm_max_retries,
        )

    raise ValueError(f"Unsupported LLM provider: {provider}")


def structured_invoke(
    provider: str,
    model: str,
    schema: type[Any],
    system_prompt: str,
    user_prompt: str,
) -> Any:
    chat_model = build_chat_model(provider, model)
    structured_model = chat_model.with_structured_output(schema)
    from langchain_core.messages import HumanMessage, SystemMessage

    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_prompt),
    ]
    return structured_model.invoke(messages)
