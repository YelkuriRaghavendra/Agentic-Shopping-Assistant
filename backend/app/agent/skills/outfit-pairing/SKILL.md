# Outfit Pairing Skill

## When to Apply This Skill

Apply when:
- Customer owns an item and wants matching recommendations
- Customer asks what goes with something
- Styling advice is needed beyond product search
- Colour combinations are being discussed

---

## Colour Pairing Rules

### The Pairing Hierarchy

```
Safest     →    Neutral contrast   (white, grey, beige with anything)
Balanced   →    Tonal pairing      (navy with blue, camel with brown)
Bold       →    Colour contrast    (red with navy, yellow with grey)
Avoid      →    Colour clash       (red with orange, blue with green)
```

### Pairing by Owned Colour

| Owns | Best pairs | Bold choice | Avoid |
|------|-----------|-------------|-------|
| Blue | Navy, white, grey, beige, camel, olive | Yellow, orange | Bright blue, green, purple |
| White | Navy, black, grey, beige, camel, any | Red, cobalt blue | Cream (too similar) |
| Black | White, grey, beige, camel, red | Yellow, cobalt | Dark navy (indistinct) |
| Grey | White, black, navy, camel, red | Any bright colour | Nothing — grey is neutral |
| Red | White, black, navy, grey | Yellow, orange | Pink, orange, bright green |
| Navy | White, light blue, beige, grey, camel | Red, yellow | Black (hard to distinguish) |
| Green | White, beige, camel, brown | Red (Christmas risk) | Blue, purple |
| Yellow | White, grey, navy, black | Purple | Orange, red, green |
| Brown | Beige, camel, white, olive, navy | Burnt orange | Black, grey |
| Pink | White, grey, navy, black, beige | Cobalt blue | Red, orange |

### Shade Matters

```
Light blue shirt  → Navy, camel, beige work best
Navy jacket       → White, light grey, cream work best
Royal blue        → White, charcoal, black work best
Denim blue        → Almost anything — most versatile blue
```

---

## Outfit Occasion Rules

| Occasion | Rules |
|----------|-------|
| Smart-casual | No gym wear, no overly formal. Chinos + shirt. Loafers or clean trainers. |
| Casual | Jeans, joggers, t-shirts acceptable. Trainer-friendly. |
| Work / office | Smart trousers or dark jeans. Collared shirt or blouse. Leather or suede shoes. |
| Formal | Suit or dress. Avoid trainers entirely. |
| Evening out | One statement piece. Everything else neutral. |

---

## The Search Query Rule

When searching for matching items, **never search for the same colour** as what the customer owns.

```
Customer owns: blue shirt
Search for:    navy trousers OR grey trousers OR beige trousers
NOT:           blue trousers
```

Build the search query from the top 3–4 pairing colours:
```
search_query = "navy grey beige {wanted_category}"
```

---

## Style Vocabulary

Use these terms naturally in responses:

- **Tonal** — similar shades of the same colour family (navy + blue)
- **Smart-casual** — dressed up but relaxed (chinos + polo)
- **Statement piece** — one bold item, rest kept neutral
- **Capsule** — a small, versatile collection of items that all work together
- **Clean lines** — minimalist, without busy patterns
- **Contrast** — deliberately different colours that complement
- **Monochromatic** — same colour family throughout an outfit

---

## Response Template

```
1. Acknowledge what they own
   "A blue shirt is a great starting point — really versatile."

2. Name the pairing principle
   "Blue pairs best with neutral tones — navy picks up the blue without matching it,
   and beige or grey add warm/cool contrast."

3. Show 2–3 options with WHY
   "Navy Chinos [P1] — tonal and sophisticated, works for everything
   Grey Trousers [P2] — safest and most versatile
   Beige Linen [P3] — warm contrast, great for summer"

4. Name a "safe" and a "bold" pick
   "If you want safe: the grey. If you want a sharper look: the navy."

5. Ask about occasion if not mentioned
   "Is this for casual wear or something smarter?"
```
