# Command: /style

## Syntax

```
/style "<what the customer owns or wants to style>"
```

## Examples

```
/style "I have a blue shirt, what trousers go with it?"
/style "outfit for a smart-casual dinner"
/style "what shoes match grey jeans?"
```

## What It Does

Activates the **Stylist Agent** which loads the `outfit-pairing` skill.

The agent acts as a personal stylist — it doesn't just search for products,
it explains *why* a combination works using colour theory and fashion principles.

## Agent Loaded

→ `agents/stylist-agent.md`

## Skills Loaded

→ `skills/outfit-pairing/SKILL.md`

## When to Use

Use `/style` when the customer:
- Owns an item and wants matching recommendations
- Wants outfit advice for a specific occasion
- Asks about colour combinations
- Wants to know what goes together

For plain product search without styling advice, do not use this command —
let the main agent handle it via `search_products` tool.
