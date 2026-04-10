"""Tests for ChatServiceV2."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

pytestmark = pytest.mark.unit


def test_chat_service_v2_imports():
    from app.services.chat_service_v2 import ChatServiceV2
    assert ChatServiceV2 is not None


def test_chat_service_v2_has_handle_method():
    from app.services.chat_service_v2 import ChatServiceV2
    assert hasattr(ChatServiceV2, "handle")
    assert hasattr(ChatServiceV2, "handle_stream")


def test_chat_service_v2_build_input_state():
    """Verify _build_input_state returns expected keys."""
    from app.services.chat_service_v2 import ChatServiceV2

    mock_request = MagicMock()
    mock_request.message = "hello"

    mock_session = MagicMock()
    mock_session.customer_id = None
    mock_session.context = {}

    state = ChatServiceV2._build_input_state(mock_request, mock_session, {})

    assert "messages" in state
    assert state["messages"][0].content == "hello"
    assert state["guardrail_status"] == "pending"
    assert state["intent"] is None
    assert state["cited_products"] == []
    assert state["suggestions"] == []
