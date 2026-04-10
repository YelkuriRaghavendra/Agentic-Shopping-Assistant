"""Tests for citation and persister nodes."""
import pytest

pytestmark = pytest.mark.unit


def test_citations_node_no_chunks():
    from app.agent.nodes.citations import citations_node
    state = {"agent_response": "Hello!", "retrieved_chunks": []}
    result = citations_node(state)
    assert result["cited_products"] == []


def test_citations_node_empty_response():
    from app.agent.nodes.citations import citations_node
    state = {"agent_response": "", "retrieved_chunks": []}
    result = citations_node(state)
    assert result["cited_products"] == []


def test_citations_node_with_dict_chunks():
    from app.agent.nodes.citations import citations_node
    state = {
        "agent_response": "Check out this shoe [P1]",
        "retrieved_chunks": [{
            "product_id": "p1",
            "content": "Nike Air Max",
            "metadata": {"product_name": "Nike Air Max 270", "price": 150},
            "document_type": "PRODUCT",
            "similarity": 0.9,
        }],
    }
    result = citations_node(state)
    # Should process without errors
    assert isinstance(result["cited_products"], list)
