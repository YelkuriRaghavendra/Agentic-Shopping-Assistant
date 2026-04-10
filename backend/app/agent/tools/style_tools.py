"""Style advisor agent tools: outfit_pairing, size_advice."""

from langchain_core.tools import tool

from app.agent.tools.shopping_tools import _deduplicate_chunks, _format_chunks_for_agent
from app.clients.rag_client import RAGClient
from app.config.loader import search_config, style_config


def create_outfit_pairing_tool(rag_client: RAGClient):
    @tool
    async def outfit_pairing(
        owned_colour: str,
        owned_category: str,
        wanted_category: str,
        occasion: str = "",
        budget: float = 0,
        size: str = "",
    ) -> str:
        """Customer owns an item and wants matching recommendations."""
        sc = style_config()
        pairings = sc["colour_pairings"]
        aliases = sc["colour_aliases"]
        colour = aliases.get(owned_colour.lower(), owned_colour.lower())
        pair_data = pairings.get(colour, {})
        recommended = pair_data.get("pairs", ["white", "black", "grey"])
        explanation = pair_data.get("explanation", f"{colour} pairs well with neutrals")
        tip = pair_data.get("tip", "")

        search_query = f"{' '.join(recommended[:3])} {wanted_category}"
        if occasion:
            search_query += f" {occasion}"

        filters: dict = {"doc_type": "product", "in_stock": True}
        if budget:
            filters["max_price"] = budget

        chunks = await rag_client.retrieve(query=search_query, filters=filters)
        top_k = search_config()["per_tool"].get("outfit_pairing", {}).get("top_k", 5)
        chunks = _deduplicate_chunks(chunks, top_k)

        result = f"Style advice: {explanation}\n"
        if tip:
            result += f"Tip: {tip}\n"
        result += f"Recommended colours: {', '.join(recommended[:3])}\n\n"
        result += _format_chunks_for_agent(chunks)
        return result

    return outfit_pairing


def create_size_advice_tool(rag_client: RAGClient):
    @tool
    async def size_advice(
        brand: str = "",
        foot_type: str = "",
        current_size: str = "",
        category: str = "shoes",
    ) -> str:
        """Give sizing and fit advice."""
        sc = style_config()
        parts: list[str] = []
        if brand:
            note = sc["brand_size_notes"].get(brand.lower())
            if note:
                parts.append(note)
        if foot_type:
            advice = sc["foot_type_advice"].get(foot_type.lower())
            if advice:
                parts.append(advice)
        if current_size:
            parts.append(f"Customer's current size: {current_size}")

        advice_text = " ".join(parts) if parts else "General advice: check the brand's size chart."

        chunks = []
        if brand:
            top_k = search_config()["per_tool"]["size_advice"]["top_k"]
            chunks = await rag_client.retrieve(
                query=f"{brand} {category}",
                filters={"brand": brand, "doc_type": "product"},
                top_k=top_k,
            )
            chunks = _deduplicate_chunks(chunks, top_k)

        result = advice_text
        if chunks:
            result += f"\n\nRelevant products:\n{_format_chunks_for_agent(chunks)}"
        return result

    return size_advice
