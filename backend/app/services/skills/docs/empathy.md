# Skill: Empathy

**File:** `skills.py` → `EmpathySkill`
**Prompt:** `prompts.py` → `SKILL_EMPATHY_PROMPT`

---

## What It Does

Shifts the agent's tone when a customer is frustrated, upset, or wants
to speak to a human. Prioritises acknowledgement and resolution over
product recommendations.

Without this skill:
> "I can help you track your order! Here are your options..."

With this skill:
> "I'm really sorry to hear your order still hasn't arrived — that's
> completely unacceptable. Let me look into this for you right now.
> Can you share your order number so I can check the status?"

---

## Priority

**EmpathySkill is always last in the registry.** This means when it's active,
its prompt instructions appear at the end and carry the highest weight with
the LLM. An empathetic tone always overrides any other skill's tone.

```python
_ALL_SKILLS: list[SkillBase] = [
    ReturningCustomerSkill(),
    StylistSkill(),
    GiftAdvisorSkill(),
    SizeExpertSkill(),
    EmpathySkill(),    # ← last = highest priority
]
```

---

## When It Activates

### Frustration signals (customer is upset):

| Trigger | Example |
|---------|---------|
| `"terrible"` / `"awful"` | "Your service is terrible" |
| `"worst"` / `"garbage"` | "Worst experience ever" |
| `"broken"` / `"damaged"` | "The item arrived broken" |
| `"never again"` | "I'll never order from you again" |
| `"waste of money"` | "This was a complete waste of money" |
| `"ripped off"` / `"scam"` | "I feel ripped off" |
| `"still waiting"` | "I'm still waiting for my order" |
| `"3 weeks"` / `"2 weeks"` | "It's been 3 weeks" |
| `"no one helped"` | "I've spoken to 3 people and no one helped" |

### Escalation signals (wants a human):

| Trigger | Example |
|---------|---------|
| `"speak to"` / `"talk to"` | "I want to speak to someone" |
| `"manager"` / `"supervisor"` | "Get me your manager" |
| `"real person"` / `"human"` | "I want to talk to a real person" |
| `"escalate"` | "I need to escalate this" |
| `intent == "escalate_to_human"` | LLM classified as escalation |

---

## Escalation Detection

The skill detects whether the customer explicitly wants a human and
adjusts its instructions:

```python
wants_human = True  →  "CRITICAL: Customer has asked to speak to a human.
                         Acknowledge this, then offer to connect them.
                         Do not try to resolve the issue yourself — escalate."

wants_human = False →  Standard empathy tone — acknowledge frustration,
                         focus on solutions, offer escalation proactively.
```

---

## What It Adds to the Prompt

```
ACTIVE SKILL: Empathetic Support

The customer seems frustrated or is dealing with a problem.

EMPATHY RULES:
- Acknowledge their frustration before jumping to solutions
- Use empathetic language: "I understand that's frustrating"
- Don't be defensive about the store — focus on resolving the issue
- Offer concrete next steps, not vague reassurances
- If the issue requires human intervention, offer to escalate proactively
- Don't ask them to repeat information they already gave
- Keep responses shorter — frustrated customers don't want to read long text
```

When escalation is detected, it also adds:
```
CRITICAL: Customer has asked to speak to a human.
Acknowledge this, then offer to connect them.
Do not try to resolve the issue yourself — escalate.
```

---

## Example Conversations

**Frustrated customer:**
```
Customer: "I've been waiting 3 weeks for my order and no one has helped me"

[EmpathySkill activates, wants_human=False]

Bot: "I'm really sorry — three weeks is far too long and I completely
understand your frustration. Let me look into this right now.

Could you share your order number so I can check exactly where it is?
If there's a problem with the delivery, I'll escalate this immediately
and make sure someone contacts you today."
```

**Wants a human:**
```
Customer: "I want to speak to a real person"

[EmpathySkill activates, wants_human=True → escalate_to_human tool fires]

Bot: "Of course — I'll connect you with one of our customer service
agents right away. You'll receive a response within 2 hours via email.
I've shared a full summary of our conversation with the team so you
won't need to repeat yourself."
```

---

## Composability

The Empathy skill can be active alongside other skills. In most frustrated
customer scenarios, the empathy tone takes precedence because it appears
last in the merged prompt. For example:

- Frustrated customer asking about a return → `EmpathySkill` + `return_request` tool
- Angry customer with sizing complaint → `EmpathySkill` + `SizeExpertSkill`

---

## Modifying This Skill

**To change the empathy tone** → edit `SKILL_EMPATHY_PROMPT` in `prompts.py`

**To add new frustration triggers** → add to `_FRUSTRATION_SIGNALS`:
```python
_FRUSTRATION_SIGNALS = [
    "terrible", "awful", ...,
    "shocking",      # ← new
    "unbelievable",  # ← new
    "disgusted",     # ← new
]
```

**To change escalation behaviour** → edit the conditional in `build_prompt_addon()`:
```python
if wants_human:
    addon += (
        "\nCRITICAL: Customer has asked to speak to a human. "
        "Acknowledge this, provide the direct support phone number, "
        "and close the chat gracefully."
    )
```
