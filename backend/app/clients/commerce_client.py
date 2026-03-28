"""
Commerce Client.

HTTP client for the checkout-order-service (NestJS, port 3001).
Single responsibility: make HTTP calls to the commerce service.

Base URL: http://checkout-order-service:3001 (configurable via COMMERCE_SERVICE_URL)
All methods propagate X-Request-ID through downstream calls.

Requirements: 11.2, 11.3, 11.4, 14.5
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

import httpx

from app.clients.base_client import BaseHTTPClient
from app.core.logging import get_logger

logger = get_logger(__name__)

_COMMERCE_SERVICE_URL = os.environ.get(
    "COMMERCE_SERVICE_URL", "http://localhost:3001"
)
_COMMERCE_TIMEOUT = float(os.environ.get("COMMERCE_TIMEOUT_SECONDS", "15"))


@dataclass
class CommerceResponse:
    """Typed wrapper around a commerce service response."""
    success: bool
    data: dict[str, Any]
    requires_escalation: bool = False
    continue_url: str | None = None
    error_code: str | None = None
    error_message: str | None = None


class CommerceClient(BaseHTTPClient):
    """
    Client for checkout-order-service.

    All methods:
      - Propagate X-Request-ID
      - Return CommerceResponse (never raise on 4xx/5xx — callers handle errors)
      - Handle requires_escalation by extracting continue_url
    """

    def __init__(self) -> None:
        super().__init__(
            base_url=_COMMERCE_SERVICE_URL,
            timeout=_COMMERCE_TIMEOUT,
        )

    # ── Checkout Session Operations ───────────────────────────────────────

    async def create_checkout_session(
        self,
        customer_id: str,
        line_items: list[dict],
        buyer: dict | None = None,
        context: dict | None = None,
        request_id: str | None = None,
    ) -> CommerceResponse:
        """
        POST /commerce/checkout/sessions
        Creates a new checkout session (first item add or checkout_initiate).
        """
        payload: dict[str, Any] = {
            "customer_id": customer_id,
            "line_items": line_items,
        }
        if buyer:
            payload["buyer"] = buyer
        if context:
            payload["context"] = context
        return await self._commerce_post(
            "/commerce/checkout/sessions", payload, request_id
        )

    async def update_checkout_session(
        self,
        session_id: str,
        line_items: list[dict] | None = None,
        buyer: dict | None = None,
        context: dict | None = None,
        payment_instrument: dict | None = None,
        request_id: str | None = None,
    ) -> CommerceResponse:
        """
        PUT /commerce/checkout/sessions/:id
        Full replacement update — line items, buyer, context.
        """
        payload: dict[str, Any] = {}
        if line_items is not None:
            payload["line_items"] = line_items
        if buyer:
            payload["buyer"] = buyer
        if context:
            payload["context"] = context
        if payment_instrument:
            payload["payment_instrument"] = payment_instrument
        return await self._commerce_put(
            f"/commerce/checkout/sessions/{session_id}", payload, request_id
        )

    async def complete_checkout_session(
        self,
        session_id: str,
        payment_instrument: dict,
        request_id: str | None = None,
    ) -> CommerceResponse:
        """
        POST /commerce/checkout/sessions/:id/complete
        Triggers Complete Checkout with payment instrument.
        """
        payload = {"payment_instrument": payment_instrument}
        return await self._commerce_post(
            f"/commerce/checkout/sessions/{session_id}/complete", payload, request_id
        )

    async def cancel_checkout_session(
        self,
        session_id: str,
        request_id: str | None = None,
    ) -> CommerceResponse:
        """
        POST /commerce/checkout/sessions/:id/cancel
        Cancels a checkout session.
        """
        return await self._commerce_post(
            f"/commerce/checkout/sessions/{session_id}/cancel", {}, request_id
        )

    async def get_checkout_session(
        self,
        session_id: str,
        request_id: str | None = None,
    ) -> CommerceResponse:
        """
        GET /commerce/checkout/sessions/:id
        Returns local session state.
        """
        return await self._commerce_get(
            f"/commerce/checkout/sessions/{session_id}", request_id=request_id
        )

    # ── Order Operations ──────────────────────────────────────────────────

    async def get_order(
        self,
        order_id: str,
        customer_id: str,
        request_id: str | None = None,
    ) -> CommerceResponse:
        """
        GET /commerce/orders/:id
        Returns order detail + fulfillment events.
        """
        return await self._commerce_get(
            f"/commerce/orders/{order_id}",
            params={"customerId": customer_id},
            request_id=request_id,
        )

    async def list_orders(
        self,
        customer_id: str,
        cursor: str | None = None,
        limit: int = 20,
        request_id: str | None = None,
    ) -> CommerceResponse:
        """
        GET /commerce/orders
        Paginated order history for a customer.
        """
        params: dict[str, Any] = {"customerId": customer_id, "limit": limit}
        if cursor:
            params["cursor"] = cursor
        return await self._commerce_get(
            "/commerce/orders", params=params, request_id=request_id
        )

    async def cancel_order(
        self,
        order_id: str,
        customer_id: str,
        reason: str | None = None,
        request_id: str | None = None,
    ) -> CommerceResponse:
        """
        POST /commerce/orders/:id/cancel
        Submits a cancellation request.
        """
        payload: dict[str, Any] = {"customerId": customer_id}
        if reason:
            payload["reason"] = reason
        return await self._commerce_post(
            f"/commerce/orders/{order_id}/cancel", payload, request_id
        )

    async def request_return(
        self,
        order_id: str,
        customer_id: str,
        reason: str | None = None,
        request_id: str | None = None,
    ) -> CommerceResponse:
        """
        POST /commerce/orders/:id/return
        Submits a return request.
        """
        payload: dict[str, Any] = {"customerId": customer_id}
        if reason:
            payload["reason"] = reason
        return await self._commerce_post(
            f"/commerce/orders/{order_id}/return", payload, request_id
        )

    # ── Internal HTTP helpers ─────────────────────────────────────────────

    async def _commerce_get(
        self,
        path: str,
        params: dict | None = None,
        request_id: str | None = None,
    ) -> CommerceResponse:
        try:
            data = await self._get(path, params=params, request_id=request_id)
            return self._parse_response(data)
        except httpx.HTTPStatusError as exc:
            return self._parse_error(exc)
        except Exception as exc:
            logger.warning("commerce_client.get_failed", path=path, error=str(exc))
            return CommerceResponse(
                success=False,
                data={},
                error_code="commerce_unavailable",
                error_message=str(exc),
            )

    async def _commerce_post(
        self,
        path: str,
        payload: dict,
        request_id: str | None = None,
    ) -> CommerceResponse:
        try:
            data = await self._post(path, payload=payload, request_id=request_id)
            return self._parse_response(data)
        except httpx.HTTPStatusError as exc:
            return self._parse_error(exc)
        except Exception as exc:
            logger.warning("commerce_client.post_failed", path=path, error=str(exc))
            return CommerceResponse(
                success=False,
                data={},
                error_code="commerce_unavailable",
                error_message=str(exc),
            )

    async def _commerce_put(
        self,
        path: str,
        payload: dict,
        request_id: str | None = None,
    ) -> CommerceResponse:
        """PUT request — not in BaseHTTPClient, implemented here."""
        headers = {"X-Request-ID": request_id} if request_id else {}
        async with self._client() as client:
            try:
                response = await client.put(path, json=payload, headers=headers)
                response.raise_for_status()
                data = response.json()
                return self._parse_response(data)
            except httpx.HTTPStatusError as exc:
                return self._parse_error(exc)
            except Exception as exc:
                logger.warning("commerce_client.put_failed", path=path, error=str(exc))
                return CommerceResponse(
                    success=False,
                    data={},
                    error_code="commerce_unavailable",
                    error_message=str(exc),
                )

    @staticmethod
    def _parse_response(data: dict) -> CommerceResponse:
        """Parse a successful HTTP response, detecting requires_escalation."""
        status = data.get("status", "")
        requires_escalation = status == "requires_escalation"
        continue_url = data.get("continue_url") if requires_escalation else None
        return CommerceResponse(
            success=True,
            data=data,
            requires_escalation=requires_escalation,
            continue_url=continue_url,
        )

    @staticmethod
    def _parse_error(exc: httpx.HTTPStatusError) -> CommerceResponse:
        """Parse an HTTP error response into a CommerceResponse."""
        try:
            body = exc.response.json()
            error_code = body.get("error", "commerce_error")
            error_message = body.get("message", str(exc))
        except Exception:
            error_code = "commerce_error"
            error_message = str(exc)
        logger.warning(
            "commerce_client.http_error",
            status=exc.response.status_code,
            error_code=error_code,
        )
        return CommerceResponse(
            success=False,
            data={},
            error_code=error_code,
            error_message=error_message,
        )
