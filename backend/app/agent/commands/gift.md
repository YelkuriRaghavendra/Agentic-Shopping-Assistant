# Command: /gift

## Syntax

```
/gift "<recipient and context>"
```

## Examples

```
/gift "birthday for my dad who runs"
/gift "christmas present for my teenage daughter, budget $80"
/gift "anniversary gift for my wife, she loves fashion"
```

## What It Does

Activates the **Gift Advisor Agent** which loads the `gift-finding` skill.

The agent focuses entirely on the recipient — their interests, the occasion,
and what would delight them — rather than searching generically.

## Agent Loaded

→ `agents/gift-advisor-agent.md`

## Skills Loaded

→ `skills/gift-finding/SKILL.md`

## When to Use

Use `/gift` when the customer explicitly states they are buying for someone else.

Triggers:
- "gift for", "present for", "birthday for"
- "for my dad / mum / wife / partner"
- Any mention of an occasion (birthday, Christmas, anniversary)
