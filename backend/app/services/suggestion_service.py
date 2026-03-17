"""
Suggestion service.

Generates contextual typing suggestions shown to the customer
as tappable chips after every bot response.

Design principles:
  - Zero LLM calls — pure rule-based logic (fast, free, deterministic)
  - Context-aware — suggestions change based on intent + what was shown
  - Max 4 chips — more than 4 overwhelms the UI
  - Short labels — under 35 chars so they fit on mobile without wrapping
  - Actionable — each chip should make the customer's next step obvious

Suggestion lifecycle:
  1. After greeting        → category starter chips
  2. After product results → refine chips (size, colour, compare)
  3. After order query     → follow-up chips (track, return, contact)
  4. After policy FAQ      → related policy chips
  5. After escalation      → contact chips
"""

from __future__ import annotations

from app.api.dto.suggestion_dto import SuggestionChip, SuggestionResponse
from app.api.dto.chat_dto import ProductCardDTO
from app.services.memory_service import SlotState
from app.core.logging import get_logger

logger = get_logger(__name__)


class SuggestionService:
    """
    Stateless — all state comes in through parameters.
    No DB, no HTTP, no LLM.
    """

    def generate(
        self,
        intent: str,
        slots: SlotState,
        cited_products: list[ProductCardDTO],
        blocked: bool,
        last_user_message: str = "",
    ) -> SuggestionResponse:
        """
        Generate suggestions based on what just happened in the conversation.
        Returns at most 4 chips.
        """
        if blocked:
            return SuggestionResponse(chips=[])

        chips: list[SuggestionChip] = []

        # Route to the right suggestion set based on intent
        if intent == "greeting":
            chips = self._greeting_chips()

        elif intent in ("product_search", "recommendation", "slot_filling"):
            chips = self._product_search_chips(slots, cited_products)

        elif intent == "outfit_pairing":
            chips = self._outfit_chips(slots, cited_products)

        elif intent == "comparison":
            chips = self._comparison_chips(cited_products)

        elif intent == "order_status":
            chips = self._order_chips()

        elif intent == "return_request":
            chips = self._return_chips()

        elif intent == "size_query":
            chips = self._size_chips(slots)

        elif intent == "price_query":
            chips = self._price_chips(slots)

        elif intent == "purchase_intent":
            chips = self._purchase_chips(cited_products)

        else:
            chips = self._fallback_chips(cited_products)

        # Cap at 4
        result = SuggestionResponse(chips=chips[:4])
        logger.debug(
            "suggestions.generated",
            intent=intent,
            count=len(result.chips),
        )
        return result

    # ─────────────────────────────────────────────────────────────────────────
    # Chip sets per intent
    # ─────────────────────────────────────────────────────────────────────────

    def _greeting_chips(self) -> list[SuggestionChip]:
        return [
            SuggestionChip(label="Browse shoes",    message="Show me shoes",                  icon="👟", chip_type="quick_reply"),
            SuggestionChip(label="Browse jackets",  message="Show me jackets",                icon="🧥", chip_type="quick_reply"),
            SuggestionChip(label="Track my order",  message="Where is my order?",             icon="📦", chip_type="navigate"),
            SuggestionChip(label="Gift ideas",      message="I need a gift for someone",      icon="🎁", chip_type="quick_reply"),
        ]

    def _product_search_chips(
        self,
        slots: SlotState,
        cited: list[ProductCardDTO],
    ) -> list[SuggestionChip]:
        chips: list[SuggestionChip] = []

        # If products were shown, offer refinement
        if cited:
            # Size refinement — if no size set yet
            if not slots.size:
                chips.append(SuggestionChip(
                    label="Find my size",
                    message="What size should I get?",
                    icon="📏", chip_type="refine",
                ))

            # Colour refinement
            chips.append(SuggestionChip(
                label="Show in black",
                message="Do you have these in black?",
                icon="⚫", chip_type="refine",
            ))

            # Compare
            if len(cited) >= 2:
                chips.append(SuggestionChip(
                    label="Compare top 2",
                    message=f"Compare {cited[0].title} vs {cited[1].title}",
                    icon="⚖️", chip_type="action",
                ))

            # Budget filter
            if not slots.budget:
                chips.append(SuggestionChip(
                    label="Under $100",
                    message="Show me options under $100",
                    icon="💰", chip_type="refine",
                ))
        else:
            # No products shown — suggest broader searches
            chips = [
                SuggestionChip(label="Show bestsellers",  message="What are your bestsellers?", icon="⭐", chip_type="quick_reply"),
                SuggestionChip(label="Browse all brands", message="Show me all brands you carry", icon="🏷️", chip_type="quick_reply"),
            ]

        return chips

    def _outfit_chips(
        self,
        slots: SlotState,
        cited: list[ProductCardDTO],
    ) -> list[SuggestionChip]:
        chips: list[SuggestionChip] = []
        wanted = slots.category or "item"

        if cited:
            chips.append(SuggestionChip(
                label="Find my size",
                message=f"What size {wanted} should I get?",
                icon="📏", chip_type="refine",
            ))
        chips.append(SuggestionChip(
            label="What shoes would match?",
            message="What shoes would go with this outfit?",
            icon="👟", chip_type="quick_reply",
        ))
        chips.append(SuggestionChip(
            label="Show me accessories",
            message="What accessories would complete this look?",
            icon="💼", chip_type="quick_reply",
        ))
        return chips

    def _comparison_chips(self, cited: list[ProductCardDTO]) -> list[SuggestionChip]:
        chips = [
            SuggestionChip(
                label="Which is more durable?",
                message="Which one is more durable long-term?",
                icon="🔧", chip_type="quick_reply",
            ),
            SuggestionChip(
                label="Which is better value?",
                message="Which gives better value for money?",
                icon="💰", chip_type="quick_reply",
            ),
        ]
        if cited:
            chips.append(SuggestionChip(
                label=f"Buy {cited[0].title.split()[0]}",
                message=f"I want to buy the {cited[0].title}",
                icon="🛒", chip_type="purchase_intent",
            ))
        return chips

    def _order_chips(self) -> list[SuggestionChip]:
        return [
            SuggestionChip(label="Return an item",     message="I want to return something",         icon="↩️", chip_type="quick_reply"),
            SuggestionChip(label="Change my address",  message="How do I change my delivery address?", icon="📍", chip_type="quick_reply"),
            SuggestionChip(label="Contact support",    message="I need to speak to someone",          icon="💬", chip_type="navigate"),
            SuggestionChip(label="Keep shopping",      message="Show me new arrivals",                icon="🛍️", chip_type="navigate"),
        ]

    def _return_chips(self) -> list[SuggestionChip]:
        return [
            SuggestionChip(label="Exchange for different size", message="I want to exchange for a different size", icon="📦", chip_type="quick_reply"),
            SuggestionChip(label="Refund to card",              message="How long does a refund take?",            icon="💳", chip_type="quick_reply"),
            SuggestionChip(label="Return policy details",       message="What is your full return policy?",        icon="📋", chip_type="quick_reply"),
        ]

    def _size_chips(self, slots: SlotState) -> list[SuggestionChip]:
        brand = slots.brand or "this brand"
        chips = [
            SuggestionChip(label=f"{brand} size guide", message=f"Show me the {brand} size guide",     icon="📏", chip_type="quick_reply"),
            SuggestionChip(label="I have wide feet",    message="I have wide feet, what should I get?", icon="👟", chip_type="quick_reply"),
            SuggestionChip(label="Between sizes",       message="I'm between sizes, which should I choose?", icon="🤔", chip_type="quick_reply"),
        ]
        return chips

    def _price_chips(self, slots: SlotState) -> list[SuggestionChip]:
        return [
            SuggestionChip(label="Under $50",    message="Show me options under $50",     icon="💰", chip_type="refine"),
            SuggestionChip(label="Under $100",   message="Show me options under $100",    icon="💰", chip_type="refine"),
            SuggestionChip(label="Any discounts?", message="Do you have any current discounts?", icon="🏷️", chip_type="quick_reply"),
        ]

    def _purchase_chips(self, cited: list[ProductCardDTO]) -> list[SuggestionChip]:
        chips: list[SuggestionChip] = []
        if cited:
            chips.append(SuggestionChip(
                label="What's the return policy?",
                message="What is your return policy if it doesn't fit?",
                icon="↩️", chip_type="quick_reply",
            ))
            chips.append(SuggestionChip(
                label="How long to deliver?",
                message="How long does delivery take?",
                icon="🚚", chip_type="quick_reply",
            ))
        return chips

    def _fallback_chips(self, cited: list[ProductCardDTO]) -> list[SuggestionChip]:
        chips = [
            SuggestionChip(label="Track my order",   message="Where is my order?",          icon="📦", chip_type="navigate"),
            SuggestionChip(label="Return something", message="I want to return an item",    icon="↩️", chip_type="quick_reply"),
        ]
        if cited:
            chips.insert(0, SuggestionChip(
                label="Tell me more",
                message=f"Tell me more about {cited[0].title}",
                icon="ℹ️", chip_type="quick_reply",
            ))
        return chips
