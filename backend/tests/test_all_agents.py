"""Tests for all agent creation."""
import pytest
from unittest.mock import AsyncMock, MagicMock
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, AIMessage

pytestmark = pytest.mark.unit


@pytest.fixture
def mock_llm():
    llm = MagicMock(spec=BaseChatModel)
    llm.ainvoke = AsyncMock()
    return llm


@pytest.fixture
def mock_rag():
    return AsyncMock()


# Supervisor tests
@pytest.mark.asyncio
async def test_supervisor_routes_product_search(mock_llm):
    from app.agent.agents.supervisor import create_supervisor_node
    mock_llm.ainvoke.return_value = AIMessage(
        content='{"agent": "shopping", "intent": "product_search", "reasoning": "wants shoes"}'
    )
    node = create_supervisor_node(mock_llm)
    state = {
        "messages": [HumanMessage(content="I want running shoes")],
        "current_agent": None,
        "intent": None,
        "slots": {},
        "customer_profile": {},
        "checkout_state": {},
    }
    result = await node(state)
    assert result["current_agent"] == "shopping"


@pytest.mark.asyncio
async def test_supervisor_commerce_keyword_routes_checkout(mock_llm):
    from app.agent.agents.supervisor import create_supervisor_node
    node = create_supervisor_node(mock_llm)
    state = {
        "messages": [HumanMessage(content="add to cart")],
        "current_agent": None,
        "intent": None,
        "slots": {},
        "customer_profile": {},
        "checkout_state": {},
    }
    result = await node(state)
    assert result["current_agent"] == "checkout"


@pytest.mark.asyncio
async def test_supervisor_stays_in_checkout(mock_llm):
    from app.agent.agents.supervisor import create_supervisor_node
    node = create_supervisor_node(mock_llm)
    state = {
        "messages": [HumanMessage(content="ship to home")],
        "current_agent": "checkout",
        "intent": None,
        "slots": {},
        "customer_profile": {},
        "checkout_state": {"active": True},
    }
    result = await node(state)
    assert result["current_agent"] == "checkout"
    mock_llm.ainvoke.assert_not_called()


# Agent creation tests
def test_shopping_agent_creates(mock_llm, mock_rag):
    from app.agent.agents.shopping import create_shopping_agent
    agent = create_shopping_agent(mock_llm, mock_rag)
    assert agent is not None


def test_style_advisor_creates(mock_llm, mock_rag):
    from app.agent.agents.style_advisor import create_style_advisor_agent
    agent = create_style_advisor_agent(mock_llm, mock_rag)
    assert agent is not None


def test_gift_finder_creates(mock_llm, mock_rag):
    from app.agent.agents.gift_finder import create_gift_finder_agent
    agent = create_gift_finder_agent(mock_llm, mock_rag)
    assert agent is not None


def test_support_agent_creates(mock_llm, mock_rag):
    from app.agent.agents.support import create_support_agent
    agent = create_support_agent(mock_llm, mock_rag)
    assert agent is not None
