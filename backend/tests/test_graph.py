"""Tests for main graph assembly."""
import pytest
from unittest.mock import AsyncMock

pytestmark = pytest.mark.unit


def test_graph_builds(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    from app.agent.graph import build_graph
    graph = build_graph(rag_client=AsyncMock())
    assert graph is not None


def test_graph_has_expected_nodes(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    from app.agent.graph import build_graph
    graph = build_graph(rag_client=AsyncMock())
    node_names = set(graph.get_graph().nodes.keys())
    expected = {"guardrails", "supervisor", "shopping", "style_advisor", "gift_finder", "support"}
    assert expected.issubset(node_names), f"Missing nodes: {expected - node_names}"
