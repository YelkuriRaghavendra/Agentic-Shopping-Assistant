"""Tests for suggestions agent."""
import pytest
from unittest.mock import AsyncMock, MagicMock
from langchain_core.messages import AIMessage

pytestmark = pytest.mark.unit


@pytest.mark.asyncio
async def test_suggestions_returns_list():
    from app.agent.agents.suggestions import create_suggestions_node
    mock_llm = MagicMock()
    mock_llm.ainvoke = AsyncMock(return_value=AIMessage(
        content='{"suggestions": [{"label": "Compare top two", "message": "Compare the first two products"}]}'
    ))
    node = create_suggestions_node(mock_llm)
    state = {"intent": "product_search", "slots": {"category": "running"}, "agent_response": "Here are shoes...", "shown_products": [], "customer_profile": {}, "current_agent": "shopping"}
    result = await node(state)
    assert len(result["suggestions"]) == 1
    assert result["suggestions"][0]["label"] == "Compare top two"


@pytest.mark.asyncio
async def test_suggestions_handles_invalid_json():
    from app.agent.agents.suggestions import create_suggestions_node
    mock_llm = MagicMock()
    mock_llm.ainvoke = AsyncMock(return_value=AIMessage(content="not json"))
    node = create_suggestions_node(mock_llm)
    state = {"intent": "general", "slots": {}, "agent_response": "Hello!", "shown_products": [], "customer_profile": {}, "current_agent": "shopping"}
    result = await node(state)
    assert result["suggestions"] == []


@pytest.mark.asyncio
async def test_suggestions_caps_at_max_count():
    from app.agent.agents.suggestions import create_suggestions_node
    mock_llm = MagicMock()
    mock_llm.ainvoke = AsyncMock(return_value=AIMessage(
        content='{"suggestions": [{"label": "A", "message": "a"}, {"label": "B", "message": "b"}, {"label": "C", "message": "c"}, {"label": "D", "message": "d"}, {"label": "E", "message": "e"}]}'
    ))
    node = create_suggestions_node(mock_llm)
    state = {"intent": "search", "slots": {}, "agent_response": "products", "shown_products": [], "customer_profile": {}, "current_agent": "shopping"}
    result = await node(state)
    assert len(result["suggestions"]) == 4  # max_count from config
