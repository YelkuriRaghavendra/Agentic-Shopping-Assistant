# Skill: Stylist

**File:** `skills.py` → `StylistSkill`
**Prompt:** `prompts.py` → `SKILL_STYLIST_PROMPT`

---

## What It Does

Makes the agent respond like a **personal stylist** rather than a search engine.
Instead of just listing products, it explains *why* a recommendation works —
colour theory, occasion appropriateness, how pieces work together.

Without this skill:
> "Here are some pants: [P1] Navy Slim Chinos, [P2] Grey Joggers"

With this skill:
> "Since you're wearing a blue shirt, navy is the strongest pairing — it picks up the
> blue tone without matching it exactly. The Navy Slim Chinos [P1] would look great.
> The grey option [P2] is safer and more versatile if you're unsure."

---

## When It Activates

Activates when **any** of these are true:

| Condition | Example |
|-----------|---------|
| `intent == "outfit_pairing"` | "I have a blue shirt, what goes with it?" |
| Message contains `"outfit"` | "Help me put together an outfit" |
| Message contains `"match"` / `"matches"` | "What matches my grey jeans?" |
| Message contains `"goes with"` | "What goes with this jacket?" |
| Message contains `"pair"` / `"pairs with"` | "What pairs well with navy?" |
| Message contains `"style"` | "How should I style this?" |
| Message contains `"look"` | "What would complete this look?" |
| Message contains `"wear with"` | "What can I wear with these boots?" |
| Message contains `"i have a"` | "I have a red dress, what shoes?" |
| Message contains `"combination"` / `"coordinate"` | "How do I coordinate these?" |

---

## What It Adds to the Prompt

```
ACTIVE SKILL: Personal Stylist

You are now acting as a personal stylist, not just a search tool.

STYLIST RULES:
- Always explain WHY a recommendation works (colour theory, occasion, material)
- Use fashion vocabulary naturally: "tonal", "smart-casual", "statement piece"
- When recommending colour pairings, explain the reasoning
- Mention how pieces can be styled together or with existing wardrobe
- Ask about the occasion if not clear
- If you have size info, mention fit
...
```

To modify what the stylist says → edit `SKILL_STYLIST_PROMPT` in `prompts.py`.

---

## Example Conversation

```
Customer: "I have a blue shirt, what trousers go with it?"

[StylistSkill activates]

Bot: "Blue shirts are really versatile! Here are my top pairings:

Navy Slim Chinos [P1] — $75
Navy is a tonal pairing with blue — sophisticated and always works.
These slim-cut chinos keep the look sharp without being too formal.

Beige Linen Trousers [P2] — $65
Warm contrast to cool blue. Great for casual or smart-casual occasions.
The linen adds a relaxed feel.

Grey Cargo Pants [P3] — $70
The safest, most versatile option. Grey is completely neutral with blue —
works for everything from weekends to casual Fridays."
```

---

## Composability

The Stylist skill works well alongside:

- **GiftAdvisorSkill** — "I need a stylish gift for my wife" → both activate
- **SizeExpertSkill** — "What outfit would work with a slim-fit jacket?" → both activate
- **ReturningCustomerSkill** — knows the customer's usual sizes → integrates size guidance naturally

---

## Modifying This Skill

**To change the tone** → edit `SKILL_STYLIST_PROMPT` in `prompts.py`

**To add a new trigger keyword** → add to `_SIGNALS` list in `StylistSkill`:
```python
_SIGNALS = [
    "outfit", "match", "matches", "goes with", "pair",
    "style", "look", "wear with", "i have a",
    "combination", "coordinate",
    "accessory",    # ← add new keywords here
    "accessorise",
]
```

**To add brand-specific style advice** → extend `build_prompt_addon()`:
```python
def build_prompt_addon(self, ctx: SkillContext) -> SkillResult:
    addon = SKILL_STYLIST_PROMPT
    if ctx.slots.brand == "Nike":
        addon += "\nNOTE: Nike items tend to suit athletic/streetwear styling."
    return SkillResult(prompt_addon=addon)
```
