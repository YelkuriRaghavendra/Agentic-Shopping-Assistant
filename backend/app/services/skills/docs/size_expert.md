# Skill: Size Expert

**File:** `skills.py` → `SizeExpertSkill`
**Prompt:** `prompts.py` → `SKILL_SIZE_EXPERT_PROMPT`

---

## What It Does

Gives specific, accurate sizing guidance — brand quirks, foot conditions,
between-sizes decisions. Goes beyond generic advice to give customers
real confidence before purchasing.

Without this skill:
> "You should check the size guide on the product page."

With this skill:
> "Adidas tends to run slightly narrow, so if you have wide feet I'd size up
> half a size. The Ultraboost also has a snug toe box — if you're between
> a 10 and 10.5, go with the 10.5 for comfort on longer runs."

---

## When It Activates

| Trigger | Example |
|---------|---------|
| `intent == "size_query"` | LLM classified as size intent |
| `"size"` / `"sizing"` | "What size should I get?" |
| `"fit"` / `"fitting"` | "How does this fit?" |
| `"wide feet"` | "I have wide feet" |
| `"narrow feet"` | "My feet are quite narrow" |
| `"flat feet"` | "I have flat feet" |
| `"high arch"` | "I have a high arch" |
| `"overpronation"` | "I overpronate" |
| `"between sizes"` | "I'm between a 9 and 10" |
| `"runs small"` / `"runs large"` | "Do these run small?" |
| `"true to size"` | "Are these true to size?" |
| `"half size"` | "Should I go half a size up?" |

---

## Foot Type Detection

When the skill activates, it tries to detect the customer's foot type
from the message and adds it to the prompt:

| Message contains | Detected type | Advice focuses on |
|-----------------|--------------|-------------------|
| `"wide"` | `wide` | Brands with wide widths (New Balance, Brooks) |
| `"narrow"` | `narrow` | Brands that run narrower (Adidas, Saucony) |
| `"flat"` | `flat` | Motion control shoes (Brooks Adrenaline, ASICS GT) |
| `"high arch"` | `high arch` | Cushioned neutral shoes (HOKA, Brooks Ghost) |
| `"overpronat"` | `overpronation` | Stability shoes |

---

## What It Adds to the Prompt

```
ACTIVE SKILL: Size and Fit Expert

The customer needs sizing guidance. Be specific and helpful.

SIZE EXPERT RULES:
- Be specific about brand sizing quirks (e.g. "Adidas runs narrow — size up")
- For foot conditions (wide, flat, high arch) — recommend specific brands/models
- Always recommend the customer check the brand's size chart for final decision
- If customer is between sizes, give a concrete recommendation with reasoning
- For clothing, explain that sizing varies by cut/style (slim fit vs regular)
...
```

When a brand is known, it adds:
```
BRAND FOCUS: Nike. Include specific sizing notes for this brand.
```

When a foot type is detected, it adds:
```
FOOT TYPE: wide. Prioritise recommendations for this condition.
```

---

## Brand Size Knowledge (in `style_advisor_service.py`)

| Brand | Note |
|-------|------|
| Nike | True to size. Wide feet → half size up |
| Adidas | Runs slightly narrow. Wide feet → size up |
| New Balance | Offers 2E/4E wide widths. True to size standard |
| Converse | Runs large — size down half a size |
| Puma | Runs slightly small — size up if between sizes |
| Hoka | True to size with roomy toe box |
| Timberland | Boots run half a size large |

To add a new brand → edit `_BRAND_SIZE_NOTES` in `style_advisor_service.py`.

---

## Example Conversation

```
Customer: "I have flat feet, do Adidas Ultraboost work for me?"

[SizeExpertSkill activates, foot_type="flat", brand="Adidas"]

Bot: "For flat feet, you generally want motion control or stability shoes
rather than neutral cushioned shoes. The Ultraboost is a cushioned
neutral trainer — it doesn't provide the arch support flat feet
typically need for longer runs.

If you love Adidas, the Adidas Solar Glide ST is a better fit —
it has stability features designed for flat feet.

Alternatively, Brooks Adrenaline [P1] and ASICS Gel-Kayano [P2]
are the most recommended brands for flat feet across the board.

Worth noting: Adidas runs slightly narrow, so if you do go with them,
size up half a size if you're between sizes."
```

---

## Composability

- **StylistSkill** — "what shoes look good AND work for wide feet?" → both activate
- **GiftAdvisorSkill** — "gift for my dad, not sure his size" → both activate
- **ReturningCustomerSkill** — if customer's usual size is known, skips the size question entirely

---

## Modifying This Skill

**To change size advice tone** → edit `SKILL_SIZE_EXPERT_PROMPT` in `prompts.py`

**To add a new brand's sizing notes** → edit `_BRAND_SIZE_NOTES` in `style_advisor_service.py`:
```python
_BRAND_SIZE_NOTES: dict[str, str] = {
    ...
    "on running": "On Running shoes run true to size with a slightly narrow fit.",
    "new balance": "...",
}
```

**To add a new foot condition** → edit `_FOOT_TYPE_ADVICE` in `style_advisor_service.py`:
```python
_FOOT_TYPE_ADVICE: dict[str, str] = {
    ...
    "bunions": "Look for wide toe box shoes — New Balance, Hoka, and Altra are designed with extra toe room.",
}
```
