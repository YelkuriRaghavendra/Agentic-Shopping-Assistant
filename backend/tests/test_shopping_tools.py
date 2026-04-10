"""Tests for shopping agent tools."""
import pytest
from unittest.mock import AsyncMock, MagicMock

pytestmark = pytest.mark.unit


@pytest.fixture
def mock_rag_client():
    client = AsyncMock()
    client.retrieve = AsyncMock(return_value=[
        MagicMock(
            product_id="p1",
            content="Nike Air Max 270 running shoe",
            metadata={"product_name": "Nike Air Max 270", "price": 150, "color": "black"},
            similarity=0.95,
            document_type="PRODUCT",
        ),
    ])
    return client


@pytest.mark.asyncio
async def test_search_products_tool(mock_rag_client):
    from app.agent.tools.shopping_tools import create_search_products_tool
    tool = create_search_products_tool(mock_rag_client)
    result = await tool.ainvoke({"query": "black nike running shoes"})
    assert "Nike Air Max" in str(result)
    mock_rag_client.retrieve.assert_called_once()


@pytest.mark.asyncio
async def test_search_products_with_filters(mock_rag_client):
    from app.agent.tools.shopping_tools import create_search_products_tool
    tool = create_search_products_tool(mock_rag_client)
    result = await tool.ainvoke({
        "query": "running shoes",
        "brand": "Nike",
        "max_price": 200,
        "color": "black",
    })
    call_args = mock_rag_client.retrieve.call_args
    filters = call_args.kwargs.get("filters") or (call_args[1].get("filters") if len(call_args) > 1 else {})
    assert filters.get("brand") == "Nike" or "Nike" in str(call_args)


@pytest.mark.asyncio
async def test_stock_check_tool(mock_rag_client):
    from app.agent.tools.shopping_tools import create_stock_check_tool
    tool = create_stock_check_tool(mock_rag_client)
    result = await tool.ainvoke({"product_name": "Nike Air Max", "size": "10"})
    assert "1" in str(result) or "Nike" in str(result)
