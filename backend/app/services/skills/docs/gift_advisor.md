# Skill: Gift Advisor

**File:** `skills.py` → `GiftAdvisorSkill`
**Prompt:** `prompts.py` → `SKILL_GIFT_ADVISOR_PROMPT`

---

## What It Does

Shifts the agent's focus from the customer to the **recipient** when
the customer is shopping for someone else.

Without this skill:
> "Here are some running shoes: [P1] Nike Pegasus, [P2] Brooks Ghost"

With this skill:
> "These are great picks for a runner! The Nike Pegasus [P1] is the most popular
> choice for everyday running — it's a safe bet if you don't know his exact
> preferences. Is this a birthday present? I can suggest gift wrapping options too."

---

## When It Activates

Activates when **any** of these appear in the message:

| Trigger | Example |
|---------|---------|
| `"gift"` | "I need a gift for someone" |
| `"present"` | "Birthday present for my wife" |
| `"birthday"` | "It's his birthday next week" |
| `"christmas"` | "Christmas gift ideas" |
| `"anniversary"` | "Anniversary present" |
| `"for my"` | "Something for my dad" |
| `"for him"` / `"for her"` | "What would look good for her?" |
| `"for a friend"` | "Looking for something for a friend" |
| `"surprise"` | "I want to surprise my partner" |
| `intent == "gift_finder"` | LLM classified as gift intent |

---

## Recipient Extraction

The skill automatically extracts the recipient from the message and
adds it to the prompt so the LLM tailors recommendations:

```python
"I need a gift for my dad who loves running"
→ recipient = "dad"
→ prompt includes: "RECIPIENT: dad. Tailor all recommendations to them."
```

Extracted recipients seen in logs:
```
gift_advisor.skill  recipient="dad"  intent=gift_finder
```

---

## What It Adds to the Prompt

```
ACTIVE SKILL: Gift Advisor

The customer is buying for someone else. Tailor responses accordingly.

GIFT ADVISOR RULES:
- Ask about the recipient's interests if not already known
- Suggest gift wrapping / gift card if available
- Frame recommendations around the recipient ("she would love this for running")
- If customer mentions an occasion — acknowledge it warmly
- Suggest a price range if customer hasn't specified one
- Offer 2-3 options at different price points when possible
- Remind customer about delivery times if occasion is time-sensitive
```

To change what the gift advisor says → edit `SKILL_GIFT_ADVISOR_PROMPT` in `prompts.py`.

---

## Example Conversation

```
Customer: "I need a birthday gift for my dad who runs"

[GiftAdvisorSkill activates, recipient="dad"]

Bot: "How thoughtful! Here are some great birthday gifts for a runner:

Nike Pegasus 40 [P1] — $130  ⭐ Most popular
The go-to daily trainer. Versatile, well-cushioned, works for all paces.

Brooks Adrenaline GTS [P2] — $140
If he has any knee or joint concerns, this stability shoe is excellent.
Great for older runners or anyone logging high mileage.

HOKA Clifton 9 [P3] — $145
Maximum cushion — feels like running on clouds.
A real treat if he's been eyeing them.

Does he have a preferred brand, or any fit considerations like wide feet?
Also — when is the birthday? I can check delivery timelines for you."
```

---

## Composability

Works well alongside:

- **StylistSkill** — "stylish gift for my wife" → both activate, combines gift focus with style advice
- **SizeExpertSkill** — "gift for my dad, not sure of his size" → both activate
- **ReturningCustomerSkill** — if customer has bought gifts before, past preferences inform suggestions

---

## Modifying This Skill

**To change the gift advisor's behaviour** → edit `SKILL_GIFT_ADVISOR_PROMPT` in `prompts.py`

**To add new occasion types** → add to `_SIGNALS`:
```python
_SIGNALS = [
    "gift", "present", "birthday", "christmas", "anniversary",
    "for my", "for him", "for her", "for a friend", "surprise",
    "graduation",    # ← new
    "father's day",  # ← new
    "mother's day",  # ← new
    "valentines",    # ← new
]
```

**To improve recipient extraction** → update the regex in `_extract_recipient()`:
```python
def _extract_recipient(self, message: str) -> str | None:
    # Current: matches "for my X"
    # Extend to also match "buying for X" or "getting X a gift"
    patterns = [
        r'for\s+my\s+([\w\s]+?)(?:\s+who|\s+that|$|,|\.)',
        r'buying\s+for\s+([\w\s]+?)(?:\s+who|$|,|\.)',
    ]
    for pattern in patterns:
        match = re.search(pattern, message, re.IGNORECASE)
        if match:
            return match.group(1).strip()
    return None
```
