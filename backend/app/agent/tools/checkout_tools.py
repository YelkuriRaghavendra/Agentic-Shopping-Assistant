"""
Checkout agent tools (LangChain @tool functions).

Each tool factory takes required clients/state as closure parameters and
returns a bound async LangChain tool.  Tools return JSON strings so the
LangGraph ReAct loop can forward them to the LLM.

Some tools include a ``checkout_action`` field in their JSON response;
the graph/orchestrator reads this field and forwards it to the frontend
via a SSE checkout_action event.
"""

from __future__ import annotations

import json
import time
import uuid
from typing import Any

from langchain_core.tools import tool

from app.clients.commerce_client import CommerceClient
from app.core.logging import get_logger
from app.db.repositories import CustomerRepository

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# place_order
# ---------------------------------------------------------------------------

def create_place_order_tool(commerce: CommerceClient, customer_id: str | None):
    @tool
    async def place_order(
        checkout_session_id: str,
        address_id: str,
        payment_method_id: str,
    ) -> str:
        """Charge the saved card and place the order. Call ONLY after the user explicitly confirms."""
        response = await commerce.charge_saved_card(
            session_id=checkout_session_id,
            payment_method_id=payment_method_id,
            address_id=address_id,
            customer_id=customer_id or "",
        )

        if response.success:
            client_secret = response.data.get("clientSecret", "")
            payment_intent_id = response.data.get("paymentIntentId", "")

            if client_secret:
                # 3DS confirmation required — frontend must render the payment form
                return json.dumps({
                    "success": True,
                    "checkout_action": "confirm_payment",
                    "payment_intent_secret": client_secret,
                    "payment_intent_id": payment_intent_id,
                    "checkout_session_id": checkout_session_id,
                    "summary": "Payment created. Customer needs to confirm payment (3DS may be required).",
                })

            order_id = response.data.get("ucpOrderId", checkout_session_id)
            delivery = response.data.get("estimatedDelivery", "5-7 business days")
            return json.dumps({
                "success": True,
                "checkout_action": "order_placed",
                "order_id": order_id,
                "estimated_delivery": delivery,
                "summary": f"Order {order_id} placed successfully.",
            })

        return json.dumps({
            "success": False,
            "error_code": response.error_code or "unknown",
            "error_message": response.error_message or "Order placement failed",
        })

    return place_order


# ---------------------------------------------------------------------------
# save_address
# ---------------------------------------------------------------------------

def create_save_address_tool(customer_repo: CustomerRepository, customer_id: str | None):
    @tool
    async def save_address(
        full_name: str,
        address_line: str,
        city: str,
        pincode: str,
        state: str = "",
        phone: str = "",
        label: str = "Home",
    ) -> str:
        """Save a new delivery address to the customer profile."""
        address_id = f"addr_{int(time.time())}"
        address: dict[str, Any] = {
            "id": address_id,
            "label": label,
            "full_name": full_name,
            "address_line": address_line,
            "city": city,
            "state": state,
            "pincode": pincode,
            "phone": phone,
            "is_default": False,
        }

        if customer_id:
            try:
                customer_uuid = uuid.UUID(customer_id)
                customer = await customer_repo.get_by_id(customer_uuid)
                if not customer:
                    return json.dumps({
                        "success": False,
                        "error": "Customer not found.",
                    })
                profile = customer.profile or {}
                existing = list(profile.get("addresses", []))
                if not existing:
                    address["is_default"] = True
                existing.append(address)
                await customer_repo.update_profile(customer_uuid, {"addresses": existing})
            except Exception as exc:
                logger.warning("checkout_tools.save_address_failed", error=str(exc))
                return json.dumps({"success": False, "error": str(exc)})

        return json.dumps({
            "success": True,
            "address_id": address_id,
            "address": address,
            "summary": f"Address saved: {address_line}, {city}",
        })

    return save_address


# ---------------------------------------------------------------------------
# request_payment_setup
# ---------------------------------------------------------------------------

def create_request_payment_setup_tool(stripe_service: Any, customer_id: str | None):
    @tool
    async def request_payment_setup() -> str:
        """Trigger inline Stripe card collection in the chat. Call when the customer has no saved payment method or wants to add a new card."""
        result = await stripe_service.create_setup_intent(customer_id or "")
        return json.dumps({
            "success": True,
            "checkout_action": "payment_setup",
            "setup_intent_secret": result["client_secret"],
            "summary": "Payment setup requested. Waiting for card input.",
        })

    return request_payment_setup


# ---------------------------------------------------------------------------
# request_address_form
# ---------------------------------------------------------------------------

def create_request_address_form_tool():
    @tool
    async def request_address_form(
        full_name: str = "",
        address_line: str = "",
        city: str = "",
        state: str = "",
        pincode: str = "",
        phone: str = "",
    ) -> str:
        """Render inline address form with pre-filled fields. Use by default whenever checkout needs a delivery address and none is saved yet."""
        prefilled = {
            k: v
            for k, v in {
                "full_name": full_name,
                "address_line": address_line,
                "city": city,
                "state": state,
                "pincode": pincode,
                "phone": phone,
            }.items()
            if v
        }
        return json.dumps({
            "success": True,
            "checkout_action": "address_form",
            "prefilled": prefilled,
            "summary": "Address form requested. Waiting for user input.",
        })

    return request_address_form


# ---------------------------------------------------------------------------
# update_cart
# ---------------------------------------------------------------------------

def create_update_cart_tool(commerce: CommerceClient, checkout_session_id: str | None):
    @tool
    async def update_cart(
        action: str,
        product_id: str,
        quantity: int = 1,
    ) -> str:
        """Modify cart: remove an item or change quantity. action must be 'remove' or 'update_quantity'."""
        session_id = checkout_session_id or ""

        current = await commerce.get_checkout_session(session_id)
        if not current.success:
            return json.dumps({"success": False, "error": "Could not load cart."})

        line_items = current.data.get("lineItemsSnapshot", [])

        if action == "remove":
            line_items = [
                li for li in line_items
                if li.get("item", {}).get("id") != product_id
            ]
        elif action == "update_quantity":
            for li in line_items:
                if li.get("item", {}).get("id") == product_id:
                    li["quantity"] = quantity
        else:
            return json.dumps({"success": False, "error": f"Unknown action: {action}"})

        response = await commerce.update_checkout_session(
            session_id=session_id,
            line_items=line_items,
        )
        if response.success:
            return json.dumps({"success": True, "summary": "Cart updated."})
        return json.dumps({"success": False, "error": "Failed to update cart."})

    return update_cart


# ---------------------------------------------------------------------------
# exit_checkout
# ---------------------------------------------------------------------------

def create_exit_checkout_tool():
    @tool
    async def exit_checkout(
        reason: str = "user_cancelled",
    ) -> str:
        """Hand control back to the shopping assistant. Call when: order placed, user cancels, off-topic, cart empty, or error."""
        return json.dumps({
            "success": True,
            "checkout_action": "exit_checkout",
            "reason": reason,
            "summary": f"Exiting checkout: {reason}",
        })

    return exit_checkout
