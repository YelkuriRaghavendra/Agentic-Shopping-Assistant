# Agent Skills

Skills are focused capabilities that extend how the agent responds.
Each skill activates automatically when relevant and adds targeted instructions to the LLM prompt.

## How Skills Work

```
Customer message arrives
        ↓
SkillRegistry checks every skill → can_handle()?
        ↓
Active skills return prompt addons
        ↓
Addons merged into the base system prompt
        ↓
LLM responds with combined context
```

Skills are:
- **Composable** — multiple skills can be active at once
- **Stateless** — all state comes from the conversation context
- **Zero-cost to activate** — `can_handle()` is pure logic, no LLM calls
- **Additive** — they append to the base prompt, never replace it

---

## Available Skills

| Skill | File | Activates When |
|-------|------|----------------|
| [Stylist](stylist.md) | `skills.py` | Outfit pairing, style advice, colour matching |
| [Gift Advisor](gift_advisor.md) | `skills.py` | Buying for someone else, occasion-based shopping |
| [Size Expert](size_expert.md) | `skills.py` | Sizing questions, foot conditions, brand quirks |
| [Returning Customer](returning_customer.md) | `skills.py` | Customer has a known profile with past preferences |
| [Empathy](empathy.md) | `skills.py` | Frustrated customer, escalation request |

---

## Where Prompts Live

All prompt strings are in **`prompts.py`** — one file, easy to find and edit.

```
app/services/skills/
  prompts.py         ← Edit this to change what skills say
  base_skill.py      ← Interface every skill must implement
  skills.py          ← All 5 skill implementations
  skill_registry.py  ← Discovers + merges active skills
  docs/
    README.md        ← This file
    stylist.md
    gift_advisor.md
    size_expert.md
    returning_customer.md
    empathy.md
```

---

## Adding a New Skill

**Step 1** — Write the prompt in `prompts.py`:

```python
# prompts.py
SKILL_MY_NEW_SKILL_PROMPT = """
ACTIVE SKILL: My New Skill

What the LLM should do differently when this skill is active.
Keep it concise — 5 to 10 bullet points maximum.
"""
```

**Step 2** — Implement the skill class in `skills.py`:

```python
class MyNewSkill(SkillBase):
    name        = "my_new_skill"
    description = "One-sentence description of what this skill does"

    _SIGNALS = ["keyword1", "keyword2"]   # triggers

    def can_handle(self, ctx: SkillContext) -> bool:
        msg = ctx.message.lower()
        return any(s in msg for s in self._SIGNALS)

    def build_prompt_addon(self, ctx: SkillContext) -> SkillResult:
        return SkillResult(
            prompt_addon=SKILL_MY_NEW_SKILL_PROMPT,
            metadata={"skill": self.name},
        )
```

**Step 3** — Register it in `skill_registry.py`:

```python
_ALL_SKILLS: list[SkillBase] = [
    ReturningCustomerSkill(),
    StylistSkill(),
    GiftAdvisorSkill(),
    SizeExpertSkill(),
    EmpathySkill(),
    MyNewSkill(),    # ← add here
]
```

**Step 4** — Add a `.md` file in `docs/` following the same format as the existing ones.

**Step 5** — Write tests in `tests/test_suggestions_and_skills.py`:

```python
def test_my_new_skill_activates_for_keyword(self, registry, empty_slots):
    ctx = SkillContext(message="keyword1", intent="product_search", ...)
    result = registry.resolve(ctx)
    assert "my_new_skill" in result.metadata.get("active_skills", [])
```

That's it — no changes needed anywhere else.

---

## Skill Priority

Skills are evaluated in this order (lower index = lower priority):

1. `ReturningCustomerSkill` — personalisation layer
2. `StylistSkill` — style advice layer
3. `GiftAdvisorSkill` — gift context layer
4. `SizeExpertSkill` — sizing guidance layer
5. `EmpathySkill` — **always last** — if active, its tone overrides all others

The `EmpathySkill` being last ensures that when a customer is frustrated,
the empathy tone wins over any other skill's instructions.

---

## Skill Activation Log

Every activated skill is logged. Check your logs for:

```
skills.activated  skills=["stylist", "gift_advisor"]  intent=gift_finder  turn=3
```

This makes it easy to debug unexpected behaviour — you can see exactly which
skills fired for any given message.
