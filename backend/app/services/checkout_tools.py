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
                "Use by default whenever checkout needs a delivery address and none is saved yet. "
                "Also use when the user gives a partial address."
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
                    "action": {
                        "type": "string",
                        "enum": ["remove", "update_quantity"],
                    },
                    "product_id": {"type": "string"},
                    "quantity": {
                        "type": "integer",
                        "description": "New qty. Only for update_quantity.",
                    },
                },
                "required": ["action", "product_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "direct_answer",
            "description": (
                "Respond directly to the customer without calling another tool. "
                "Use for presenting order summaries, confirming addresses, "
                "asking questions, or any conversational response."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "content": {"type": "string"},
                },
                "required": ["content"],
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
                            "order_placed",
                            "user_cancelled",
                            "off_topic",
                            "cart_empty",
                            "error",
                            "payment_unsupported",
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
        stripe_service: Any,
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
            # charge-saved now returns clientSecret for 3DS confirmation
            client_secret = response.data.get("clientSecret", "")
            payment_intent_id = response.data.get("paymentIntentId", "")

            if client_secret:
                # Frontend needs to confirm payment (3DS flow)
                return CheckoutToolResult(
                    tool_name="place_order",
                    success=True,
                    data={
                        "payment_intent_secret": client_secret,
                        "payment_intent_id": payment_intent_id,
                        "checkout_session_id": session_id,
                    },
                    summary="Payment created. Customer needs to confirm payment (3DS may be required).",
                    checkout_action="confirm_payment",
                )

            # Direct success (no 3DS needed)
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
                customer_uuid = uuid.UUID(self._customer_id)
                customer = await self._customer_repo.get_by_id(customer_uuid)
                if not customer:
                    return CheckoutToolResult(
                        tool_name="save_address",
                        success=False,
                        data={"error": "Customer not found."},
                        summary="Could not save address because the customer record was not found.",
                    )

                profile = customer.profile or {}
                existing = list(profile.get("addresses", []))
                if not existing:
                    address["is_default"] = True
                existing.append(address)
                await self._customer_repo.update_profile(
                    customer_uuid, {"addresses": existing}
                )
            except Exception as exc:
                logger.warning("checkout_tools.save_address_failed", error=str(exc))
                return CheckoutToolResult(
                    tool_name="save_address",
                    success=False,
                    data={"error": str(exc)},
                    summary=f"Could not save address: {exc}",
                )

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
            line_items = [
                li for li in line_items
                if li.get("item", {}).get("id") != product_id
            ]
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

    async def _handle_direct_answer(self, args: dict) -> CheckoutToolResult:
        content = args.get("content", "")
        return CheckoutToolResult(
            tool_name="direct_answer",
            success=True,
            data={"content": content},
            summary=content,
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
