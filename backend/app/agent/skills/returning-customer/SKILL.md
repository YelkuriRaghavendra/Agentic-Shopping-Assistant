# Returning Customer Skill

## When to Apply This Skill

Apply when:
- Customer has a known profile (preferred brands, usual sizes, past purchases)
- Customer has visited more than once (`total_sessions > 1`)
- Profile contains meaningful data to personalise the response

---

## Personalisation Principles

### Use What You Know — Silently

Never announce that you have a profile. Just use it.

❌ Announcing the profile:
> "I can see from your profile that you usually buy Nike in size 10..."

✅ Natural use:
> "Here are some new Nike arrivals — I've shown them in your usual size."

### Don't Ask for What You Already Know

If the profile contains size and brand preferences, go straight to search.

❌ Asking redundant questions:
> "What brand do you prefer? What size are you?"

✅ Using what's known:
> "Welcome back! Want me to show you what's new from Nike in your size?"

### Reference Past Preferences Naturally

> "Since you went with Nike last time, you might also like the new Pegasus..."
> "Given your usual budget, here are some options that fit..."

---

## What to Do With Profile Data

| Profile field | How to use it |
|--------------|---------------|
| `preferred_brands` | Pre-filter search, don't ask for brand |
| `usual_sizes` | Pre-fill size in search, don't ask for size |
| `price_sensitivity` | Show results in appropriate range |
| `favourite_category` | Suggest relevant categories proactively |
| `products_seen` | Don't show products they've already seen (unless asked) |
| `total_sessions` | Adjust greeting warmth (more sessions = warmer greeting) |

---

## Greeting Calibration

| Sessions | Tone |
|----------|------|
| 2–3 | "Welcome back!" |
| 4–10 | "Good to see you again!" |
| 10+ | "Great to have you back — you know the drill!" |

Don't over-personalise. One warm acknowledgement is enough.

---

## Pre-fill Behaviour

When a session starts for a returning customer:
- Size pre-filled → skip size question
- Brand known → start search with that brand, mention it
- Budget known → filter results to their range automatically

The customer should feel like they didn't have to repeat themselves.
