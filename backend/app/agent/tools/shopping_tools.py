"""
Shopping agent tools.

Tools: search_products, compare_products, stock_check.
Each tool wraps RAG client calls and returns structured results.
"""

import asyncio
from langchain_core.tools import tool

from app.clients.rag_client import RAGClient, RetrievedChunk
from app.config.loader import search_config
from app.core.logging import get_logger

logger = get_logger(__name__)


def _deduplicate_chunks(chunks: list[RetrievedChunk], top_k: int | None = None) -> list[RetrievedChunk]:
    if top_k is None:
        top_k = search_config()["defaults"]["dedup_top_k"]
    seen: set[str] = set()
    result: list[RetrievedChunk] = []
    for chunk in chunks:
        pid = chunk.product_id
        if pid and pid in seen:
            continue
        if pid:
            seen.add(pid)
        result.append(chunk)
        if len(result) >= top_k:
            break
    return result


def _enrich_query(query: str, args: dict) -> str:
    parts = [query]
    for key in ("use_case", "category", "brand", "size"):
        val = args.get(key)
        if val:
            parts.append(f"size {val}" if key == "size" else val)
    seen: set[str] = set()
    tokens: list[str] = []
    for part in parts:
        for token in part.split():
            lower = token.lower()
            if lower not in seen:
                seen.add(lower)
                tokens.append(token)
    return " ".join(tokens)


def _format_chunks_for_agent(chunks: list[RetrievedChunk]) -> str:
    if not chunks:
        return "No products found."
    lines = []
    for i, chunk in enumerate(chunks):
        meta = chunk.metadata
        price = f" | ${meta['price']}" if meta.get("price") else ""
        rating = f" | rating {meta['rating']}" if meta.get("rating") else ""
        lines.append(f"[P{i+1}] {chunk.product_id}{price}{rating}\n{chunk.content}")
    return "\n\n---\n\n".join(lines)


def create_search_products_tool(rag_client: RAGClient):
    sc = search_config()
    default_top_k = sc["per_tool"]["search_products"]["top_k"]

    @tool
    async def search_products(
        query: str,
        brand: str = "",
        category: str = "",
        use_case: str = "",
        max_price: float = 0,
        size: str = "",
        color: str = "",
    ) -> str:
        """Search for products. Use when customer wants to find or buy something."""
        args = {"brand": brand, "category": category, "use_case": use_case, "size": size}
        enriched_query = _enrich_query(query, args)
        if color:
            enriched_query = f"{color} {enriched_query}"

        filters: dict = {}
        if color:
            filters["color"] = color.lower()
        if brand:
            filters["brand"] = brand
        if max_price:
            filters["max_price"] = max_price
        if category:
            filters["doc_type"] = "product"

        chunks = await rag_client.retrieve(query=enriched_query, filters=filters)
        chunks = _deduplicate_chunks(chunks, default_top_k)

        if color and chunks:
            color_lower = color.lower()
            color_matched = [
                c for c in chunks
                if color_lower in c.content.lower()
                or color_lower in c.metadata.get("color", "").lower()
                or color_lower in c.metadata.get("product_name", "").lower()
            ]
            if color_matched:
                chunks = color_matched

        return _format_chunks_for_agent(chunks)

    return search_products


def create_compare_products_tool(rag_client: RAGClient):
    sc = search_config()
    top_k_per = sc["per_tool"]["compare_products"]["top_k_per_product"]

    @tool
    async def compare_products(
        product_names: list[str],
        aspects: str = "",
    ) -> str:
        """Compare two or more products side by side."""
        if len(product_names) < 2:
            return "Need at least 2 products to compare."

        tasks = [
            rag_client.retrieve(query=name, filters={"doc_type": "product"})
            for name in product_names
        ]
        all_results = await asyncio.gather(*tasks)

        seen_ids: set[str] = set()
        final_chunks: list[RetrievedChunk] = []
        for chunks in all_results:
            deduped = _deduplicate_chunks(chunks, top_k_per)
            for chunk in deduped:
                if chunk.product_id not in seen_ids:
                    final_chunks.append(chunk)
                    seen_ids.add(chunk.product_id)
                    break

        return _format_chunks_for_agent(final_chunks)

    return compare_products


def create_stock_check_tool(rag_client: RAGClient):
    sc = search_config()
    top_k = sc["per_tool"]["stock_check"]["top_k"]

    @tool
    async def stock_check(
        product_name: str,
        size: str = "",
        color: str = "",
    ) -> str:
        """Check if a specific item is in stock."""
        query = product_name
        if color:
            query = f"{color} {query}"
        if size:
            query = f"{query} size {size}"

        chunks = await rag_client.retrieve(
            query=query,
            filters={"doc_type": "product", "in_stock": True},
            top_k=top_k,
        )
        chunks = _deduplicate_chunks(chunks, top_k)

        if not chunks:
            return f"No stock found for {product_name}. The item appears unavailable."
        return f"Stock check for {product_name}: {len(chunks)} available.\n\n{_format_chunks_for_agent(chunks)}"

    return stock_check
