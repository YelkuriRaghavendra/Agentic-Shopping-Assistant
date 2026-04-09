# Checkout Agent Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the modal-based checkout with a conversational checkout agent — everything inline in chat, no modals, no redirects.

**Architecture:** Mode-switch in the orchestrator. When checkout intent is detected, `session.context["active_agent"]` is set to `"checkout"`, the checkout agent prompt + checkout-specific tools are injected, and subsequent messages stay in checkout mode until the agent calls `exit_checkout`. Stripe Elements renders inline in chat for first-time card save only.

**Tech Stack:** Python/FastAPI (backend), Next.js/React (frontend), Stripe Elements (`@stripe/react-stripe-js`), OpenAI function-calling, SSE streaming.

**Spec:** `docs/superpowers/specs/2026-04-09-checkout-agent-design.md`

---

## File Map

### New Files

| File | Responsibility |
|------|---------------|
| `backend/app/agent/agents/checkout-agent.md` | Checkout agent system prompt |
| `backend/app/services/checkout_tools.py` | Checkout tool definitions + handler class |
| `backend/app/services/stripe_customer_service.py` | Stripe Customer CRUD, SetupIntent, list PaymentMethods |
| `backend/tests/test_checkout_agent.py` | Tests for checkout tools + mode switching |
| `checkout-order-service/src/modules/stripe/stripe-customer.controller.ts` | `POST setup-intent`, `GET payment-methods` endpoints |
| `checkout-order-service/src/modules/stripe/stripe-customer.service.ts` | Stripe Customer + SetupIntent + PaymentMethod logic |
| `Frontend/components/cards/PaymentSetupCard.tsx` | Inline Stripe PaymentElement card |
| `Frontend/components/cards/AddressFormCard.tsx` | Inline pre-filled address form card |

### Modified Files

| File | Changes |
|------|---------|
| `backend/app/services/chat_service.py` | Checkout mode detection, prompt/tool swap, `__checkout:` message handling, timeout |
| `backend/app/services/memory_service.py` | `active_agent` + `checkout_entered_at` in session context |
| `backend/app/clients/commerce_client.py` | `create_setup_intent()`, `list_payment_methods()`, `charge_saved_card()` |
| `checkout-order-service/src/modules/checkout/session/checkout-session.service.ts` | `chargeSavedPaymentMethod()` method |
| `checkout-order-service/src/modules/checkout/session/checkout.controller.ts` | `POST :id/charge-saved` endpoint |
| `Frontend/types/chat.types.ts` | `setup_intent_secret`, `address_form_data`, `checkout_action` fields |
| `Frontend/hooks/useChat.ts` | Handle `checkout_action` SSE events, send `__checkout:` messages |
| `Frontend/components/MessageBubble.tsx` | Render PaymentSetupCard + AddressFormCard inline |
| `Frontend/app/chat/page.tsx` | Remove Stripe redirect handling |
| `Frontend/config/config.ts` | Add Stripe publishable key |
| `Frontend/package.json` | Add `@stripe/stripe-js`, `@stripe/react-stripe-js` |

### Deleted Files

| File | Reason |
|------|--------|
| `Frontend/components/CheckoutModal.tsx` | Replaced by conversational flow |

---

## Task 1: Checkout Agent Prompt

**Files:**
- Create: `backend/app/agent/agents/checkout-agent.md`

- [ ] **Step 1: Create the checkout agent markdown file**

```markdown
# Agent: Checkout

## Role

You are a checkout assistant for Vikrai, an online fashion store.
You complete purchases on behalf of the customer with minimum friction.
You are NOT a shopping assistant — do not recommend products, do not
discuss style. If asked, say "Let me hand you back to our shopping
assistant" and call exit_checkout.

## Personality

- Concise and transactional — this is a checkout, not a conversation
- Confident — "I'll place that for you" not "Would you like me to try?"
- Transparent — always show what you're about to charge before charging
- Helpful on errors — don't just say "failed", explain what to do next

## Context (injected by orchestrator each turn)

You receive cart, customer, saved_addresses, and saved_payment_methods
as a JSON block in your system message. All prices are in paise
(Indian cents). 899900 paise = ₹8,999.00.

## Price Formatting

- Always ₹X,XXX.XX with comma separators
- Always ₹ symbol, never "Rs" or "INR"
- If grand_total_cents is 0 or missing → "Something doesn't look right
  with the pricing. Let me hand you back." → exit_checkout

## Decision Flow (think silently, don't show to user)

### Validate cart
- Empty → "Your cart is empty! Want me to help you find something?" → exit_checkout

### Assess what's available
- has_address = saved_addresses has ≥ 1 entry
- has_payment = saved_payment_methods has ≥ 1 entry
- default_address = is_default == true or first entry
- default_payment = is_default == true or first entry

### Present based on availability

**Has both:** Show full summary + "Shall I place it?"
```
Here's your order:

• {title} × {qty} — ₹{line_total}

Total: ₹{grand_total}

📍 {label} — {full_name}, {address_line}, {city} {pincode}
💳 {Brand} •••{last4}

Shall I place it?
```

Multiple addresses → use default + "(I can deliver elsewhere if you prefer)"
Multiple cards → use default + "(I can use a different card if you'd like)"

**Has address, no payment:** Show summary + "I'll need to save a payment
method." → call request_payment_setup

**Has payment, no address:** Show summary + "Where should I deliver this?"

**Has neither:** Show summary + "I'll need a delivery address and payment
method. Where should I deliver?"

## Address Parsing

**Complete (street + city + pincode):** Confirm back → yes → save_address
**Partial (1-2 missing):** Ask specifically for missing fields
**Vague (3+ missing):** call request_address_form with pre-filled fields
Use customer.name and customer.phone as defaults when available.

## Payment Setup Flow

1. Call request_payment_setup → frontend renders Stripe PaymentElement
2. On payment_setup_complete event → re-present summary + ask confirm
3. On payment_setup_failed → "That card was declined. Try another?"

## On User Confirmation ("yes", "place it", "go ahead", etc.)

1. Show: "Placing your order: {count} items, ₹{total} → {address}, {card}..."
2. Call place_order
3. Success:
```
✅ Order confirmed!

Order #{order_id}
{count} items • ₹{total}
📍 {address}
📦 Estimated delivery: {date}

You'll receive a confirmation at {email}.
```
Then exit_checkout.

4. Failure by type:
   - card_declined → offer different card
   - insufficient_funds → offer different card
   - out_of_stock → offer to remove item
   - session_expired → exit_checkout
   - commerce_unavailable → "Payment system temporarily down" → exit_checkout
   - unknown → retry once, then exit_checkout

## Handling Changes

**Address:** match saved label or parse new, re-confirm
**Payment:** match by brand or list saved, re-confirm
**Cart:** remove/update_quantity via update_cart, re-confirm
**Add item:** "Can't add during checkout" → exit_checkout
**Cancel:** "No problem! Cart saved." → exit_checkout
**Off-topic:** "Let me get you back to shopping." → exit_checkout

## Response Format

- Bullet (•) for items, not numbers
- Emoji: 📍 💳 ✅ 📦 ❌ only
- Never show internal IDs
- Never use tables
- Under 4 sentences except order summary
- Never reference own nature as AI/agent

## Edge Cases

- Deleted address/card between turns → re-prompt (context re-injected fresh)
- Image during checkout → "Can't process images. Back to shopping?"
- Empty/gibberish → "Didn't catch that. Place order or make changes?"
- Multiple rapid "yes" → only first place_order matters
- 0-quantity items → "Something looks off" → exit_checkout
```

Save this as `backend/app/agent/agents/checkout-agent.md`.

- [ ] **Step 2: Verify file loads via skill_loader**

Run: `cd backend && python -c "from app.agent.skill_loader import skill_loader; print(skill_loader.load_agent('checkout-agent')[:50])"`

Expected: First 50 chars of the prompt printed.

- [ ] **Step 3: Commit**

```bash
git add backend/app/agent/agents/checkout-agent.md
git commit -m "feat: add checkout agent prompt definition"
```

---

## Task 2: Checkout Tool Definitions + Handlers

**Files:**
- Create: `backend/app/services/checkout_tools.py`
- Test: `backend/tests/test_checkout_agent.py`

- [ ] **Step 1: Write failing tests for checkout tools**

Create `backend/tests/test_checkout_agent.py`:

```python
"""Tests for checkout agent tools."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.services.checkout_tools import CheckoutToolRegistry, CHECKOUT_TOOL_DEFINITIONS


class TestCheckoutToolDefinitions:
    """Verify tool definitions are well-formed."""

    def test_all_tools_present(self):
        names = [t["function"]["name"] for t in CHECKOUT_TOOL_DEFINITIONS]
        assert "place_order" in names
        assert "save_address" in names
        assert "request_payment_setup" in names
        assert "request_address_form" in names
        assert "update_cart" in names
        assert "exit_checkout" in names

    def test_place_order_requires_all_params(self):
        place = next(t for t in CHECKOUT_TOOL_DEFINITIONS if t["function"]["name"] == "place_order")
        required = place["function"]["parameters"]["required"]
        assert "checkout_session_id" in required
        assert "address_id" in required
        assert "payment_method_id" in required

    def test_exit_checkout_reason_enum(self):
        exit_tool = next(t for t in CHECKOUT_TOOL_DEFINITIONS if t["function"]["name"] == "exit_checkout")
        reason_prop = exit_tool["function"]["parameters"]["properties"]["reason"]
        assert "order_placed" in reason_prop["enum"]
        assert "user_cancelled" in reason_prop["enum"]


class TestCheckoutToolHandlers:
    """Test tool handler execution."""

    @pytest.fixture
    def registry(self):
        commerce = AsyncMock()
        customer_repo = AsyncMock()
        stripe_service = AsyncMock()
        return CheckoutToolRegistry(
            commerce_client=commerce,
            customer_repo=customer_repo,
            stripe_service=stripe_service,
        )

    @pytest.mark.asyncio
    async def test_place_order_calls_commerce(self, registry):
        registry._commerce.charge_saved_card.return_value = MagicMock(
            success=True,
            data={"ucpOrderId": "VIK-001", "estimatedDelivery": "2026-04-14"},
        )
        result = await registry.execute("place_order", {
            "checkout_session_id": "cs_123",
            "address_id": "addr_1",
            "payment_method_id": "pm_abc",
        })
        assert result.success is True
        assert result.data["order_id"] == "VIK-001"
        registry._commerce.charge_saved_card.assert_called_once()

    @pytest.mark.asyncio
    async def test_place_order_failure(self, registry):
        registry._commerce.charge_saved_card.return_value = MagicMock(
            success=False,
            error_code="card_declined",
            error_message="Your card was declined",
        )
        result = await registry.execute("place_order", {
            "checkout_session_id": "cs_123",
            "address_id": "addr_1",
            "payment_method_id": "pm_abc",
        })
        assert result.success is False
        assert result.data["error_code"] == "card_declined"

    @pytest.mark.asyncio
    async def test_save_address(self, registry):
        registry._customer_repo.update_profile = AsyncMock()
        result = await registry.execute("save_address", {
            "full_name": "Raghav",
            "address_line": "42 MG Road",
            "city": "Bangalore",
            "pincode": "560001",
        })
        assert result.success is True
        assert "addr_" in result.data["address_id"]

    @pytest.mark.asyncio
    async def test_request_payment_setup(self, registry):
        registry._stripe.create_setup_intent.return_value = {
            "client_secret": "seti_secret_123",
        }
        result = await registry.execute("request_payment_setup", {})
        assert result.success is True
        assert result.data["setup_intent_secret"] == "seti_secret_123"

    @pytest.mark.asyncio
    async def test_request_address_form(self, registry):
        result = await registry.execute("request_address_form", {
            "full_name": "Raghav",
            "city": "Bangalore",
        })
        assert result.success is True
        assert result.data["prefilled"]["full_name"] == "Raghav"

    @pytest.mark.asyncio
    async def test_update_cart_remove(self, registry):
        registry._commerce.update_checkout_session.return_value = MagicMock(
            success=True,
            data={"lineItemsSnapshot": [], "totalsSnapshot": {"grand_total_cents": 0}},
        )
        result = await registry.execute("update_cart", {
            "action": "remove",
            "product_id": "prod_1",
        })
        assert result.success is True

    @pytest.mark.asyncio
    async def test_exit_checkout(self, registry):
        result = await registry.execute("exit_checkout", {"reason": "user_cancelled"})
        assert result.success is True
        assert result.data["reason"] == "user_cancelled"

    @pytest.mark.asyncio
    async def test_unknown_tool(self, registry):
        result = await registry.execute("nonexistent_tool", {})
        assert result.success is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && OPENAI_API_KEY=sk-test pytest tests/test_checkout_agent.py -v`

Expected: FAIL — `ModuleNotFoundError: No module named 'app.services.checkout_tools'`

- [ ] **Step 3: Implement checkout_tools.py**

Create `backend/app/services/checkout_tools.py`:

```python
"""
Checkout tool registry.

Defines tools available to the checkout agent (replaces shopping tools
when checkout mode is active). Each tool maps to a handler method.

Tools:
  - place_order: charge saved card, create order
  - save_address: persist new address to customer profile
  - request_payment_setup: create Stripe SetupIntent for card save
  - request_address_form: signal frontend to render inline form
  - update_cart: remove item or change quantity
  - exit_checkout: hand back to shopping agent
"""

import time
import uuid
from dataclasses import dataclass
from typing import Any

from app.clients.commerce_client import CommerceClient
from app.core.logging import get_logger
from app.db.repositories import CustomerRepository

logger = get_logger(__name__)


@dataclass
class CheckoutToolResult:
    """Result from a checkout tool execution."""
    tool_name: str
    success: bool
    data: dict[str, Any]
    summary: str
    # Signals for frontend (sent via SSE checkout_action events)
    checkout_action: str | None = None


CHECKOUT_TOOL_DEFINITIONS: list[dict] = [
    {
        "type": "function",
        "function": {
            "name": "place_order",
            "description": (
                "Charge the saved card and place the order. "
                "Call ONLY after the user explicitly confirms."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "checkout_session_id": {"type": "string"},
                    "address_id": {"type": "string"},
                    "payment_method_id": {"type": "string"},
                },
                "required": ["checkout_session_id", "address_id", "payment_method_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "save_address",
            "description": "Save a new delivery address to customer profile.",
            "parameters": {
                "type": "object",
                "properties": {
                    "full_name":    {"type": "string"},
                    "address_line": {"type": "string"},
                    "city":         {"type": "string"},
                    "state":        {"type": "string"},
                    "pincode":      {"type": "string"},
                    "phone":        {"type": "string"},
                    "label":        {"type": "string", "description": "e.g. Home, Office"},
                },
                "required": ["full_name", "address_line", "city", "pincode"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "request_payment_setup",
            "description": (
                "Trigger inline Stripe card collection in the chat. "
                "Call when customer has no saved payment method or wants to add a new card."
            ),
            "parameters": {
                "type": "object",
                "properties": {},
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "request_address_form",
            "description": (
                "Render inline address form with pre-filled fields. "
                "Use when user gives a partial address missing 3+ fields."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "full_name":    {"type": "string"},
                    "address_line": {"type": "string"},
                    "city":         {"type": "string"},
                    "state":        {"type": "string"},
                    "pincode":      {"type": "string"},
                    "phone":        {"type": "string"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "update_cart",
            "description": "Modify cart: remove an item or change quantity.",
            "parameters": {
                "type": "object",
                "properties": {
                    "action":     {"type": "string", "enum": ["remove", "update_quantity"]},
                    "product_id": {"type": "string"},
                    "quantity":   {"type": "integer", "description": "New qty. Only for update_quantity."},
                },
                "required": ["action", "product_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "exit_checkout",
            "description": (
                "Hand control back to shopping assistant. "
                "Call when: order placed, user cancels, off-topic, cart empty, or error."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "reason": {
                        "type": "string",
                        "enum": [
                            "order_placed", "user_cancelled", "off_topic",
                            "cart_empty", "error", "payment_unsupported",
                        ],
                    },
                },
                "required": ["reason"],
            },
        },
    },
]


class CheckoutToolRegistry:
    """Execute checkout agent tool calls."""

    def __init__(
        self,
        commerce_client: CommerceClient,
        customer_repo: CustomerRepository,
        stripe_service: Any,  # StripeCustomerService
        customer_id: str | None = None,
        checkout_session_id: str | None = None,
    ):
        self._commerce = commerce_client
        self._customer_repo = customer_repo
        self._stripe = stripe_service
        self._customer_id = customer_id
        self._checkout_session_id = checkout_session_id

    async def execute(self, tool_name: str, args: dict) -> CheckoutToolResult:
        handler = getattr(self, f"_handle_{tool_name}", None)
        if not handler:
            return CheckoutToolResult(
                tool_name=tool_name,
                success=False,
                data={},
                summary=f"Unknown checkout tool: {tool_name}",
            )
        try:
            return await handler(args)
        except Exception as exc:
            logger.error("checkout_tools.handler_error", tool=tool_name, error=str(exc))
            return CheckoutToolResult(
                tool_name=tool_name,
                success=False,
                data={"error": str(exc)},
                summary=f"Checkout tool failed: {exc}",
            )

    async def _handle_place_order(self, args: dict) -> CheckoutToolResult:
        session_id = args.get("checkout_session_id", self._checkout_session_id or "")
        address_id = args.get("address_id", "")
        payment_method_id = args.get("payment_method_id", "")

        response = await self._commerce.charge_saved_card(
            session_id=session_id,
            payment_method_id=payment_method_id,
            address_id=address_id,
            customer_id=self._customer_id or "",
        )

        if response.success:
            order_id = response.data.get("ucpOrderId", session_id)
            delivery = response.data.get("estimatedDelivery", "5-7 business days")
            return CheckoutToolResult(
                tool_name="place_order",
                success=True,
                data={"order_id": order_id, "estimated_delivery": delivery},
                summary=f"Order {order_id} placed successfully.",
                checkout_action="order_placed",
            )
        return CheckoutToolResult(
            tool_name="place_order",
            success=False,
            data={
                "error_code": response.error_code or "unknown",
                "error_message": response.error_message or "Order placement failed",
            },
            summary=f"Order failed: {response.error_message}",
        )

    async def _handle_save_address(self, args: dict) -> CheckoutToolResult:
        address_id = f"addr_{int(time.time())}"
        address = {
            "id": address_id,
            "label": args.get("label", "Home"),
            "full_name": args["full_name"],
            "address_line": args["address_line"],
            "city": args["city"],
            "state": args.get("state", ""),
            "pincode": args["pincode"],
            "phone": args.get("phone", ""),
            "is_default": False,
        }

        if self._customer_id:
            try:
                profile = await self._customer_repo.get_profile(self._customer_id)
                existing = profile.get("addresses", []) if profile else []
                # First address becomes default
                if not existing:
                    address["is_default"] = True
                existing.append(address)
                await self._customer_repo.update_profile(
                    self._customer_id, {"addresses": existing}
                )
            except Exception as exc:
                logger.warning("checkout_tools.save_address_failed", error=str(exc))

        return CheckoutToolResult(
            tool_name="save_address",
            success=True,
            data={"address_id": address_id, "address": address},
            summary=f"Address saved: {address['address_line']}, {address['city']}",
        )

    async def _handle_request_payment_setup(self, args: dict) -> CheckoutToolResult:
        result = await self._stripe.create_setup_intent(self._customer_id or "")
        return CheckoutToolResult(
            tool_name="request_payment_setup",
            success=True,
            data={"setup_intent_secret": result["client_secret"]},
            summary="Payment setup requested. Waiting for card input.",
            checkout_action="payment_setup",
        )

    async def _handle_request_address_form(self, args: dict) -> CheckoutToolResult:
        prefilled = {
            k: v for k, v in args.items()
            if k in ("full_name", "address_line", "city", "state", "pincode", "phone") and v
        }
        return CheckoutToolResult(
            tool_name="request_address_form",
            success=True,
            data={"prefilled": prefilled},
            summary="Address form requested. Waiting for user input.",
            checkout_action="address_form",
        )

    async def _handle_update_cart(self, args: dict) -> CheckoutToolResult:
        action = args.get("action", "remove")
        product_id = args.get("product_id", "")
        session_id = self._checkout_session_id or ""

        # Fetch current session to get line items
        current = await self._commerce.get_checkout_session(session_id)
        if not current.success:
            return CheckoutToolResult(
                tool_name="update_cart",
                success=False,
                data={},
                summary="Could not load cart.",
            )

        line_items = current.data.get("lineItemsSnapshot", [])

        if action == "remove":
            line_items = [li for li in line_items if li.get("item", {}).get("id") != product_id]
        elif action == "update_quantity":
            qty = args.get("quantity", 1)
            for li in line_items:
                if li.get("item", {}).get("id") == product_id:
                    li["quantity"] = qty

        response = await self._commerce.update_checkout_session(
            session_id=session_id,
            line_items=line_items,
        )
        return CheckoutToolResult(
            tool_name="update_cart",
            success=response.success,
            data=response.data if response.success else {},
            summary="Cart updated." if response.success else "Failed to update cart.",
        )

    async def _handle_exit_checkout(self, args: dict) -> CheckoutToolResult:
        reason = args.get("reason", "user_cancelled")
        return CheckoutToolResult(
            tool_name="exit_checkout",
            success=True,
            data={"reason": reason},
            summary=f"Exiting checkout: {reason}",
            checkout_action="exit_checkout",
        )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && OPENAI_API_KEY=sk-test pytest tests/test_checkout_agent.py -v`

Expected: All 9 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/checkout_tools.py backend/tests/test_checkout_agent.py
git commit -m "feat: add checkout tool definitions and handlers with tests"
```

---

## Task 3: Stripe Customer Service (Backend)

**Files:**
- Create: `backend/app/services/stripe_customer_service.py`

- [ ] **Step 1: Create StripeCustomerService**

```python
"""
Stripe Customer service.

Manages the link between our customer_id and Stripe Customer objects.
Handles:
  - Creating/getting Stripe Customer
  - Creating SetupIntents (for saving cards)
  - Listing saved PaymentMethods
"""

from __future__ import annotations

import os
from typing import Any

from app.clients.commerce_client import CommerceClient
from app.core.logging import get_logger

logger = get_logger(__name__)

_COMMERCE_SERVICE_URL = os.environ.get("COMMERCE_SERVICE_URL", "http://localhost:3001")


class StripeCustomerService:
    """Proxies Stripe Customer operations through the checkout-order-service."""

    def __init__(self, commerce_client: CommerceClient | None = None):
        self._commerce = commerce_client or CommerceClient()

    async def create_setup_intent(self, customer_id: str) -> dict[str, str]:
        """
        Create a Stripe SetupIntent for saving a card.
        Returns: {"client_secret": "seti_xxx_secret_yyy"}
        """
        response = await self._commerce._commerce_post(
            f"/commerce/customers/{customer_id}/setup-intent",
            payload={},
        )
        if response.success:
            return {"client_secret": response.data.get("clientSecret", "")}
        raise RuntimeError(
            f"Failed to create SetupIntent: {response.error_message}"
        )

    async def list_payment_methods(self, customer_id: str) -> list[dict[str, Any]]:
        """
        List saved payment methods for a customer.
        Returns: [{"id": "pm_xxx", "brand": "visa", "last4": "4242", ...}]
        """
        response = await self._commerce._commerce_get(
            f"/commerce/customers/{customer_id}/payment-methods",
        )
        if response.success:
            return response.data.get("paymentMethods", [])
        logger.warning(
            "stripe_customer.list_payment_methods_failed",
            customer_id=customer_id,
            error=response.error_message,
        )
        return []

    async def charge_saved_card(
        self,
        session_id: str,
        payment_method_id: str,
        customer_id: str,
    ) -> dict[str, Any]:
        """
        Charge a saved payment method for a checkout session.
        Creates PaymentIntent with off_session=true, confirm=true.
        """
        response = await self._commerce._commerce_post(
            f"/commerce/checkout-sessions/{session_id}/charge-saved",
            payload={
                "payment_method_id": payment_method_id,
                "customer_id": customer_id,
            },
        )
        return response
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/services/stripe_customer_service.py
git commit -m "feat: add StripeCustomerService for payment method management"
```

---

## Task 4: Commerce Client — New Methods

**Files:**
- Modify: `backend/app/clients/commerce_client.py`

- [ ] **Step 1: Add charge_saved_card method to CommerceClient**

Add after the `cancel_checkout_session` method (around line 137):

```python
    async def charge_saved_card(
        self,
        session_id: str,
        payment_method_id: str,
        address_id: str,
        customer_id: str,
        request_id: str | None = None,
    ) -> CommerceResponse:
        """
        POST /commerce/checkout-sessions/:id/charge-saved
        Charges a saved PaymentMethod server-side (off_session).
        """
        payload: dict[str, Any] = {
            "payment_method_id": payment_method_id,
            "address_id": address_id,
            "customer_id": customer_id,
        }
        return await self._commerce_post(
            f"/commerce/checkout-sessions/{session_id}/charge-saved",
            payload,
            request_id,
        )
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/clients/commerce_client.py
git commit -m "feat: add charge_saved_card to commerce client"
```

---

## Task 5: Checkout Mode in Chat Service

**Files:**
- Modify: `backend/app/services/chat_service.py`
- Modify: `backend/app/services/memory_service.py`

This is the core integration — wiring the checkout agent into the orchestrator.

- [ ] **Step 1: Add checkout mode helpers to MemoryService**

In `backend/app/services/memory_service.py`, add these methods to the `MemoryService` class (after `persist_session_memory`):

```python
    def get_active_agent(self, session: Session) -> str | None:
        """Return the active agent name, or None for default shopping."""
        return (session.context or {}).get("active_agent")

    def get_checkout_entered_at(self, session: Session) -> float | None:
        """Return the timestamp when checkout mode was entered."""
        return (session.context or {}).get("checkout_entered_at")

    async def set_active_agent(
        self, session: Session, agent_name: str | None
    ) -> None:
        """Set or clear the active agent in session context."""
        if session.context is None:
            session.context = {}
        if agent_name:
            session.context["active_agent"] = agent_name
            session.context["checkout_entered_at"] = time.time()
        else:
            session.context.pop("active_agent", None)
            session.context.pop("checkout_entered_at", None)
        await self._session_repo.update_context(session.session_id, session.context)
```

Add `import time` at the top of the file if not present.

- [ ] **Step 2: Add checkout mode detection and routing in ChatService**

In `backend/app/services/chat_service.py`, add these imports at the top:

```python
from app.services.checkout_tools import (
    CheckoutToolRegistry,
    CHECKOUT_TOOL_DEFINITIONS,
    CheckoutToolResult,
)
from app.services.stripe_customer_service import StripeCustomerService
from app.agent.skill_loader import skill_loader
```

- [ ] **Step 3: Add checkout orchestration method to ChatService**

Add this method to the `ChatService` class (before `_handle_commerce_intent`):

```python
    async def _handle_checkout_mode(
        self,
        session: Session,
        request: ChatRequest,
        customer_profile: dict | None,
        conversation: ConversationHistory,
        t_start: float,
    ) -> ChatResponse | None:
        """
        Handle a message while checkout agent is active.
        Returns ChatResponse if handled, None to fall through to normal flow.
        """
        # Timeout check — 30 minutes
        entered_at = self._memory.get_checkout_entered_at(session)
        if entered_at and (time.time() - entered_at > 1800):
            await self._memory.set_active_agent(session, None)
            return await self._direct_response(
                session, request,
                "Your checkout session timed out. Your cart is saved for when you're ready!",
                "checkout_timeout", t_start,
            )

        customer_id = str(session.customer_id) if session.customer_id else ""

        # Load checkout context (fresh every turn)
        stripe_service = StripeCustomerService(self._commerce)
        cart_response = await self._commerce.get_checkout_session(
            (session.context or {}).get("checkout_session_id", "")
        )
        saved_addresses = (customer_profile or {}).get("addresses", [])
        saved_payments = await stripe_service.list_payment_methods(customer_id)

        cart_data = cart_response.data if cart_response.success else {}
        checkout_session_id = cart_data.get("sessionId", "")

        # Build checkout context JSON for the agent
        checkout_context = {
            "cart": {
                "checkout_session_id": checkout_session_id,
                "line_items": cart_data.get("lineItemsSnapshot", []),
                "totals": cart_data.get("totalsSnapshot", {}),
            },
            "customer": {
                "customer_id": customer_id,
                "name": (customer_profile or {}).get("name", ""),
                "email": (customer_profile or {}).get("email", ""),
                "phone": (customer_profile or {}).get("phone", ""),
            },
            "saved_addresses": saved_addresses,
            "saved_payment_methods": saved_payments,
        }

        # Handle __checkout: prefixed messages from frontend card actions
        message = request.message
        checkout_event = None
        if message.startswith("__checkout:"):
            event_type = message.split(":", 1)[1] if ":" in message else ""
            checkout_event = {"event": event_type}
            # The actual payload comes from request.filters (frontend sends it there)
            if request.filters:
                checkout_event.update(request.filters)
            message = f"[System event: {event_type}]"

        # Load checkout agent prompt
        agent_prompt = skill_loader.load_agent("checkout-agent")
        system_prompt = (
            agent_prompt
            + "\n\n## Current Checkout Context\n\n```json\n"
            + json.dumps(checkout_context, indent=2, default=str)
            + "\n```"
        )
        if checkout_event:
            system_prompt += (
                "\n\n## Incoming Event\n\n```json\n"
                + json.dumps(checkout_event, indent=2)
                + "\n```"
            )

        # History
        llm_history = [
            {"role": t["role"], "content": t["content"]}
            for t in conversation.recent_turns[-6:]
        ]

        # LLM tool decision with checkout tools
        try:
            tool_call = await self._llm.decide_tool(
                system_prompt=system_prompt,
                user_message=message,
                history=llm_history,
                tools=CHECKOUT_TOOL_DEFINITIONS,
            )
        except LLMError:
            return await self._error_response(session, request, t_start)

        # Execute checkout tool
        checkout_tools = CheckoutToolRegistry(
            commerce_client=self._commerce,
            customer_repo=self._customer_repo,
            stripe_service=stripe_service,
            customer_id=customer_id,
            checkout_session_id=checkout_session_id,
        )
        tool_result = await checkout_tools.execute(tool_call.tool_name, tool_call.tool_args)

        # Handle exit_checkout — clear mode
        if tool_call.tool_name == "exit_checkout":
            await self._memory.set_active_agent(session, None)

        # Generate response with tool result context
        try:
            llm_result = await self._llm.generate(
                system_prompt=system_prompt,
                user_message=message,
                history=llm_history,
                tool_result_summary=tool_result.summary,
                tool_name=tool_call.tool_name,
            )
        except LLMError:
            return await self._error_response(session, request, t_start)

        # Build response
        response = await self._direct_response(
            session, request, llm_result.content,
            f"checkout_{tool_call.tool_name}", t_start,
        )

        # Attach checkout_action for frontend SSE
        if tool_result.checkout_action:
            response.checkout_action = {
                "action": tool_result.checkout_action,
                **tool_result.data,
            }

        return response
```

- [ ] **Step 4: Wire checkout mode into handle() and handle_stream()**

In the `handle()` method (around line 307, after loading memory), add checkout mode check BEFORE the commerce intent classification:

```python
        # ── 7a. Checkout agent mode ────────────────────────────────────────
        if self._memory.get_active_agent(session) == "checkout":
            checkout_response = await self._handle_checkout_mode(
                session=session,
                request=request,
                customer_profile=customer_profile,
                conversation=conversation,
                t_start=t_start,
            )
            if checkout_response is not None:
                return checkout_response
```

In the commerce intent handler (the `_handle_commerce_intent` method), when `commerce_intent == "checkout_initiate"`, INSTEAD of the current flow, enter checkout mode:

At the top of `_handle_commerce_intent`, add:

```python
        # Enter checkout agent mode for checkout_initiate
        if commerce_intent == "checkout_initiate":
            # Store the checkout session ID in session context
            commerce_slots = await self._extract_commerce_slots(
                message=message, intent=commerce_intent, session=session,
            )
            # Create or get checkout session
            try:
                service_response = await self._dispatch_commerce_intent(
                    intent=commerce_intent, slots=commerce_slots,
                    customer_id=customer_id_str or "", request_id=str(session.session_id),
                    session=session,
                )
                if service_response.success and service_response.data:
                    session_id = (
                        service_response.data.get("sessionId")
                        or service_response.data.get("session_id", "")
                    )
                    if session.context is None:
                        session.context = {}
                    session.context["checkout_session_id"] = session_id
            except Exception as exc:
                logger.warning("chat.checkout_session_create_failed", error=str(exc))

            await self._memory.set_active_agent(session, "checkout")
            # Now handle as checkout mode
            return await self._handle_checkout_mode(
                session=session, request=request,
                customer_profile=customer_profile,
                conversation=ConversationHistory(
                    recent_turns=[
                        {"role": t["role"], "content": t["content"]}
                        for t in (await self._load_history(session)).recent_turns
                    ]
                ),
                t_start=t_start,
            )
```

- [ ] **Step 5: Add checkout_action field to ChatResponse DTO**

In `backend/app/api/dto/chat_dto.py`, add to the `ChatResponse` class:

```python
    checkout_action: dict | None = None
```

- [ ] **Step 6: Wire checkout_action into SSE stream**

In the `handle_stream` method of `chat_service.py`, in the section that builds the `done_event` dict (around line 765-780), add:

```python
                if commerce_response.checkout_action:
                    done_event["checkout_action"] = commerce_response.checkout_action
```

Also add similar handling for the checkout mode path in streaming (replicate the `_handle_checkout_mode` logic for the stream path, emitting SSE events for tool results).

- [ ] **Step 7: Run existing tests to check nothing broke**

Run: `cd backend && OPENAI_API_KEY=sk-test pytest tests/ -v --timeout=30`

Expected: All existing tests still pass.

- [ ] **Step 8: Commit**

```bash
git add backend/app/services/chat_service.py backend/app/services/memory_service.py backend/app/api/dto/chat_dto.py
git commit -m "feat: wire checkout agent mode into orchestrator"
```

---

## Task 6: Checkout-Order-Service — Charge Saved Card + Setup Intent

**Files:**
- Create: `checkout-order-service/src/modules/stripe/stripe-customer.controller.ts`
- Create: `checkout-order-service/src/modules/stripe/stripe-customer.service.ts`
- Modify: `checkout-order-service/src/modules/checkout/session/checkout-session.service.ts`
- Modify: `checkout-order-service/src/modules/checkout/session/checkout.controller.ts`

- [ ] **Step 1: Create StripeCustomerService**

Create `checkout-order-service/src/modules/stripe/stripe-customer.service.ts`:

```typescript
import { Injectable, Logger } from '@nestjs/common';
import Stripe from 'stripe';

@Injectable()
export class StripeCustomerService {
  private readonly logger = new Logger(StripeCustomerService.name);

  constructor(private readonly stripe: Stripe) {}

  /**
   * Get or create a Stripe Customer for our internal customer ID.
   * Uses metadata.internal_customer_id to link.
   */
  async getOrCreateCustomer(customerId: string): Promise<string> {
    const existing = await this.stripe.customers.search({
      query: `metadata['internal_customer_id']:'${customerId}'`,
      limit: 1,
    });

    if (existing.data.length > 0) {
      return existing.data[0].id;
    }

    const customer = await this.stripe.customers.create({
      metadata: { internal_customer_id: customerId },
    });
    return customer.id;
  }

  /**
   * Create a SetupIntent for saving a card.
   */
  async createSetupIntent(customerId: string): Promise<{ clientSecret: string }> {
    const stripeCustomerId = await this.getOrCreateCustomer(customerId);
    const setupIntent = await this.stripe.setupIntents.create({
      customer: stripeCustomerId,
      payment_method_types: ['card'],
      metadata: { internal_customer_id: customerId },
    });

    return { clientSecret: setupIntent.client_secret! };
  }

  /**
   * List saved payment methods for a customer.
   */
  async listPaymentMethods(
    customerId: string,
  ): Promise<{ paymentMethods: Array<Record<string, unknown>> }> {
    const stripeCustomerId = await this.getOrCreateCustomer(customerId);
    const methods = await this.stripe.paymentMethods.list({
      customer: stripeCustomerId,
      type: 'card',
    });

    return {
      paymentMethods: methods.data.map((pm) => ({
        id: pm.id,
        type: pm.type,
        brand: pm.card?.brand ?? 'unknown',
        last4: pm.card?.last4 ?? '****',
        exp_month: pm.card?.exp_month,
        exp_year: pm.card?.exp_year,
        is_default: false, // TODO: track default in our DB
      })),
    };
  }

  /**
   * Charge a saved payment method off-session.
   */
  async chargeSavedCard(
    amountCents: number,
    paymentMethodId: string,
    customerId: string,
    metadata: Record<string, string>,
  ): Promise<Stripe.PaymentIntent> {
    const stripeCustomerId = await this.getOrCreateCustomer(customerId);

    const paymentIntent = await this.stripe.paymentIntents.create({
      amount: amountCents,
      currency: 'inr',
      customer: stripeCustomerId,
      payment_method: paymentMethodId,
      off_session: true,
      confirm: true,
      metadata,
    });

    return paymentIntent;
  }
}
```

- [ ] **Step 2: Create StripeCustomerController**

Create `checkout-order-service/src/modules/stripe/stripe-customer.controller.ts`:

```typescript
import { Controller, Post, Get, Param, Body, HttpCode, HttpStatus } from '@nestjs/common';
import { StripeCustomerService } from './stripe-customer.service';

@Controller('commerce/customers')
export class StripeCustomerController {
  constructor(private readonly stripeCustomerService: StripeCustomerService) {}

  @Post(':customerId/setup-intent')
  @HttpCode(HttpStatus.OK)
  async createSetupIntent(
    @Param('customerId') customerId: string,
  ): Promise<{ clientSecret: string }> {
    return this.stripeCustomerService.createSetupIntent(customerId);
  }

  @Get(':customerId/payment-methods')
  async listPaymentMethods(
    @Param('customerId') customerId: string,
  ): Promise<{ paymentMethods: Array<Record<string, unknown>> }> {
    return this.stripeCustomerService.listPaymentMethods(customerId);
  }
}
```

- [ ] **Step 3: Add chargeSavedPaymentMethod to CheckoutSessionService**

In `checkout-order-service/src/modules/checkout/session/checkout-session.service.ts`, add:

```typescript
  async chargeSavedPaymentMethod(
    sessionId: string,
    paymentMethodId: string,
    customerId: string,
  ): Promise<CheckoutSession> {
    const session = await this.loadSession(sessionId);
    this.assertNotCanceled(session);

    const amount = session.totalsSnapshot?.grand_total_cents ?? 0;
    if (amount <= 0) {
      throw new BadRequestException('Invalid order amount');
    }

    const stripeCustomerService = new StripeCustomerService(this.stripe);
    const paymentIntent = await stripeCustomerService.chargeSavedCard(
      amount,
      paymentMethodId,
      customerId,
      { checkout_session_id: sessionId },
    );

    session.stripePaymentIntentId = paymentIntent.id;
    session.stripeClientSecret = paymentIntent.client_secret ?? null;
    session.ucpStatus = UcpCheckoutStatus.COMPLETED;
    if (!session.ucpOrderId) {
      session.ucpOrderId = randomUUID();
    }
    await this.sessionRepo.save(session);
    await this.handleCompleted(session);

    return session;
  }
```

- [ ] **Step 4: Add charge-saved endpoint to CheckoutController**

In `checkout-order-service/src/modules/checkout/session/checkout.controller.ts`, add:

```typescript
  @Post(':id/charge-saved')
  @HttpCode(HttpStatus.OK)
  async chargeSavedCard(
    @Param('id') id: string,
    @Body() body: { payment_method_id: string; customer_id: string },
  ): Promise<CheckoutSession> {
    return this.checkoutSessionService.chargeSavedPaymentMethod(
      id,
      body.payment_method_id,
      body.customer_id,
    );
  }
```

- [ ] **Step 5: Register new providers in app module**

Add `StripeCustomerService` and `StripeCustomerController` to the relevant NestJS module's `providers` and `controllers` arrays.

- [ ] **Step 6: Commit**

```bash
git add checkout-order-service/src/modules/stripe/stripe-customer.service.ts \
      checkout-order-service/src/modules/stripe/stripe-customer.controller.ts \
      checkout-order-service/src/modules/checkout/session/checkout-session.service.ts \
      checkout-order-service/src/modules/checkout/session/checkout.controller.ts
git commit -m "feat: add charge-saved-card and setup-intent endpoints"
```

---

## Task 7: Frontend — Types + Stripe Setup

**Files:**
- Modify: `Frontend/types/chat.types.ts`
- Modify: `Frontend/config/config.ts`
- Modify: `Frontend/package.json`

- [ ] **Step 1: Install Stripe dependencies**

```bash
cd Frontend && npm install @stripe/stripe-js @stripe/react-stripe-js
```

- [ ] **Step 2: Add checkout fields to ChatMessageUI**

In `Frontend/types/chat.types.ts`, add these fields to `ChatMessageUI` (after `orderHistoryData`):

```typescript
  /** Stripe SetupIntent secret — triggers inline card collection */
  setupIntentSecret?: string;
  /** Pre-filled address data — triggers inline address form */
  addressFormData?: {
    full_name?: string;
    address_line?: string;
    city?: string;
    state?: string;
    pincode?: string;
    phone?: string;
  };
  /** Checkout action from agent (payment_setup, address_form, order_placed, exit_checkout) */
  checkoutAction?: {
    action: string;
    [key: string]: unknown;
  };
```

- [ ] **Step 3: Add Stripe publishable key to config**

In `Frontend/config/config.ts`, add:

```typescript
export const stripePublishableKey =
  process.env.NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY || "";
```

- [ ] **Step 4: Commit**

```bash
git add Frontend/types/chat.types.ts Frontend/config/config.ts Frontend/package.json Frontend/package-lock.json
git commit -m "feat: add checkout types and Stripe config"
```

---

## Task 8: Frontend — PaymentSetupCard Component

**Files:**
- Create: `Frontend/components/cards/PaymentSetupCard.tsx`

- [ ] **Step 1: Create PaymentSetupCard**

```tsx
"use client";

import { useState } from "react";
import { loadStripe } from "@stripe/stripe-js";
import { Elements, PaymentElement, useStripe, useElements } from "@stripe/react-stripe-js";
import { stripePublishableKey } from "@/config/config";

const stripePromise = stripePublishableKey ? loadStripe(stripePublishableKey) : null;

interface PaymentSetupCardProps {
  clientSecret: string;
  onComplete: (paymentMethod: { id: string; brand: string; last4: string; exp_month: number; exp_year: number }) => void;
  onError: (reason: string) => void;
}

function SetupForm({ onComplete, onError }: Omit<PaymentSetupCardProps, "clientSecret">) {
  const stripe = useStripe();
  const elements = useElements();
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!stripe || !elements) return;

    setIsSubmitting(true);
    setError(null);

    const { error: setupError, setupIntent } = await stripe.confirmSetup({
      elements,
      redirect: "if_required",
    });

    if (setupError) {
      setError(setupError.message ?? "Card setup failed");
      setIsSubmitting(false);
      onError(setupError.code ?? "card_declined");
      return;
    }

    if (setupIntent?.status === "succeeded" && setupIntent.payment_method) {
      // Fetch the payment method details
      const pmId = typeof setupIntent.payment_method === "string"
        ? setupIntent.payment_method
        : setupIntent.payment_method.id;

      onComplete({
        id: pmId,
        brand: "card",
        last4: "****",
        exp_month: 0,
        exp_year: 0,
      });
    }
    setIsSubmitting(false);
  };

  return (
    <form onSubmit={handleSubmit} style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
      <PaymentElement
        options={{
          layout: "tabs",
        }}
      />
      {error && (
        <p style={{ color: "#f87171", fontSize: "11px", margin: 0 }}>{error}</p>
      )}
      <button
        type="submit"
        disabled={!stripe || isSubmitting}
        style={{
          background: "#1D9E75",
          color: "#000",
          border: "none",
          borderRadius: "4px",
          padding: "12px",
          fontFamily: "var(--font-josefin)",
          fontWeight: 700,
          fontSize: "12px",
          letterSpacing: "2px",
          textTransform: "uppercase",
          cursor: isSubmitting ? "not-allowed" : "pointer",
          opacity: isSubmitting ? 0.5 : 1,
        }}
      >
        {isSubmitting ? "Saving..." : "Save Card"}
      </button>
    </form>
  );
}

export function PaymentSetupCard({ clientSecret, onComplete, onError }: PaymentSetupCardProps) {
  if (!stripePromise) {
    return (
      <div style={{ color: "#f87171", fontSize: "12px", padding: "16px" }}>
        Stripe is not configured. Please set NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY.
      </div>
    );
  }

  return (
    <div
      style={{
        background: "rgba(255,255,255,0.02)",
        border: "1px solid rgba(29,158,117,0.2)",
        borderRadius: "12px",
        padding: "16px",
        maxWidth: "400px",
      }}
    >
      <div style={{ display: "flex", alignItems: "center", gap: "6px", marginBottom: "12px" }}>
        <span style={{ fontSize: "14px" }}>💳</span>
        <span
          style={{
            fontFamily: "var(--font-mono)",
            fontSize: "9px",
            textTransform: "uppercase",
            letterSpacing: "1.5px",
            color: "rgba(29,158,117,0.8)",
          }}
        >
          Save Payment Method
        </span>
      </div>
      <Elements
        stripe={stripePromise}
        options={{
          clientSecret,
          appearance: {
            theme: "night",
            variables: {
              colorPrimary: "#1D9E75",
              colorBackground: "#0C0C0F",
              colorText: "rgba(255,255,255,0.8)",
              borderRadius: "8px",
              fontFamily: "var(--font-inter)",
            },
          },
        }}
      >
        <SetupForm onComplete={onComplete} onError={onError} />
      </Elements>
      <p
        style={{
          color: "rgba(255,255,255,0.2)",
          fontSize: "9px",
          textAlign: "center",
          marginTop: "8px",
          fontFamily: "var(--font-mono)",
        }}
      >
        Secured by Stripe. Card saved for future orders.
      </p>
    </div>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add Frontend/components/cards/PaymentSetupCard.tsx
git commit -m "feat: add inline PaymentSetupCard with Stripe Elements"
```

---

## Task 9: Frontend — AddressFormCard Component

**Files:**
- Create: `Frontend/components/cards/AddressFormCard.tsx`

- [ ] **Step 1: Create AddressFormCard**

```tsx
"use client";

import { useState, type FormEvent } from "react";

interface AddressFormCardProps {
  prefilled?: {
    full_name?: string;
    address_line?: string;
    city?: string;
    state?: string;
    pincode?: string;
    phone?: string;
  };
  onSubmit: (address: {
    full_name: string;
    address_line: string;
    city: string;
    state: string;
    pincode: string;
    phone: string;
  }) => void;
}

const inputStyle = {
  background: "rgba(255,255,255,0.03)",
  border: "1px solid rgba(255,255,255,0.09)",
  borderRadius: "8px",
  color: "rgba(255,255,255,0.65)",
  fontFamily: "var(--font-inter)",
  fontWeight: 300,
  fontSize: "13px",
  padding: "10px 12px",
  outline: "none",
  width: "100%",
};

const labelStyle = {
  fontFamily: "var(--font-mono)",
  fontSize: "9px",
  textTransform: "uppercase" as const,
  letterSpacing: "1.5px",
  color: "rgba(29,158,117,0.8)",
};

export function AddressFormCard({ prefilled = {}, onSubmit }: AddressFormCardProps) {
  const [fullName, setFullName] = useState(prefilled.full_name ?? "");
  const [addressLine, setAddressLine] = useState(prefilled.address_line ?? "");
  const [city, setCity] = useState(prefilled.city ?? "");
  const [state, setState] = useState(prefilled.state ?? "");
  const [pincode, setPincode] = useState(prefilled.pincode ?? "");
  const [phone, setPhone] = useState(prefilled.phone ?? "");

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault();
    if (!fullName.trim() || !addressLine.trim() || !city.trim() || !pincode.trim()) return;
    onSubmit({
      full_name: fullName.trim(),
      address_line: addressLine.trim(),
      city: city.trim(),
      state: state.trim(),
      pincode: pincode.trim(),
      phone: phone.trim(),
    });
  };

  const isValid = fullName.trim() && addressLine.trim() && city.trim() && pincode.trim();

  return (
    <div
      style={{
        background: "rgba(255,255,255,0.02)",
        border: "1px solid rgba(29,158,117,0.2)",
        borderRadius: "12px",
        padding: "16px",
        maxWidth: "400px",
      }}
    >
      <div style={{ display: "flex", alignItems: "center", gap: "6px", marginBottom: "12px" }}>
        <span style={{ fontSize: "14px" }}>📍</span>
        <span style={labelStyle}>Delivery Address</span>
      </div>
      <form onSubmit={handleSubmit} style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
        <div style={{ display: "flex", flexDirection: "column", gap: "4px" }}>
          <label style={labelStyle}>Full Name *</label>
          <input value={fullName} onChange={(e) => setFullName(e.target.value)} placeholder="John Doe" required style={inputStyle} />
        </div>
        <div style={{ display: "flex", flexDirection: "column", gap: "4px" }}>
          <label style={labelStyle}>Address *</label>
          <input value={addressLine} onChange={(e) => setAddressLine(e.target.value)} placeholder="123 Main Street" required style={inputStyle} />
        </div>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "8px" }}>
          <div style={{ display: "flex", flexDirection: "column", gap: "4px" }}>
            <label style={labelStyle}>City *</label>
            <input value={city} onChange={(e) => setCity(e.target.value)} placeholder="Mumbai" required style={inputStyle} />
          </div>
          <div style={{ display: "flex", flexDirection: "column", gap: "4px" }}>
            <label style={labelStyle}>State</label>
            <input value={state} onChange={(e) => setState(e.target.value)} placeholder="Maharashtra" style={inputStyle} />
          </div>
        </div>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "8px" }}>
          <div style={{ display: "flex", flexDirection: "column", gap: "4px" }}>
            <label style={labelStyle}>Pincode *</label>
            <input value={pincode} onChange={(e) => setPincode(e.target.value)} placeholder="400001" required style={inputStyle} />
          </div>
          <div style={{ display: "flex", flexDirection: "column", gap: "4px" }}>
            <label style={labelStyle}>Phone</label>
            <input value={phone} onChange={(e) => setPhone(e.target.value)} placeholder="+91 98765 43210" style={inputStyle} />
          </div>
        </div>
        <button
          type="submit"
          disabled={!isValid}
          style={{
            background: "#1D9E75",
            color: "#000",
            border: "none",
            borderRadius: "4px",
            padding: "12px",
            fontFamily: "var(--font-josefin)",
            fontWeight: 700,
            fontSize: "12px",
            letterSpacing: "2px",
            textTransform: "uppercase",
            cursor: isValid ? "pointer" : "not-allowed",
            opacity: isValid ? 1 : 0.4,
            marginTop: "4px",
          }}
        >
          Save Address
        </button>
      </form>
    </div>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add Frontend/components/cards/AddressFormCard.tsx
git commit -m "feat: add inline AddressFormCard component"
```

---

## Task 10: Frontend — Wire Cards into MessageBubble + useChat

**Files:**
- Modify: `Frontend/components/MessageBubble.tsx`
- Modify: `Frontend/hooks/useChat.ts`

- [ ] **Step 1: Add card rendering to MessageBubble**

In `Frontend/components/MessageBubble.tsx`, add imports at the top:

```tsx
import { PaymentSetupCard } from "@/components/cards/PaymentSetupCard";
import { AddressFormCard } from "@/components/cards/AddressFormCard";
```

Add `onCheckoutAction` to the props interface:

```tsx
export interface MessageBubbleProps {
  message: ChatMessageUI;
  onSelectProduct?: (productId: string, productName: string) => void;
  onSelectSuggestion?: (message: string) => void;
  onCompareProducts?: (products: ProductCardDTO[]) => void;
  onCheckout?: (message: ChatMessageUI) => void;
  onCheckoutAction?: (action: string, payload: Record<string, unknown>) => void;
}
```

After the OrderConfirmationCard block (line 114) and BEFORE the old Checkout CTA block (line 117), add:

```tsx
        {/* Inline Payment Setup Card */}
        {!isUser && message.setupIntentSecret && onCheckoutAction && (
          <PaymentSetupCard
            clientSecret={message.setupIntentSecret}
            onComplete={(pm) => onCheckoutAction("payment_setup_complete", { payment_method: pm })}
            onError={(reason) => onCheckoutAction("payment_setup_failed", { reason })}
          />
        )}

        {/* Inline Address Form Card */}
        {!isUser && message.addressFormData && onCheckoutAction && (
          <AddressFormCard
            prefilled={message.addressFormData}
            onSubmit={(addr) => onCheckoutAction("address_submitted", addr)}
          />
        )}
```

Remove the old Checkout CTA button block (lines 117-130 — the "Proceed to Checkout" button that opened the modal).

- [ ] **Step 2: Handle checkout_action SSE events in useChat**

In `Frontend/hooks/useChat.ts`, in the SSE event parsing (both the `done` event handler around line 432 and the buffer processing around line 384), add handling for `checkout_action`:

```typescript
// Inside the done event handler, after setting streamDone:
if (event.checkout_action) {
  const action = event.checkout_action;
  // Map checkout actions to message fields
  const updates: Partial<ChatMessageUI> = {};
  if (action.action === "payment_setup" && action.setup_intent_secret) {
    updates.setupIntentSecret = action.setup_intent_secret as string;
  }
  if (action.action === "address_form" && action.prefilled) {
    updates.addressFormData = action.prefilled as ChatMessageUI["addressFormData"];
  }
  // Apply updates to message
  setMessages((prev) =>
    prev.map((m) =>
      m.id === botId ? { ...m, ...updates } : m
    )
  );
}
```

- [ ] **Step 3: Add sendCheckoutAction helper to useChat**

Add a new function in `useChat` that card components call:

```typescript
const sendCheckoutAction = useCallback(
  (action: string, payload: Record<string, unknown>) => {
    const message = `__checkout:${action}`;
    // Send as a regular message but with payload in filters
    const body: ChatRequest = {
      message,
      customer_id: customerId || undefined,
      session_id: activeSessionId || undefined,
      channel: "web",
      filters: payload,
    };
    // Use the same sendMessage flow
    sendMessage(message);
  },
  [customerId, activeSessionId, sendMessage]
);
```

Expose `sendCheckoutAction` in the return value and `UseChatReturn` interface.

- [ ] **Step 4: Pass onCheckoutAction through ChatWindow to MessageBubble**

In `Frontend/components/ChatWindow.tsx`, pass the handler:

```tsx
<MessageBubble
  message={message}
  onSelectProduct={...}
  onSelectSuggestion={...}
  onCompareProducts={...}
  onCheckout={handleCheckout}
  onCheckoutAction={chat.sendCheckoutAction}
/>
```

- [ ] **Step 5: Commit**

```bash
git add Frontend/components/MessageBubble.tsx Frontend/hooks/useChat.ts Frontend/components/ChatWindow.tsx
git commit -m "feat: wire checkout cards into chat message rendering"
```

---

## Task 11: Frontend — Remove CheckoutModal + Stripe Redirect

**Files:**
- Delete: `Frontend/components/CheckoutModal.tsx`
- Modify: `Frontend/app/chat/page.tsx`
- Modify: `Frontend/components/ChatWindow.tsx`

- [ ] **Step 1: Remove CheckoutModal import and usage from ChatWindow**

In `Frontend/components/ChatWindow.tsx`:
- Remove `import { CheckoutModal } from "./CheckoutModal";`
- Remove `checkoutOpen` and `checkoutData` state variables
- Remove the `<CheckoutModal>` component render block
- Remove the `handleCheckout` function (or simplify it — the checkout agent handles it now)

- [ ] **Step 2: Remove Stripe redirect handling from chat page**

In `Frontend/app/chat/page.tsx`:
- Remove the `pendingCheckoutId` state and both `useEffect` blocks that handle Stripe redirect (lines 31-89)
- Remove `localStorage.getItem("pending_payment_chat_session")` logic

- [ ] **Step 3: Delete CheckoutModal.tsx**

```bash
rm Frontend/components/CheckoutModal.tsx
```

- [ ] **Step 4: Verify build**

```bash
cd Frontend && npm run build
```

Expected: Build succeeds with no errors.

- [ ] **Step 5: Commit**

```bash
git add -A Frontend/
git commit -m "feat: remove CheckoutModal and Stripe redirect in favor of conversational checkout"
```

---

## Task 12: Integration Test — End-to-End Checkout Flow

**Files:**
- Modify: `backend/tests/test_checkout_agent.py`

- [ ] **Step 1: Add integration test for checkout mode entry/exit**

```python
class TestCheckoutModeIntegration:
    """Test checkout mode switching in session context."""

    @pytest.mark.asyncio
    async def test_checkout_mode_entry(self):
        """Verify session context gets active_agent set."""
        from app.services.memory_service import MemoryService
        from unittest.mock import AsyncMock, MagicMock

        session = MagicMock()
        session.context = {}
        session.session_id = "test-session"

        session_repo = AsyncMock()
        session_repo.update_context = AsyncMock()
        customer_repo = AsyncMock()

        memory = MemoryService(session_repo, customer_repo)
        await memory.set_active_agent(session, "checkout")

        assert session.context["active_agent"] == "checkout"
        assert "checkout_entered_at" in session.context
        session_repo.update_context.assert_called_once()

    @pytest.mark.asyncio
    async def test_checkout_mode_exit(self):
        """Verify session context clears active_agent."""
        from app.services.memory_service import MemoryService
        from unittest.mock import AsyncMock, MagicMock

        session = MagicMock()
        session.context = {"active_agent": "checkout", "checkout_entered_at": 1000}
        session.session_id = "test-session"

        session_repo = AsyncMock()
        session_repo.update_context = AsyncMock()
        customer_repo = AsyncMock()

        memory = MemoryService(session_repo, customer_repo)
        await memory.set_active_agent(session, None)

        assert "active_agent" not in session.context
        assert "checkout_entered_at" not in session.context

    def test_get_active_agent(self):
        """Verify active agent detection."""
        from app.services.memory_service import MemoryService
        from unittest.mock import MagicMock

        session = MagicMock()
        session.context = {"active_agent": "checkout"}

        memory = MemoryService(MagicMock(), MagicMock())
        assert memory.get_active_agent(session) == "checkout"

        session.context = {}
        assert memory.get_active_agent(session) is None

        session.context = None
        assert memory.get_active_agent(session) is None
```

- [ ] **Step 2: Run all tests**

```bash
cd backend && OPENAI_API_KEY=sk-test pytest tests/test_checkout_agent.py -v
```

Expected: All tests PASS.

- [ ] **Step 3: Commit**

```bash
git add backend/tests/test_checkout_agent.py
git commit -m "test: add checkout mode integration tests"
```

---

## Task 13: Final Verification

- [ ] **Step 1: Run full backend test suite**

```bash
cd backend && OPENAI_API_KEY=sk-test pytest tests/ -v --timeout=30
```

Expected: All tests pass, no regressions.

- [ ] **Step 2: Run frontend build**

```bash
cd Frontend && npm run build
```

Expected: Clean build, no type errors.

- [ ] **Step 3: Run frontend lint**

```bash
cd Frontend && npm run lint
```

Expected: No errors.

- [ ] **Step 4: Verify deleted CheckoutModal has no remaining imports**

```bash
cd Frontend && grep -r "CheckoutModal" --include="*.tsx" --include="*.ts" .
```

Expected: No results.

- [ ] **Step 5: Final commit**

```bash
git add -A
git commit -m "chore: final cleanup for conversational checkout agent"
```
