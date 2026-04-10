"""Tests for checkout agent creation."""
import pytest
from unittest.mock import AsyncMock, MagicMock
from langchain_core.language_models import BaseChatModel

pytestmark = pytest.mark.unit


def test_checkout_agent_creates():
    from app.agent.agents.checkout import create_checkout_agent
    agent = create_checkout_agent(
        llm=MagicMock(spec=BaseChatModel),
        commerce=AsyncMock(), customer_repo=AsyncMock(), stripe_service=AsyncMock(),
        customer_id="cust-123", checkout_session_id="cs-456",
    )
    assert agent is not None
