"""Tests for LLM factory — verify correct model type returned per provider."""
import pytest

pytestmark = pytest.mark.unit


def test_create_openai_primary(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    from app.agent.llm_factory import create_chat_model, ModelTier
    model = create_chat_model(ModelTier.PRIMARY, provider_override="openai")
    from langchain_openai import ChatOpenAI
    assert isinstance(model, ChatOpenAI)


def test_create_openai_cheap(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    from app.agent.llm_factory import create_chat_model, ModelTier
    model = create_chat_model(ModelTier.CHEAP, provider_override="openai")
    from langchain_openai import ChatOpenAI
    assert isinstance(model, ChatOpenAI)


def test_create_anthropic_primary(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    from app.agent.llm_factory import create_chat_model, ModelTier
    model = create_chat_model(ModelTier.PRIMARY, provider_override="anthropic")
    from langchain_anthropic import ChatAnthropic
    assert isinstance(model, ChatAnthropic)


def test_unknown_provider_raises():
    from app.agent.llm_factory import create_chat_model, ModelTier
    with pytest.raises(ValueError, match="Unknown LLM provider"):
        create_chat_model(ModelTier.PRIMARY, provider_override="unknown_provider")


def test_model_names_from_config(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    from app.agent.llm_factory import create_chat_model, ModelTier
    model = create_chat_model(ModelTier.PRIMARY, provider_override="openai")
    assert model.model_name == "gpt-4o"

    cheap = create_chat_model(ModelTier.CHEAP, provider_override="openai")
    assert cheap.model_name == "gpt-4o-mini"
