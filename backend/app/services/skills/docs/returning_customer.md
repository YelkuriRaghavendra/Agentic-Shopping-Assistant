# Skill: Returning Customer

**File:** `skills.py` → `ReturningCustomerSkill`
**Prompt:** `prompts.py` → `SKILL_RETURNING_CUSTOMER_PROMPT`

---

## What It Does

Personalises the response for returning customers using their stored profile.
The agent acts like a shop assistant who remembers you — it doesn't ask for
information it already has, and it references past preferences naturally.

Without this skill (new customer):
> "What brand do you prefer? What size are you? What's your budget?"

With this skill (returning customer, profile: Nike, size 10, mid budget):
> "Welcome back! I've pulled up some new Nike arrivals in your size.
> Want me to show you what's new in running, or something different today?"

---

## When It Activates

Activates when the customer's profile contains **any** of:

| Profile field | Example value |
|--------------|---------------|
| `preferred_brands` | `["Nike", "Adidas"]` |
| `usual_sizes` | `{"shoes": "10", "clothing": "L"}` |
| `total_sessions > 1` | `3` |

Guest users (no `customer_id`) never have a profile — this skill never fires for guests.

---

## What It Adds to the Prompt

```
ACTIVE SKILL: Returning Customer Recognition

This customer has shopped with us before. Use their history to personalise.

PERSONALISATION RULES:
- Acknowledge their preferences naturally (don't announce you have a profile)
- Don't ask for info you already know (size, preferred brand, budget range)
- Reference past purchases naturally if relevant
- If they previously bought a product, don't show it again unless they ask
- Use their price sensitivity as a guide
- Greet warmly but not obsequiously — one friendly acknowledgement is enough
```

It also appends a summary of what is known:
```
KNOWN CUSTOMER DATA:
- Preferred brands: Nike, Adidas
- Usual sizes: shoes size 10, clothing size L
- Price range: mid-range budget ($80–200)
- Usually shops for: running
- Returning customer (3 sessions)
```

---

## Profile Data Structure

The profile lives in `customers.profile` (JSONB column). Written to by `MemoryService.update_customer_profile()` after every successful product interaction.

```json
{
  "preferred_brands":   ["Nike", "Adidas"],
  "usual_sizes":        {"shoes": "10", "clothing": "L"},
  "price_sensitivity":  "mid",
  "favourite_category": "running",
  "products_seen":      [{"sku": "NK-001", "title": "Nike Air Max", "date": "2024-03-10"}],
  "interaction_count":  12,
  "total_sessions":     3,
  "last_seen":          "2024-03-16T10:30:00Z"
}
```

---

## Example Conversation

```
New customer:
  Bot: "What are you looking for — shoes, a jacket, or something else?"
  Bot: "Any brand you prefer?"
  Bot: "What size are you?"

Returning customer (Nike, size 10, running):
  Bot: "Welcome back! Still looking for running gear, or something different today?"
  Customer: "Show me something new"
  Bot: [searches Nike running shoes size 10] → shows results immediately
       "Here are some new Nike running options in your size..."
```

---

## Privacy Note

The personalisation is framed naturally — the agent does not say
"I can see from your profile that..." or "According to our records...".
It simply uses the information to give better responses without drawing
attention to it. Edit `SKILL_RETURNING_CUSTOMER_PROMPT` in `prompts.py`
to change this behaviour.

---

## Modifying This Skill

**To change personalisation tone** → edit `SKILL_RETURNING_CUSTOMER_PROMPT` in `prompts.py`

**To lower the activation threshold** → edit `can_handle()`:
```python
def can_handle(self, ctx: SkillContext) -> bool:
    profile = ctx.customer_profile
    # Currently requires brands OR sizes OR 2+ sessions
    # To activate for any returning customer:
    return bool(profile)  # just needs a non-empty profile
```

**To add more profile fields** → update `MemoryService.update_customer_profile()` in `memory_service.py`
and add corresponding display in `build_prompt_addon()` here.
