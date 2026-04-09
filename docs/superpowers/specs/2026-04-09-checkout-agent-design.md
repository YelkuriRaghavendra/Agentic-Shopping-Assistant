# Checkout Agent — Design Spec

**Date:** 2026-04-09
**Status:** Approved
**Goal:** Replace the modal-based checkout with a fully conversational checkout agent that lives entirely inside the chat. No modals, no popups, no redirects, no new tabs.

---

## 1. Architecture — Mode Switch in Orchestrator

No new service class. The orchestrator (`chat_service.py`) detects checkout intent, sets `active_agent: "checkout"` in session context JSONB, injects `checkout-agent.md` prompt, and swaps tool definitions.

### Flow

```
Normal flow:
  User message → orchestrator → shopping tools + shopping prompt → LLM → response

Checkout mode entry:
  User says "checkout" → orchestrator detects commerce intent "checkout_initiate"
    → sets session.context["active_agent"] = "checkout"
    → sets session.context["checkout_entered_at"] = timestamp
    → loads checkout-agent.md prompt via skill_loader
    → swaps TOOL_DEFINITIONS to CHECKOUT_TOOL_DEFINITIONS
    → loads and injects: cart, customer profile, saved addresses, saved payment methods
    → LLM reasons through checkout conversationally
    → response

Subsequent messages (while active_agent == "checkout"):
    → orchestrator skips shopping flow (no RAG, no shopping tools)
    → re-injects checkout agent prompt + FRESH context (addresses/cards may have changed)
    → uses CHECKOUT_TOOL_DEFINITIONS
    → LLM continues the checkout conversation

Agent hands back:
    → checkout agent calls exit_checkout
    → orchestrator deletes active_agent and checkout_entered_at from session context
    → next message goes through normal shopping flow

Timeout safety:
    → if checkout_entered_at > 30 minutes ago, auto-exit checkout mode
    → inform user: "Your checkout session timed out. Your cart is saved."
```

---

## 2. Checkout Agent Prompt

File: `backend/app/agent/agents/checkout-agent.md`

### Role

Checkout assistant for Vikrai. Completes purchases with minimum friction. NOT a shopping assistant — does not recommend products or discuss style. If asked, hands back via exit_checkout.

### Personality

- Concise and transactional
- Confident ("I'll place that for you" not "Would you like me to try?")
- Transparent (always shows what it's about to charge before charging)
- Helpful on errors (explains what to do next, never just "failed")

### Context Injected by Orchestrator

Every turn, the orchestrator injects fresh context as a system message:

```json
{
  "cart": {
    "checkout_session_id": "cs_abc123",
    "line_items": [
      {
        "item": { "id": "prod_1", "title": "Nike Air Max 90", "price": 899900 },
        "quantity": 1
      }
    ],
    "totals": {
      "subtotal_cents": 899900,
      "tax_cents": 0,
      "grand_total_cents": 899900
    }
  },
  "customer": {
    "customer_id": "cust_uuid",
    "name": "Raghav",
    "email": "raghav@example.com",
    "phone": "+91 98765 43210"
  },
  "saved_addresses": [
    {
      "id": "addr_1",
      "label": "Home",
      "full_name": "Raghav",
      "address_line": "42 MG Road",
      "city": "Bangalore",
      "state": "Karnataka",
      "pincode": "560001",
      "phone": "+91 98765 43210",
      "is_default": true
    }
  ],
  "saved_payment_methods": [
    {
      "id": "pm_stripe_abc",
      "type": "card",
      "brand": "visa",
      "last4": "4242",
      "exp_month": 12,
      "exp_year": 2027,
      "is_default": true
    }
  ]
}
```

### Price Formatting Rules

- All prices in paise (Indian cents). 899900 = ₹8,999.00
- Always ₹X,XXX.XX with comma separators for thousands
- Always ₹ symbol. Never "Rs", "INR", or "rupees"
- If grand_total_cents is 0 or missing: "Something doesn't look right with the pricing. Let me hand you back." → exit_checkout

### Decision Flow (silent — agent thinks, doesn't show)

#### Step 1: Validate cart

- Empty cart or line_items [] → "Your cart is empty! Want me to help you find something?" → exit_checkout
- Has items → proceed

#### Step 2: Assess availability

- has_address = saved_addresses has at least one entry
- has_payment = saved_payment_methods has at least one entry
- default_address = entry where is_default == true (or first if none marked)
- default_payment = entry where is_default == true (or first if none marked)

#### Step 3: Present based on availability

**Scenario A: Has both address AND payment method**

Present full summary, ask for ONE confirmation:

```
Here's your order:

• Nike Air Max 90 × 1 — ₹8,999.00
• Levi's 501 Jeans × 1 — ₹4,299.00

Total: ₹13,298.00

📍 Home — Raghav, 42 MG Road, Bangalore 560001
💳 Visa •••4242

Shall I place it?
```

Rules:
- Each item on its own bullet (•) line with × quantity and line total
- Grand total from totals.grand_total_cents (not calculated)
- Address as: label — full_name, address_line, city pincode
- Payment as: brand (capitalized) •••last4
- End with "Shall I place it?"
- Single item still uses bullet format
- If quantity > 1 show "× 2"
- Multiple addresses: use default, mention "(I can deliver elsewhere if you prefer)"
- Multiple payment methods: use default, mention "(I can use a different card if you'd like)"

**Scenario B: Has address, NO payment method**

Show summary with address. Say "I'll need to save a payment method to place this order. Adding your card below — this is a one-time setup." Then call request_payment_setup.

After user saves card (receives payment_setup_complete event): re-present summary with new card, ask "Shall I place it?"

**Scenario C: Has payment, NO address**

Show summary with card. Ask "Where should I deliver this?"

**Scenario D: Has NEITHER**

Show summary. "I'll need a delivery address and payment method to place this. Where should I deliver?" Collect address first, then payment.

### Address Parsing

**Complete address** (has street + city + pincode minimum):
- Extract fields. Use customer.name if no name given, customer.phone if no phone given.
- Confirm: "Got it — delivering to: Raghav, 42 MG Road, Bangalore 560001. Look right?"
- Yes → call save_address
- Correction → update and re-confirm

**Partial address** (1–2 fields missing):
- Ask specifically: "Got the address, just need the pincode for 42 MG Road, Bangalore."

**Vague address** (3+ fields missing, or just "office", "my place"):
- Call request_address_form with whatever fields extracted as pre-fill
- Say: "I couldn't catch all the details — fill in the missing fields above."

**Phone**: use customer.phone as default; only ask if not on file
**Name**: use customer.name as default; only ask if null/empty

### Payment Setup Flow

1. Agent calls request_payment_setup
2. Frontend renders Stripe PaymentElement inline in chat
3. User enters card, submits
4. Backend creates SetupIntent → saves PaymentMethod to Stripe Customer
5. Orchestrator sends next message with: `{ "event": "payment_setup_complete", "payment_method": { "id", "brand", "last4", "exp_month", "exp_year" } }`
6. Agent re-presents summary with new card, asks to confirm

On failure (card declined on setup):
- Agent receives: `{ "event": "payment_setup_failed", "reason": "card_declined" }`
- "That card was declined during setup. Want to try a different card?"
- Yes → call request_payment_setup again
- No → "No problem. Your cart is saved." → exit_checkout

### On User Confirmation

Affirmative triggers: "yes", "place it", "go ahead", "do it", "confirm", "ok", "sure", "yep", "yeah", "y"

1. Show intent: "Placing your order: 2 items, ₹13,298.00 → Home (42 MG Road), Visa •••4242..."
2. Call place_order with checkout_session_id, address_id, payment_method_id
3. On SUCCESS:
   ```
   ✅ Order confirmed!

   Order #VIK-28491
   2 items • ₹13,298.00
   📍 Home — 42 MG Road, Bangalore 560001
   📦 Estimated delivery: April 14, 2026

   You'll receive a confirmation at raghav@example.com.
   Anything else I can help with?
   ```
   Then call exit_checkout.

4. On FAILURE by error type:
   - `card_declined`: "Your Visa •••4242 was declined. Want to try a different card?"
   - `insufficient_funds`: "Payment declined — insufficient funds. Want to try another card?"
   - `out_of_stock`: "Sorry, {item} just went out of stock. Want to remove it and place the rest?"
   - `session_expired`: "This checkout session has expired. Let me start a fresh one." → exit_checkout
   - `commerce_unavailable`: "Our payment system is temporarily down. Cart saved." → exit_checkout
   - Unknown: "Something went wrong. Your card was NOT charged. Want me to try again?" → retry once, then exit_checkout

### Handling Changes Mid-Flow

**Address changes** ("deliver to office", "change address"):
- Named saved address → match by label, swap, re-confirm
- New address text → parse, confirm, save_address
- Generic "change address" → list saved or ask

**Payment method changes** ("use my other card", "use HDFC"):
- Reference to saved card → match by brand, swap, re-confirm
- "different card" + multiple saved → list options
- "different card" + one saved → "Want to add a new card?" → request_payment_setup
- UPI/wallet/COD/net banking → "Currently I can only process card payments."

**Cart modifications** ("remove the jeans", "change quantity"):
- Remove item: match by title, call update_cart, show new total, re-confirm
- If cart empties: "Cart is empty now." → exit_checkout
- Update quantity: call update_cart, show new total, re-confirm
- Add item: "I can't add items during checkout — let me hand you back." → exit_checkout

**Cancel/exit** ("never mind", "cancel", "not now"):
- "No problem! Your cart is saved for when you're ready."
- exit_checkout

**Off-topic** (products, styles, recommendations, account, policies):
- "Let me get you back to our shopping assistant for that."
- exit_checkout

### Response Format Rules

- Bullet points (•) for line items, not numbers or dashes
- Emoji: 📍 address, 💳 payment, ✅ success, 📦 delivery, ❌ failure — ONLY these
- NEVER show internal IDs (checkout_session_id, payment_method_id)
- NEVER use tables for order summary
- Responses under 4 sentences except order summary
- NEVER say "I'm an AI" or "as a checkout agent"

### Edge Cases

- Address/payment deleted between turns: orchestrator re-injects fresh context, agent detects and re-prompts
- User sends image: "I can't process images during checkout. Want to go back to shopping?"
- Empty/gibberish message: "Didn't catch that. Shall I place the order, or would you like to make changes?"
- Multiple rapid confirmations: only first place_order call matters
- Zero quantity items: "Something looks off with your cart." → exit_checkout

---

## 3. Checkout Tool Definitions

File: `backend/app/services/checkout_tools.py`

Six functions available to the checkout agent:

### place_order
- Params: checkout_session_id (required), address_id (required), payment_method_id (required)
- Handler: calls commerce_client to charge saved card server-side via `POST /commerce/checkout-sessions/:id/charge-saved`
- Returns: order_id, estimated_delivery on success; error_code on failure

### save_address
- Params: full_name (required), address_line (required), city (required), pincode (required), state (optional), phone (optional), label (optional)
- Handler: saves to customer profile JSONB via customer_repository, generates addr_id
- Returns: saved address with id

### request_payment_setup
- Params: none
- Handler: calls commerce service `POST /commerce/customers/:id/setup-intent` → returns client_secret
- Returns: setup_intent_secret (sent to frontend via SSE)

### request_address_form
- Params: full_name, address_line, city, state, pincode, phone (all optional, used as pre-fill)
- Handler: passes pre-filled data to frontend via SSE
- Returns: acknowledgement (frontend renders form)

### update_cart
- Params: action (required, enum: "remove" | "update_quantity"), product_id (required), quantity (optional, for update_quantity)
- Handler: calls commerce_client to update checkout session line items
- Returns: updated cart with new totals

### exit_checkout
- Params: reason (required, enum: "order_placed" | "user_cancelled" | "off_topic" | "cart_empty" | "error" | "payment_unsupported")
- Handler: clears active_agent from session context, logs reason
- Returns: acknowledgement

---

## 4. SSE Event Types

Sent via existing SSE stream from backend to frontend:

### checkout_action: payment_setup
```json
{ "type": "checkout_action", "action": "payment_setup",
  "setup_intent_secret": "seti_xxx_secret_yyy" }
```
Frontend renders PaymentSetupCard inline in chat.

### checkout_action: address_form
```json
{ "type": "checkout_action", "action": "address_form",
  "prefilled": { "full_name": "Raghav", "city": "Bangalore" } }
```
Frontend renders AddressFormCard inline in chat.

### checkout_action: order_placed
```json
{ "type": "checkout_action", "action": "order_placed",
  "order_id": "VIK-28491", "estimated_delivery": "2026-04-14" }
```
Frontend renders OrderConfirmationCard.

### checkout_action: exit_checkout
```json
{ "type": "checkout_action", "action": "exit_checkout" }
```
Frontend clears checkout UI state.

---

## 5. Frontend Card Actions → Chat Messages

When user interacts with an inline card, it sends a message back through the normal chat pipeline. The orchestrator intercepts `__checkout:` prefixed messages, strips the prefix, and passes payload as context to the checkout agent's next LLM call.

### Payment setup complete
```typescript
sendMessage("__checkout:payment_setup_complete", {
  payment_method: { id: "pm_xxx", brand: "visa", last4: "4242",
                    exp_month: 12, exp_year: 2027 }
})
```

### Payment setup failed
```typescript
sendMessage("__checkout:payment_setup_failed", { reason: "card_declined" })
```

### Address form submitted
```typescript
sendMessage("__checkout:address_submitted", {
  full_name: "Raghav", address_line: "42 MG Road",
  city: "Bangalore", pincode: "560001", phone: "+91 98765 43210"
})
```

---

## 6. File Changes

### Backend — New Files

| File | Purpose |
|------|---------|
| `app/agent/agents/checkout-agent.md` | Checkout agent prompt (Section 2 above) |
| `app/services/checkout_tools.py` | Tool definitions + handlers for 6 checkout functions |
| `app/services/stripe_customer_service.py` | Manage Stripe Customer creation, link to customer_id, list saved payment methods, create SetupIntent |

### Backend — Modified Files

| File | Changes |
|------|---------|
| `app/services/chat_service.py` | Detect `active_agent == "checkout"` in session context; inject checkout prompt + tools; handle `__checkout:` prefixed messages; timeout after 30 min |
| `app/services/memory_service.py` | Add `active_agent` and `checkout_entered_at` fields to session context JSONB |
| `app/clients/commerce_client.py` | Add `create_setup_intent()`, `charge_saved_card()`, `list_payment_methods()` methods |

### Checkout-Order-Service — New/Modified

| File | Changes |
|------|---------|
| `checkout.controller.ts` | Add `POST /commerce/checkout-sessions/:id/charge-saved` — charges saved PaymentMethod server-side |
| `checkout-session.service.ts` | Add `chargeSavedPaymentMethod()` — creates PaymentIntent with `off_session: true, confirm: true` |
| New: `stripe-customer.controller.ts` | `POST /commerce/customers/:id/setup-intent` — creates SetupIntent. `GET /commerce/customers/:id/payment-methods` — lists saved cards |

### Frontend — New Files

| File | Purpose |
|------|---------|
| `components/cards/PaymentSetupCard.tsx` | Wraps Stripe `<Elements>` + `<PaymentElement />`, renders inline in chat. One-time card save. |
| `components/cards/AddressFormCard.tsx` | Inline pre-filled address form, renders in chat. Only shown when agent can't parse address conversationally. |

### Frontend — Modified Files

| File | Changes |
|------|---------|
| `components/MessageBubble.tsx` | Render PaymentSetupCard when message has `setup_intent_secret`; render AddressFormCard when message has `address_form_data` |
| `hooks/useChat.ts` | Handle checkout card actions (payment_setup_complete, address_submitted); send as `__checkout:` prefixed messages |
| `types/chat.types.ts` | Add `setup_intent_secret`, `address_form_data`, `checkout_action` fields to ChatMessageUI |
| `app/chat/page.tsx` | Remove Stripe redirect handling (lines 30-89) |
| `config/config.ts` | Add Stripe publishable key config |

### Frontend — Deleted Files

| File | Reason |
|------|--------|
| `components/CheckoutModal.tsx` | Replaced entirely by conversational flow |

### Frontend — New Dependencies

```
@stripe/stripe-js
@stripe/react-stripe-js
```

---

## 7. Mode Entry/Exit Logic

### Entry (in chat_service.py)

When commerce intent == "checkout_initiate":
1. Set `session.context["active_agent"] = "checkout"`
2. Set `session.context["checkout_entered_at"] = current_timestamp`
3. Load cart from commerce_client
4. Load customer profile (addresses from profile JSONB)
5. Load saved payment methods from stripe_customer_service
6. Load checkout-agent.md via skill_loader
7. Use CHECKOUT_TOOL_DEFINITIONS instead of TOOL_DEFINITIONS
8. First LLM call with full context

### Persistence Across Turns

At the start of every `send_message()`:
1. Check `session.context.get("active_agent") == "checkout"`
2. If yes: skip shopping flow (no RAG, no shopping tools)
3. Re-inject checkout agent prompt + FRESH context (addresses/cards may have changed since last turn)
4. Use CHECKOUT_TOOL_DEFINITIONS
5. Handle `__checkout:` prefixed messages by stripping prefix and injecting payload

### Exit

When checkout agent calls exit_checkout:
1. Delete `session.context["active_agent"]`
2. Delete `session.context["checkout_entered_at"]`
3. Save session context
4. Next message goes through normal shopping flow

### Timeout

If `checkout_entered_at` is more than 30 minutes ago:
1. Auto-clear active_agent
2. Inform user: "Your checkout session timed out. Your cart is saved."
3. Process current message through normal shopping flow
