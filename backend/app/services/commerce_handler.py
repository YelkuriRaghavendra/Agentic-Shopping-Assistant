"""
Commerce handler — keyword-based commerce intent classification and dispatch.

Extracted from ChatService for reuse in the LangGraph pipeline.
Pure functions + data constants. No class, no self.
"""

from __future__ import annotations

import re
from app.core.logging import get_logger

logger = get_logger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────────────────────────────────────

COMMERCE_INTENT_MAP: list[tuple[list[str], str]] = [
    (["checkout", "check out", "place order", "place my order", "buy now",
      "proceed to checkout", "proceed to payment", "proceed with payment",
      "proceed with purchase", "place the order",
      "purchase this", "purchase it", "buy this", "buy it",
      "complete my purchase", "complete the purchase", "complete purchase",
      "confirm my purchase", "confirm purchase", "confirm the purchase",
      "confirm my order", "confirm order",
      "finalize", "finalise", "make the purchase",
      "pay for this", "payment for the", "i want to pay for"], "checkout_initiate"),
    (["add to cart", "add to my cart", "put in cart", "put it in", "add it", "add this",
      "i want to add", "add the"], "add_to_cart"),
    (["remove from cart", "take out of cart", "delete from cart", "remove it", "take it out"], "remove_from_cart"),
    (["view cart", "show cart", "what's in my cart", "my cart", "see my cart", "show my cart"], "view_cart"),
    (["order status", "where is my order", "track my order", "order #", "order number",
      "status of my order", "where's my order"], "order_status"),
    (["order history", "my orders", "past orders", "previous orders", "all orders",
      "show my orders", "show orders", "see my orders"], "order_history"),
    (["cancel order", "cancel my order", "cancel purchase", "cancel the order"], "cancel_order"),
]

REQUIRED_SLOTS: dict[str, list[str]] = {
    "add_to_cart":       ["product_id", "quantity"],
    "remove_from_cart":  ["product_id"],
    "view_cart":         [],
    "checkout_initiate": [],
    "order_status":      ["order_id"],
    "order_history":     [],
    "cancel_order":      ["order_id"],
}

SLOT_PROMPTS: dict[str, str] = {
    "product_id": "Which product would you like? Could you describe it or give me the product name?",
    "quantity":   "How many would you like to add?",
    "order_id":   "Could you share your order number? You can find it in your confirmation email.",
    "line_items": "Your cart appears to be empty. Would you like to add some items first?",
}

PURCHASE_INTENT_PHRASES = [
    "i want to buy", "i'd like to buy", "i would like to buy",
    "i want to purchase", "i'd like to purchase", "i would like to purchase",
    "i want to order", "i'd like to order", "i would like to order",
]

BROWSE_CATEGORY_WORDS = {
    "shoes", "shoe", "sneakers", "boots", "sandals", "slippers",
    "shirts", "shirt", "pants", "jeans", "jacket", "jackets",
    "clothes", "clothing", "apparel", "dress", "dresses",
    "something", "anything", "some", "a few", "options",
}


# ─────────────────────────────────────────────────────────────────────────────
# Functions
# ─────────────────────────────────────────────────────────────────────────────

def is_specific_product_reference(msg: str, phrase: str) -> bool:
    """Check if text after the purchase phrase references a specific product."""
    after = msg[msg.index(phrase) + len(phrase) :].strip()
    if not after:
        return False
    if after.startswith("the ") or after.startswith("this ") or after.startswith("that "):
        return True
    first_word = after.split()[0].rstrip(".,!?") if after.split() else ""
    if first_word in BROWSE_CATEGORY_WORDS:
        return False
    if len(after.split()) >= 3:
        return True
    return False


def classify_commerce_intent(message: str) -> str | None:
    """
    Keyword-based commerce intent classifier.
    Returns a commerce intent name or None if no match.
    Zero LLM cost.
    """
    msg = message.lower()

    for keywords, intent in COMMERCE_INTENT_MAP:
        matched = [kw for kw in keywords if kw in msg]
        if matched:
            logger.info(
                "commerce_intent.classified",
                intent=intent,
                matched_keywords=matched,
            )
            return intent

    for phrase in PURCHASE_INTENT_PHRASES:
        if phrase in msg and is_specific_product_reference(msg, phrase):
            logger.info(
                "commerce_intent.classified",
                intent="checkout_initiate",
                reason="specific_product_reference",
            )
            return "checkout_initiate"

    return None
