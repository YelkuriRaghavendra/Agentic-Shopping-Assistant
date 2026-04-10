"""Tests for agent graph state."""
import pytest
from typing import get_type_hints

pytestmark = pytest.mark.unit


def test_agent_state_has_required_fields():
    from app.agent.state import AgentState
    hints = get_type_hints(AgentState, include_extras=True)
    required_fields = [
        "messages", "current_agent", "intent", "slots",
        "shown_products", "customer_id", "customer_profile",
        "checkout_session_id", "checkout_state",
        "agent_response", "retrieved_chunks", "tool_results",
        "cited_products", "suggestions", "guardrail_status",
        "stream_events",
    ]
    for field in required_fields:
        assert field in hints, f"Missing field: {field}"


def test_agent_state_messages_uses_add_messages():
    from app.agent.state import AgentState
    import typing
    hints = typing.get_type_hints(AgentState, include_extras=True)
    msg_hint = hints["messages"]
    assert hasattr(msg_hint, "__metadata__"), "messages should be Annotated with add_messages"
