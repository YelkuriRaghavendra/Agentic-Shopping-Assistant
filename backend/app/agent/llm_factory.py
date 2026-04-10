"""
LLM Factory — provider-agnostic model creation.

Returns LangChain BaseChatModel instances configured from llm.json + env vars.
Supports: OpenAI, Azure OpenAI, Anthropic.

Usage:
    from app.agent.llm_factory import create_chat_model, ModelTier
    model = create_chat_model(ModelTier.PRIMARY)
"""

import os
from enum import Enum

from langchain_core.language_models import BaseChatModel

from app.config.loader import llm_config
from app.core.logging import get_logger

logger = get_logger(__name__)


class ModelTier(str, Enum):
    PRIMARY = "primary"
    CHEAP = "cheap"


def create_chat_model(
    tier: ModelTier = ModelTier.PRIMARY,
    provider_override: str | None = None,
) -> BaseChatModel:
    """
    Create a LangChain chat model for the given tier.

    Resolution order for provider:
      1. provider_override parameter
      2. LLM_PROVIDER env var
      3. llm.json "provider" field
    """
    config = llm_config()
    provider = (
        provider_override
        or os.environ.get("LLM_PROVIDER")
        or config.get("provider", "openai")
    )

    tier_config = config["models"].get(tier.value, config["models"]["primary"])

    # Env var overrides for model name
    env_model_key = f"LLM_{tier.value.upper()}_MODEL"
    model_name = os.environ.get(env_model_key) or tier_config["model"]
    temperature = float(os.environ.get("LLM_TEMPERATURE", tier_config.get("temperature", 0.3)))
    max_tokens = int(os.environ.get("LLM_MAX_TOKENS", tier_config.get("max_tokens", 1024)))

    if provider == "openai":
        from langchain_openai import ChatOpenAI
        api_key = os.environ.get("OPENAI_API_KEY", "")
        logger.info("llm_factory.create", provider="openai", model=model_name, tier=tier.value)
        return ChatOpenAI(
            model=model_name,
            temperature=temperature,
            max_tokens=max_tokens,
            api_key=api_key,
        )

    if provider == "azure_openai":
        from langchain_openai import AzureChatOpenAI
        azure_config = config.get("azure", {})
        deployment = azure_config.get("deployments", {}).get(tier.value, model_name)
        endpoint = os.environ.get("AZURE_OPENAI_ENDPOINT") or azure_config.get("endpoint", "")
        api_version = os.environ.get("AZURE_OPENAI_API_VERSION") or azure_config.get("api_version", "2024-02-15-preview")
        api_key = os.environ.get("AZURE_OPENAI_API_KEY", "")
        logger.info("llm_factory.create", provider="azure", deployment=deployment, tier=tier.value)
        return AzureChatOpenAI(
            azure_deployment=deployment,
            azure_endpoint=endpoint,
            api_version=api_version,
            api_key=api_key,
            temperature=temperature,
            max_tokens=max_tokens,
        )

    if provider == "anthropic":
        from langchain_anthropic import ChatAnthropic
        anthropic_config = config.get("anthropic", {})
        anthropic_model = anthropic_config.get("models", {}).get(tier.value, model_name)
        api_key = os.environ.get("ANTHROPIC_API_KEY", "")
        logger.info("llm_factory.create", provider="anthropic", model=anthropic_model, tier=tier.value)
        return ChatAnthropic(
            model=anthropic_model,
            temperature=temperature,
            max_tokens=max_tokens,
            api_key=api_key,
        )

    raise ValueError(f"Unknown LLM provider: {provider}. Supported: openai, azure_openai, anthropic")
