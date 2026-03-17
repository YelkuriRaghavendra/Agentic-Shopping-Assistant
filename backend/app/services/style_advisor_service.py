"""
Style advisor service.

Provides colour pairing knowledge and size guidance.
Pure business logic — no DB, no HTTP, no LLM calls.
"""

from dataclasses import dataclass

# ─────────────────────────────────────────────────────────────────────────────
# Colour pairing knowledge
# ─────────────────────────────────────────────────────────────────────────────

_COLOUR_PAIRINGS: dict[str, dict] = {
    "blue":   {"pairs_with": ["navy", "white", "grey", "beige", "camel", "black", "khaki", "olive"],   "avoid": ["bright blue", "green", "purple", "brown"],   "notes": {"navy": "tonal and sophisticated", "white": "classic clean contrast", "grey": "safe and versatile", "beige": "warm casual contrast"}},
    "white":  {"pairs_with": ["navy", "black", "grey", "beige", "camel", "olive", "red"],              "avoid": ["cream", "off-white"],                         "notes": {}},
    "black":  {"pairs_with": ["white", "grey", "beige", "camel", "red", "navy", "olive"],              "avoid": ["dark navy", "dark brown"],                    "notes": {"white": "classic high contrast", "camel": "sophisticated warm contrast"}},
    "grey":   {"pairs_with": ["white", "black", "navy", "camel", "red"],                               "avoid": [],                                             "notes": {}},
    "red":    {"pairs_with": ["white", "black", "navy", "grey", "beige"],                              "avoid": ["orange", "pink", "bright green", "purple"],   "notes": {"white": "bold and classic", "navy": "rich and sophisticated"}},
    "green":  {"pairs_with": ["white", "beige", "camel", "brown", "navy", "grey"],                    "avoid": ["red", "blue", "purple"],                      "notes": {}},
    "yellow": {"pairs_with": ["white", "grey", "navy", "black"],                                       "avoid": ["orange", "red", "green"],                     "notes": {}},
    "beige":  {"pairs_with": ["white", "navy", "black", "brown", "camel", "olive"],                   "avoid": ["cream", "light yellow"],                      "notes": {}},
    "navy":   {"pairs_with": ["white", "light blue", "beige", "grey", "camel", "red"],                "avoid": ["black"],                                      "notes": {"white": "classic nautical"}},
    "pink":   {"pairs_with": ["white", "grey", "navy", "black", "beige"],                             "avoid": ["red", "orange", "bright purple"],             "notes": {}},
    "brown":  {"pairs_with": ["beige", "white", "camel", "olive", "navy"],                            "avoid": ["black", "grey"],                              "notes": {}},
}

_COLOUR_ALIASES: dict[str, str] = {
    "tan": "beige", "khaki": "beige", "cream": "beige",
    "off-white": "white", "ivory": "white",
    "charcoal": "grey", "silver": "grey",
    "denim": "blue", "royal": "blue", "cobalt": "blue", "sky": "blue",
    "maroon": "red", "burgundy": "red", "wine": "red",
    "teal": "green", "olive": "green", "emerald": "green",
    "coral": "orange", "gold": "yellow", "mustard": "yellow",
    "purple": "pink", "violet": "pink", "lilac": "pink",
}

# ─────────────────────────────────────────────────────────────────────────────
# Size knowledge
# ─────────────────────────────────────────────────────────────────────────────

_BRAND_SIZE_NOTES: dict[str, str] = {
    "nike":         "Nike runs true to size. Wide feet should go half a size up.",
    "adidas":       "Adidas runs slightly narrow. Wide feet should size up half a size.",
    "new balance":  "New Balance offers wide widths (2E, 4E). True to size in standard.",
    "asics":        "Asics runs true to size. Good arch support for overpronation.",
    "brooks":       "Brooks runs true to size. Excellent for wide feet.",
    "hoka":         "Hoka runs true to size with a roomy toe box.",
    "converse":     "Converse runs large — size down half a size.",
    "vans":         "Vans run true to size for standard width.",
    "puma":         "Puma runs slightly small — size up half if between sizes.",
    "salomon":      "Salomon trail shoes run true. Snug fit by design.",
    "timberland":   "Timberland boots run half a size large.",
}

_FOOT_TYPE_ADVICE: dict[str, str] = {
    "wide":          "Look for New Balance (2E/4E widths), Brooks, or ASICS. Size up half in narrow brands like Adidas.",
    "narrow":        "Adidas, Saucony, and Mizuno tend to run narrower.",
    "flat":          "Look for motion control shoes — Brooks Adrenaline, New Balance 860, ASICS Gel-Kayano.",
    "high arch":     "Cushioned neutral shoes work best — HOKA, Brooks Ghost, New Balance Fresh Foam.",
    "overpronation": "Stability shoes are ideal — ASICS GT series, Brooks Adrenaline, New Balance 860.",
}


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

        top = pairs[:3]
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
