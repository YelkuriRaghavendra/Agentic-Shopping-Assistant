"""
Citation processing node.
Parses [P1], [P2] markers from agent response and builds product cards.
Reuses existing CitationService logic.
"""

from app.services.citation_service import CitationService
from app.core.logging import get_logger

logger = get_logger(__name__)

_citation_service = CitationService()


def citations_node(state: dict) -> dict:
    agent_response = state.get("agent_response", "")
    chunks = state.get("retrieved_chunks", [])

    if not agent_response or not chunks:
        # Don't overwrite cited_products if already populated by agent wrapper
        existing = state.get("cited_products", [])
        return {"cited_products": existing, "agent_response": agent_response}

    # Build citation map from chunks
    citation_map: dict[str, dict] = {}
    for i, chunk in enumerate(chunks):
        cid = f"P{i + 1}"
        if isinstance(chunk, dict):
            meta = chunk.get("metadata", chunk)
            doc_type = chunk.get("document_type", "PRODUCT")
            product_id = chunk.get("product_id", "")
        else:
            meta = chunk.metadata
            doc_type = getattr(chunk, "document_type", "PRODUCT")
            product_id = chunk.product_id

        if str(doc_type).upper() == "PRODUCT":
            citation_map[cid] = {
                "citation_id": cid,
                "product_id": product_id,
                "product_name": meta.get("product_name"),
                "price": meta.get("price"),
                "image_url": meta.get("image_url"),
                "rating": meta.get("rating"),
                "url": meta.get("product_url", meta.get("url", "")),
            }

    answer, answer_html, cited_products = _citation_service.process(agent_response, citation_map)

    return {
        "agent_response": answer,
        "cited_products": [p.model_dump() for p in cited_products],
    }
