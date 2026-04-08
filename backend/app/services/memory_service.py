"""
Memory service.

Layer 2 — Session memory   (sessions.context JSONB)
Layer 3 — Customer memory  (customers.profile JSONB)

Cross-session people context:
  "my friend who runs" is extracted, stored in customers.profile["known_people"],
  and injected into every future prompt so the agent remembers across sessions.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, UTC
from typing import Any

from app.api.dto.chat_dto import ProductCardDTO
from app.clients.redis_client import cache_get, cache_set, cache_delete
from app.config.loader import business_rules
from app.core.config import get_settings
from app.db.repositories import SessionRepository, CustomerRepository
from app.db.models.session import Session
from app.core.logging import get_logger

logger = get_logger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# SlotState
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class SlotState:
    """Shopping criteria collected from conversation. Persists across turns."""
    category:  str | None = None
    use_case:  str | None = None
    brand:     str | None = None
    budget:    float | None = None
    size:      str | None = None
    color:     str | None = None

    def to_dict(self) -> dict:
        return {k: v for k, v in self.__dict__.items() if v is not None}

    @classmethod
    def from_dict(cls, d: dict) -> "SlotState":
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})

    def to_search_query(self) -> str:
        br = business_rules()
        unlimited = br["budget"]["unlimited_sentinel"]
        parts = [
            self.use_case or "",
            self.category or "",
            self.brand if self.brand and self.brand.lower() != "any" else "",
            self.color or "",
            f"size {self.size}" if self.size else "",
            f"under ${int(self.budget)}" if self.budget and self.budget < unlimited else "",
        ]
        return " ".join(p for p in parts if p).strip() or "products"

    def to_rag_filters(self, extra: dict | None = None) -> dict:
        br = business_rules()
        unlimited = br["budget"]["unlimited_sentinel"]
        filters: dict[str, Any] = {"in_stock": True}
        if self.brand and self.brand.lower() not in ("any", "no preference"):
            filters["brand"] = self.brand
        if self.budget and self.budget < unlimited:
            filters["max_price"] = self.budget
        if self.use_case:
            filters["category"] = self.use_case
        if extra:
            filters.update(extra)
        return filters

    def summary(self) -> str:
        br = business_rules()
        unlimited = br["budget"]["unlimited_sentinel"]
        parts: list[str] = []
        if self.category:
            parts.append(self.category)
        if self.use_case:
            parts.append(f"for {self.use_case}")
        if self.brand and self.brand.lower() not in ("any",):
            parts.append(f"from {self.brand}")
        if self.size:
            parts.append(f"size {self.size}")
        if self.budget and self.budget < unlimited:
            parts.append(f"under ${int(self.budget)}")
        if self.color:
            parts.append(f"in {self.color}")
        return ", ".join(parts)


# ─────────────────────────────────────────────────────────────────────────────
# PersonNote
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class PersonNote:
    """
    A person the customer has mentioned.
    Stored in customers.profile["known_people"] — survives session ends.
    This is what makes "my friend who runs" persist across sessions.
    """
    name:      str | None = None
    relation:  str | None = None
    interests: list[str] = field(default_factory=list)
    size:      str | None = None
    budget:    str | None = None
    extra:     str | None = None

    def to_dict(self) -> dict:
        d = {k: v for k, v in self.__dict__.items() if v is not None}
        if not self.interests:
            d.pop("interests", None)
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "PersonNote":
        return cls(
            name=d.get("name"),
            relation=d.get("relation"),
            interests=d.get("interests", []),
            size=d.get("size"),
            budget=d.get("budget"),
            extra=d.get("extra"),
        )

    def summary(self) -> str:
        label = self.name or self.relation or "person"
        parts: list[str] = []
        if self.interests:
            parts.append(f"likes {', '.join(self.interests)}")
        if self.size:
            parts.append(f"size {self.size}")
        if self.budget:
            parts.append(f"{self.budget} budget")
        if self.extra:
            parts.append(self.extra)
        return f"{label}: {'; '.join(parts)}" if parts else label


@dataclass
class ConversationHistory:
    recent_turns: list[dict] = field(default_factory=list)
    summary:      str | None = None


# ─────────────────────────────────────────────────────────────────────────────
# MemoryService
# ─────────────────────────────────────────────────────────────────────────────

class MemoryService:

    def __init__(self, session_repo: SessionRepository, customer_repo: CustomerRepository):
        self._session_repo  = session_repo
        self._customer_repo = customer_repo

    # ── Layer 2 ───────────────────────────────────────────────────────────

    def load_slots(self, session: Session) -> SlotState:
        return SlotState.from_dict(session.context.get("slots", {}))

    def load_shown_products(self, session: Session) -> list[dict]:
        return session.context.get("shown_products", [])

    def load_summary(self, session: Session) -> str | None:
        return session.context.get("summary")

    async def persist_session_memory(
        self,
        session: Session,
        slots: SlotState,
        cited_products: list[ProductCardDTO],
        intent: str,
    ) -> None:
        br = business_rules()
        max_shown = br["session"]["max_shown_products"]
        ctx = dict(session.context)
        ctx["slots"]       = slots.to_dict()
        ctx["last_intent"] = intent

        shown: list[dict] = ctx.get("shown_products", [])
        existing_ids = {p.get("productId") for p in shown if p.get("productId")}
        for product in cited_products:
            if product.productId in existing_ids:
                continue
            shown.append({
                "productId":     product.productId,
                "productName":   product.productName,
                "price":         product.price,
                "productImageUrl": product.productImageUrl,
                "rating":        product.rating,
                "shown_at_turn": session.message_count,
            })
            existing_ids.add(product.productId)

        ctx["shown_products"] = shown[-max_shown:]
        await self._session_repo.update_context(session, ctx)

    async def persist_summary(self, session_id: uuid.UUID, summary: str) -> None:
        session = await self._session_repo.get_by_id(session_id)
        if not session:
            return
        ctx = dict(session.context)
        ctx["summary"] = summary
        await self._session_repo.update_context(session, ctx)

    # ── Layer 3 ───────────────────────────────────────────────────────────

    async def load_customer_profile(self, customer_id: uuid.UUID | None) -> dict:
        if not customer_id:
            return {}

        # Check Redis cache first
        cache_key = f"profile:{customer_id}"
        cached = await cache_get(cache_key)
        if cached is not None:
            return cached

        customer = await self._customer_repo.get_by_id(customer_id)
        profile = customer.profile if customer else {}

        # Cache for fast subsequent lookups
        if profile:
            settings = get_settings()
            await cache_set(cache_key, profile, ttl=settings.CACHE_PROFILE_TTL)

        return profile

    def prefill_slots_from_profile(self, slots: SlotState, profile: dict) -> SlotState:
        """Pre-fill slots for returning customers."""
        sizes  = profile.get("usual_sizes", {})
        brands = profile.get("preferred_brands", [])
        if not slots.size and sizes:
            # Try category-specific size first, then use_case, then fallback to "shoes"
            size_key = slots.category or slots.use_case or "shoes"
            slots.size = sizes.get(size_key) or sizes.get("shoes") or next(iter(sizes.values()), None)
        if not slots.brand and brands:
            slots.brand = brands[0]
        return slots

    async def update_customer_profile(
        self,
        customer_id: uuid.UUID,
        slots: SlotState,
        cited_products: list[ProductCardDTO],
        intent: str,
        people: list[PersonNote] | None = None,
    ) -> None:
        br = business_rules()
        budget_cfg = br["budget"]
        max_brands = br["session"]["max_profile_brands"]
        max_seen   = br["session"]["max_profile_products_seen"]

        customer = await self._customer_repo.get_by_id(customer_id)
        if not customer:
            return
        profile = dict(customer.profile)

        if slots.brand and slots.brand.lower() not in ("any", "no preference"):
            brands: list[str] = list(profile.get("preferred_brands", []))
            b = slots.brand.title()
            if b in brands:
                brands.remove(b)
            brands.insert(0, b)
            profile["preferred_brands"] = brands[:max_brands]

        if slots.size:
            size_key = slots.category or slots.use_case or "shoes"
            sizes = dict(profile.get("usual_sizes", {}))
            sizes[size_key] = slots.size
            profile["usual_sizes"] = sizes

        if slots.budget and slots.budget < budget_cfg["unlimited_sentinel"]:
            if slots.budget <= budget_cfg["budget_tier_max"]:
                profile["price_sensitivity"] = "budget"
            elif slots.budget <= budget_cfg["mid_tier_max"]:
                profile["price_sensitivity"] = "mid"
            else:
                profile["price_sensitivity"] = "premium"

        if slots.use_case:
            profile["favourite_category"] = slots.use_case

        if cited_products and intent in ("product_search", "outfit_pairing", "gift_finder"):
            seen: list[dict] = list(profile.get("products_seen", []))
            seen_ids = {p.get("productId") for p in seen}
            today = datetime.now(UTC).date().isoformat()
            for p in cited_products:
                if p.productId not in seen_ids:
                    seen.append({"productId": p.productId, "productName": p.productName, "date": today})
                    seen_ids.add(p.productId)
            profile["products_seen"] = seen[-max_seen:]

        # Persist people mentioned (Bug 1 fix: cross-session context)
        if people:
            existing: list[dict] = list(profile.get("known_people", []))
            existing_relations = {p.get("relation") for p in existing}
            for person in people:
                if not person.relation:
                    continue
                if person.relation not in existing_relations:
                    existing.append(person.to_dict())
                    existing_relations.add(person.relation)
                else:
                    for i, p in enumerate(existing):
                        if p.get("relation") == person.relation:
                            merged = {**p, **person.to_dict()}
                            merged["interests"] = list(
                                set(p.get("interests", []) + person.interests)
                            )
                            existing[i] = merged
                            break
            profile["known_people"] = existing[-10:]

        profile["interaction_count"] = profile.get("interaction_count", 0) + 1
        profile["total_sessions"]    = profile.get("total_sessions", 0) + 1
        profile["last_seen"]         = datetime.now(UTC).isoformat()
        await self._customer_repo.update_profile(customer_id, profile)

        # Invalidate cached profile so next load gets fresh data
        await cache_delete(f"profile:{customer_id}")

    # ── People context (Bug 1 fix) ────────────────────────────────────────

    def extract_people_from_message(self, message: str) -> list[PersonNote]:
        """
        Extract people mentions from a message.
        "my friend who runs" → PersonNote(relation="friend", interests=["running"])
        """
        import re
        br = business_rules()
        relation_cfg = br["people_context"]["relations"]

        msg = message.lower()
        found_relation: str | None = None
        for relation, keywords in relation_cfg.items():
            if any(kw in msg for kw in keywords):
                found_relation = relation
                break

        if not found_relation:
            return []

        name_match = re.search(
            r'(?:my\s+\w+\s+|for\s+my\s+\w+\s+)([A-Z][a-z]+)', message
        )
        name = name_match.group(1) if name_match else None

        interests: list[str] = []
        # Use prefix patterns (r"\brun") to match conjugations:
        # "run", "runs", "running", "runner" all match r"\brun"
        interest_map = {
            "running": [r"\brun", r"\bjog", r"\bmarathon"],
            "gym":     [r"\bgym\b", r"\bworkout", r"\bfitness", r"\btraining"],
            "hiking":  [r"\bhik", r"\btrail", r"\boutdoor", r"\btrek"],
            "casual":  [r"\bcasual", r"\bstreetwear", r"\beveryday"],
            "sport":   [r"\bsport", r"\bathlet", r"\bactive"],
            "cycling": [r"\bcycl", r"\bbike\b", r"\bbicycle"],
        }
        for interest, patterns in interest_map.items():
            if any(re.search(p, msg) for p in patterns):
                interests.append(interest)

        brands = br["slot_extraction"]["brands"]
        for brand in brands:
            if brand in msg:
                interests.append(brand.title())

        return [PersonNote(
            name=name, relation=found_relation, interests=interests,
            extra=message[:120] if len(message) > 20 else None,
        )]

    def load_known_people(self, profile: dict) -> list[PersonNote]:
        return [PersonNote.from_dict(p) for p in profile.get("known_people", [])]

    def build_people_context(self, profile: dict) -> str:
        """
        Inject cross-session people context into the LLM prompt.

        If in session 1 the customer said "my friend who runs", this injects
        that context into session 2 so the agent already knows — customer
        never needs to repeat themselves.
        """
        people = self.load_known_people(profile)
        if not people:
            return ""
        lines = [f"  - {p.summary()}" for p in people]
        return (
            "PEOPLE THIS CUSTOMER HAS MENTIONED IN PREVIOUS CONVERSATIONS:\n"
            + "\n".join(lines)
            + "\nUse this context. Do not ask the customer to repeat what they already said."
        )

    def build_profile_context(self, profile: dict) -> str:
        br = business_rules()
        tiers = br["budget"]["tiers"]
        parts: list[str] = []
        if brands := profile.get("preferred_brands", []):
            parts.append(f"Preferred brands: {', '.join(brands[:3])}")
        if sizes := profile.get("usual_sizes", {}):
            parts.append("Usual sizes: " + ", ".join(f"{k}: {v}" for k, v in sizes.items()))
        if (s := profile.get("price_sensitivity")) and s in tiers:
            parts.append(f"Price range: {tiers[s]}")
        if cat := profile.get("favourite_category"):
            parts.append(f"Usually shops for: {cat}")
        if (n := profile.get("total_sessions", 0)) > 1:
            parts.append(f"Returning customer ({n} sessions)")
        return "\n".join(parts)
