"""
Prompt builder service.

Assembles the full LLM prompt from all available context:
  - Base system rules
  - Customer profile (Layer 3 memory)
  - Products shown earlier in session (Layer 2 memory)
  - Retrieved products/docs (current turn)
  - Conversation history (recent turns + summary)
  - Slot summary (what we know customer wants)

Returns: (system_prompt, citation_map)
  citation_map maps "P1" → product metadata so [P1] can be
  replaced with real links after the LLM responds.
"""

from app.clients.rag_client import RetrievedChunk
from app.services.memory_service import SlotState, ConversationHistory
from app.config.loader import prompts
from app.core.logging import get_logger

logger = get_logger(__name__)

_BASE_SYSTEM_PROMPT = prompts()["system"]["base"]


class PromptBuilderService:

    def build(
        self,
        user_message: str,
        history: ConversationHistory,
        retrieved_chunks: list[RetrievedChunk],
        slots: SlotState | None = None,
        customer_profile: dict | None = None,
        shown_products: list[dict] | None = None,
        tool_context: str | None = None,
    ) -> tuple[str, str, dict[str, dict]]:
        """
        Build the full system prompt and citation map.

        Returns:
          system_prompt  — everything the LLM needs to know
          user_prompt    — the customer's message (unchanged)
          citation_map   — {"P1": {title, url, price, ...}}
        """
        citation_map: dict[str, dict] = {}
        context_blocks: list[str] = []

        # ── Build citation map from retrieved chunks ─────────────────────
        for i, chunk in enumerate(retrieved_chunks):
            cid = f"P{i + 1}"
            meta = chunk.metadata

            if chunk.document_type.upper() == "PRODUCT":
                citation_map[cid] = {
                    "citation_id":  cid,
                    "product_id":   chunk.product_id,
                    "product_name": meta.get("product_name"),
                    "url":          meta.get("product_url", meta.get("url", "")),
                    "price":        meta.get("price"),
                    "currency":     meta.get("currency"),
                    "image_url":    meta.get("image_url"),
                    "sku":          meta.get("sku"),
                    "rating":       meta.get("rating"),
                    "similarity":   chunk.similarity,
                }
                price_str  = f" | ${meta['price']}" if meta.get("price") else ""
                rating_str = f" | ⭐ {meta['rating']}" if meta.get("rating") else ""
                stock_str  = "In stock" if meta.get("in_stock", True) else "Out of stock"
                context_blocks.append(
                    f"[{cid}] {chunk.product_id}{price_str}{rating_str} | {stock_str}\n"
                    f"{chunk.content}"
                )
            else:
                # Policy / FAQ — no citation, just reference
                context_blocks.append(
                    f"[Reference] {chunk.product_id}\n{chunk.content}"
                )

        # ── Assemble system prompt sections ──────────────────────────────
        sections: list[str] = [_BASE_SYSTEM_PROMPT]

        # Layer 3: customer profile
        if customer_profile:
            profile_summary = self._profile_summary(customer_profile)
            if profile_summary:
                sections.append(
                    "RETURNING CUSTOMER PROFILE:\n"
                    + profile_summary
                    + "\nDo NOT ask for information you already have."
                )

        # Layer 3: people the customer has mentioned across sessions
        # This is the cross-session memory — "my friend who runs" remembered next session
        if customer_profile:
            known_people = customer_profile.get("known_people", [])
            if known_people:
                from app.services.memory_service import PersonNote
                people_lines = [
                    f"  - {PersonNote.from_dict(p).summary()}"
                    for p in known_people
                ]
                sections.append(
                    "PEOPLE THIS CUSTOMER HAS MENTIONED IN PREVIOUS CONVERSATIONS:\n"
                    + "\n".join(people_lines)
                    + "\n\nCRITICAL: If the customer refers to 'my friend', 'my dad', etc., "
                    "check this list first. You already know who they are — do NOT ask again. "
                    "Use what you know to make a relevant recommendation immediately."
                )

        # Layer 2: products shown earlier this session
        if shown_products:
            lines = [
                f"  • {p['productName']}"
                + (f" — ${p['price']}" if p.get("price") else "")
                + (f" (ID: {p['productId']})" if p.get("productId") else "")
                for p in shown_products[-8:]
            ]
            sections.append(
                "PRODUCTS SHOWN EARLIER IN THIS CONVERSATION:\n"
                + "\n".join(lines)
                + "\nWhen customer says 'those ones', 'that one', 'the ones you showed' "
                "— refer to these specifically."
            )

        # Current retrieved context
        if context_blocks:
            sections.append(
                "CONTEXT (use this to answer, cite with [P1][P2]):\n"
                + "\n\n---\n\n".join(context_blocks)
            )
        else:
            sections.append(
                "CONTEXT: No specific products found for this query. "
                "Be honest — tell the customer and offer to help with something else."
            )

        # Tool result summary (if provided)
        if tool_context:
            sections.append(f"TOOL RESULT:\n{tool_context}")

        # Conversation history
        history_text = self._format_history(history)
        if history_text:
            sections.append(f"CONVERSATION SO FAR:\n{history_text}")

        # Slot summary
        if slots:
            summary = slots.summary()
            if summary:
                sections.append(
                    f"CUSTOMER IS LOOKING FOR: {summary}\n"
                    "Personalise your response accordingly."
                )

        system_prompt = "\n\n".join(sections)

        logger.debug(
            "prompt.built",
            chunks=len(context_blocks),
            citations=len(citation_map),
            has_profile=bool(customer_profile),
            has_shown=bool(shown_products),
        )

        return system_prompt, user_message, citation_map

    def _format_history(self, history: ConversationHistory) -> str:
        parts: list[str] = []
        if history.summary:
            parts.append(
                f"Earlier in this conversation:\n{history.summary}"
            )
        for turn in history.recent_turns:
            label = "Customer" if turn["role"] == "user" else "You"
            parts.append(f"{label}: {turn['content']}")
        return "\n".join(parts)

    def _profile_summary(self, profile: dict) -> str:
        from app.config.loader import business_rules
        tiers = business_rules()["budget"]["tiers"]
        parts: list[str] = []
        brands = profile.get("preferred_brands", [])
        if brands:
            parts.append(f"Preferred brands: {', '.join(brands[:3])}")
        sizes = profile.get("usual_sizes", {})
        if sizes:
            parts.append("Usual sizes: " + ", ".join(f"{k}: {v}" for k, v in sizes.items()))
        sensitivity = profile.get("price_sensitivity")
        if sensitivity in tiers:
            parts.append(f"Price range: {tiers[sensitivity]}")
        if profile.get("favourite_category"):
            parts.append(f"Usually shops for: {profile['favourite_category']}")
        sessions = profile.get("total_sessions", 0)
        if sessions > 1:
            parts.append(f"Returning customer ({sessions} sessions)")
        return "\n".join(parts)
