"""
Stripe Customer service.

Manages the link between our customer_id and Stripe Customer objects.
Proxies all Stripe operations through the checkout-order-service.

Handles:
  - Creating SetupIntents (for saving cards)
  - Listing saved PaymentMethods
"""

from __future__ import annotations

from typing import Any

from app.clients.commerce_client import CommerceClient
from app.core.logging import get_logger

logger = get_logger(__name__)


class StripeCustomerService:
    """Proxies Stripe Customer operations through the checkout-order-service."""

    def __init__(self, commerce_client: CommerceClient | None = None):
        self._commerce = commerce_client or CommerceClient()

    async def create_setup_intent(self, customer_id: str) -> dict[str, str]:
        """
        Create a Stripe SetupIntent for saving a card.
        Calls: POST /commerce/customers/{customer_id}/setup-intent
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
        Calls: GET /commerce/customers/{customer_id}/payment-methods
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
