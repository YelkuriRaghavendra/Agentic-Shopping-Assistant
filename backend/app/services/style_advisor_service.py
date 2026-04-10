"""
Style advisor service.

Provides colour pairing knowledge and size guidance.
Pure business logic — no DB, no HTTP, no LLM calls.
"""

from dataclasses import dataclass

from app.config.loader import style_config

# ─────────────────────────────────────────────────────────────────────────────
# Colour pairing knowledge
# ─────────────────────────────────────────────────────────────────────────────


def _load_style_data():
    sc = style_config()
    return sc["colour_pairings"], sc["colour_aliases"], sc["brand_size_notes"], sc["foot_type_advice"]


_COLOUR_PAIRINGS, _COLOUR_ALIASES, _BRAND_SIZE_NOTES, _FOOT_TYPE_ADVICE = _load_style_data()


@dataclass
class OutfitRecommendation:
    owned_colour:        str
    wanted_category:     str
    recommended_colours: list[str]
    search_query:        str
    explanation:         str
    style_tip:           str


class StyleAdvisorService:

    def get_outfit_recommendation(
        self,
        owned_colour: str,
        owned_category: str,
        wanted_category: str,
    ) -> OutfitRecommendation:
        normalised = _COLOUR_ALIASES.get(owned_colour.lower(), owned_colour.lower())
        data = _COLOUR_PAIRINGS.get(normalised, {})
        pairs = [c for c in data.get("pairs_with", []) if c != "any colour"]
        notes = data.get("notes", {})
        avoid = data.get("avoid", [])

        if not pairs:
            pairs = ["white", "black", "grey", "navy", "beige"]

        top_n = style_config().get("top_color_pairs_count", 3)
        top = pairs[:top_n]
        avoid_str = f" Avoid {', '.join(avoid[:2])}." if avoid else ""
        explanation = (
            f"A {owned_colour} {owned_category} pairs best with "
            f"{', '.join(top[:-1])} or {top[-1]}.{avoid_str}"
        )
        top_notes = [notes[c] for c in top if notes.get(c)]
        style_tip = top_notes[0] if top_notes else (
            f"{top[0].title()} will complement your {owned_colour} {owned_category} perfectly."
        )

        return OutfitRecommendation(
            owned_colour=owned_colour,
            wanted_category=wanted_category,
            recommended_colours=pairs,
            search_query=" ".join(pairs[:4]) + f" {wanted_category}",
            explanation=explanation,
            style_tip=style_tip,
        )

    def get_size_advice(
        self,
        brand: str | None,
        foot_type: str | None,
        current_size: str | None,
    ) -> str:
        parts: list[str] = []
        if brand:
            note = _BRAND_SIZE_NOTES.get(brand.lower())
            if note:
                parts.append(note)
        if foot_type:
            advice = _FOOT_TYPE_ADVICE.get(foot_type.lower())
            if advice:
                parts.append(advice)
        if not parts:
            return (
                "I'd recommend going with your usual size and checking the "
                "product's size guide. If between sizes, generally size up for comfort."
            )
        return " ".join(parts)
