"""
Slot service — pure functions for preference extraction and management.

Extracted from ChatService to enable independent testing and reuse
across both the LangGraph pipeline and any future endpoints.

No class, no self, no DB calls — pure data transformation.
"""

from __future__ import annotations

import re

from app.config.loader import business_rules
from app.services.memory_service import SlotState
from app.core.logging import get_logger

logger = get_logger(__name__)


def extract_slots(message: str, existing: SlotState) -> SlotState:
    """
    Extract structured slot data from a user message.
    All keyword lists and thresholds come from config/business_rules.json.
    Enriches the LLM's search query — doesn't gate the conversation.
    """
    msg = message.lower()
    br = business_rules()
    slot_cfg = br["slot_extraction"]
    budget_cfg = br["budget"]

    # Reset signal
    reset_phrases = "|".join(re.escape(p) for p in slot_cfg["reset_phrases"])
    if re.search(rf"\b({reset_phrases})\b", msg, re.I):
        return SlotState()

    slots = SlotState(
        category=existing.category,
        use_case=existing.use_case,
        brand=existing.brand,
        budget=existing.budget,
        size=existing.size,
        color=existing.color,
    )

    # Category
    for cat, keywords in slot_cfg["categories"].items():
        if any(kw in msg for kw in keywords):
            slots.category = cat
            break

    # Use case
    for use, keywords in slot_cfg["use_cases"].items():
        if any(re.search(r"\b" + k + r"\b", msg) for k in keywords):
            slots.use_case = use
            break

    # Brand
    for brand in slot_cfg["brands"]:
        if brand in msg:
            slots.brand = brand.title()
            break
    no_brand_pattern = "|".join(re.escape(p) for p in slot_cfg["no_brand_phrases"])
    if re.search(rf"\b({no_brand_pattern})\b", msg, re.I):
        slots.brand = "any"

    # Budget — explicit number first, then keyword fallback
    budget_match = re.search(
        r"(?:under|below|less than|up to|max|around|about)\s*\$?\s*(\d+)", msg, re.I
    )
    if budget_match:
        slots.budget = float(budget_match.group(1))
    elif any(kw in msg for kw in slot_cfg["budget_keywords"]["cheap"]):
        slots.budget = float(budget_cfg["cheap_keyword_default"])
    elif any(kw in msg for kw in slot_cfg["budget_keywords"]["no_limit"]):
        slots.budget = float(budget_cfg["unlimited_sentinel"])

    # Size
    size_match = re.search(
        r"\b(?:size\s*)?([4-9]|1[0-5])(?:\.5)?\b|\b(xs|s|m|l|xl|xxl)\b", msg, re.I
    )
    if size_match:
        raw = (size_match.group(1) or size_match.group(2) or "").strip()
        size_map = {"xs": "XS", "s": "S", "m": "M", "l": "L", "xl": "XL", "xxl": "XXL"}
        slots.size = size_map.get(raw.lower(), raw)

    # Color
    colors = slot_cfg["colors"]
    color_pattern = "|".join(colors)
    color_match = re.search(rf"\b({color_pattern})\b", msg, re.I)
    if color_match:
        slots.color = color_match.group(0).lower()

    return slots


def build_slot_status(slots: SlotState) -> str:
    """
    Build a human-readable summary of collected slots for the LLM.
    Tells the LLM what's been gathered and whether it's enough to search.
    """
    br = business_rules()
    unlimited = br["budget"]["unlimited_sentinel"]

    cat = slots.category or slots.use_case or "not yet asked"
    brand = (
        slots.brand
        if slots.brand and slots.brand.lower() != "any"
        else ("no preference" if slots.brand and slots.brand.lower() == "any" else "not yet asked")
    )
    budget = (
        f"under ${int(slots.budget)}"
        if slots.budget and slots.budget < unlimited
        else ("no limit" if slots.budget else "not yet asked")
    )
    color = slots.color or "not yet asked"
    size = slots.size or "not yet asked"

    has_type = bool(slots.category or slots.use_case)
    has_brand = bool(slots.brand)
    has_budget = bool(slots.budget)
    has_size = bool(slots.size)
    has_color = bool(slots.color)
    filled_count = sum([has_brand, has_budget, has_size, has_color])
    ready = has_type and filled_count >= 1

    lines = [
        "CUSTOMER PREFERENCES COLLECTED:",
        f"- Type: {cat}",
        f"- Brand: {brand}",
        f"- Budget: {budget}",
        f"- Color: {color}",
        f"- Size: {size}",
    ]

    if ready:
        reasons = []
        if has_type:
            reasons.append("type")
        if has_brand:
            reasons.append("brand")
        if has_budget:
            reasons.append("budget")
        if has_size:
            reasons.append("size")
        if has_color:
            reasons.append("color")
        lines.append(
            f"→ READY TO SEARCH. You have {' + '.join(reasons)}. "
            "Call search_products NOW. Do NOT ask any more questions."
        )
    elif not has_type:
        lines.append("→ Not enough info yet. Ask what TYPE of shoes they want.")
    else:
        lines.append(
            "→ Have type only. Ask about their BRAND preference or BUDGET range next. "
            "Do NOT search yet."
        )

    return "\n".join(lines)


def enrich_tool_args(
    tool_name: str,
    args: dict,
    slots: SlotState,
    extra_filters: dict | None = None,
) -> dict:
    """
    Inject collected slots into tool args before execution.
    Makes RAG searches precise — brand, price, size as real filters.
    Does NOT override what the LLM already extracted.
    """
    if tool_name not in ("search_products", "outfit_pairing", "gift_finder"):
        return args

    unlimited = business_rules()["budget"]["unlimited_sentinel"]

    enriched = dict(args)
    if slots.brand and slots.brand.lower() not in ("any", "no preference"):
        enriched.setdefault("brand", slots.brand)
    if slots.budget and slots.budget < unlimited:
        enriched.setdefault("max_price", slots.budget)
    if slots.size:
        enriched.setdefault("size", slots.size)
    if slots.use_case:
        enriched.setdefault("use_case", slots.use_case)
    if slots.category:
        enriched.setdefault("category", slots.category)

    # Build richer query if current query is vague (1-2 words)
    current_query = enriched.get("query", "")
    if len(current_query.split()) <= 2 and slots.category:
        enriched["query"] = slots.to_search_query()

    if extra_filters:
        enriched["_extra_filters"] = extra_filters

    return enriched


def build_suggestions(llm_suggestions: list | None) -> list[dict]:
    """Convert LLM-generated SuggestionItem objects to frontend-ready dicts."""
    if not llm_suggestions:
        return []
    return [
        {"label": s.label[:40], "message": s.message, "chip_type": "quick_reply"}
        for s in llm_suggestions
        if s.label
    ][:4]
