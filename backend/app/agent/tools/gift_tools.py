"""Gift finder agent tools: gift_search."""

from langchain_core.tools import tool

from app.agent.tools.shopping_tools import _deduplicate_chunks, _format_chunks_for_agent
from app.clients.rag_client import RAGClient
from app.config.loader import search_config


def create_gift_search_tool(rag_client: RAGClient):
    sc = search_config()
    top_k = sc["per_tool"].get("gift_search", {}).get("top_k", 5)

    @tool
    async def gift_search(
        recipient: str,
        interests: str = "",
        budget: float = 0,
        occasion: str = "",
        gender: str = "",
    ) -> str:
        """Find gift recommendations for someone."""
        query = f"gift for {recipient}"
        if interests:
            query = f"{interests} {query}"
        if occasion:
            query += f" {occasion}"

        filters: dict = {"doc_type": "product", "in_stock": True}
        if budget:
            filters["max_price"] = budget

        chunks = await rag_client.retrieve(query=query, filters=filters)
        chunks = _deduplicate_chunks(chunks, top_k)

        if not chunks:
            return f"No gift options found for {recipient}."
        return f"Gift ideas for {recipient} ({len(chunks)} options):\n\n{_format_chunks_for_agent(chunks)}"

    return gift_search
