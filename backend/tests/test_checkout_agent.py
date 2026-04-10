"""Tests for checkout agent tools and mode switching."""
import time
import uuid

import pytest
from unittest.mock import AsyncMock, MagicMock

from app.services.checkout_tools import (
    CheckoutToolRegistry,
    CHECKOUT_TOOL_DEFINITIONS,
    CheckoutToolResult,
)


# ── Tool definition tests ────────────────────────────────────────────────────


class TestCheckoutToolDefinitions:
    """Verify tool definitions are well-formed."""

    def test_all_tools_present(self):
        names = [t["function"]["name"] for t in CHECKOUT_TOOL_DEFINITIONS]
        assert "place_order" in names
        assert "save_address" in names
        assert "request_payment_setup" in names
        assert "request_address_form" in names
        assert "update_cart" in names
        assert "direct_answer" in names
        assert "exit_checkout" in names
        assert len(names) == 7

    def test_place_order_requires_all_params(self):
        place = next(
            t for t in CHECKOUT_TOOL_DEFINITIONS
            if t["function"]["name"] == "place_order"
        )
        required = place["function"]["parameters"]["required"]
        assert "checkout_session_id" in required
        assert "address_id" in required
        assert "payment_method_id" in required

    def test_exit_checkout_reason_enum(self):
        exit_tool = next(
            t for t in CHECKOUT_TOOL_DEFINITIONS
            if t["function"]["name"] == "exit_checkout"
        )
        reason_prop = exit_tool["function"]["parameters"]["properties"]["reason"]
        assert "order_placed" in reason_prop["enum"]
        assert "user_cancelled" in reason_prop["enum"]
        assert "off_topic" in reason_prop["enum"]
        assert "cart_empty" in reason_prop["enum"]

    def test_save_address_required_fields(self):
        save = next(
            t for t in CHECKOUT_TOOL_DEFINITIONS
            if t["function"]["name"] == "save_address"
        )
        required = save["function"]["parameters"]["required"]
        assert "full_name" in required
        assert "address_line" in required
        assert "city" in required
        assert "pincode" in required

    def test_update_cart_action_enum(self):
        cart = next(
            t for t in CHECKOUT_TOOL_DEFINITIONS
            if t["function"]["name"] == "update_cart"
        )
        action_prop = cart["function"]["parameters"]["properties"]["action"]
        assert "remove" in action_prop["enum"]
        assert "update_quantity" in action_prop["enum"]


# ── Tool handler tests ───────────────────────────────────────────────────────


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
            customer_id="cust_123",
            checkout_session_id="cs_456",
        )

    @pytest.mark.asyncio
    async def test_place_order_success(self, registry):
        registry._commerce.charge_saved_card.return_value = MagicMock(
            success=True,
            data={"ucpOrderId": "VIK-001", "estimatedDelivery": "2026-04-14"},
        )
        result = await registry.execute("place_order", {
            "checkout_session_id": "cs_456",
            "address_id": "addr_1",
            "payment_method_id": "pm_abc",
        })
        assert result.success is True
        assert result.data["order_id"] == "VIK-001"
        assert result.checkout_action == "order_placed"
        registry._commerce.charge_saved_card.assert_called_once()

    @pytest.mark.asyncio
    async def test_place_order_failure(self, registry):
        registry._commerce.charge_saved_card.return_value = MagicMock(
            success=False,
            error_code="card_declined",
            error_message="Your card was declined",
        )
        result = await registry.execute("place_order", {
            "checkout_session_id": "cs_456",
            "address_id": "addr_1",
            "payment_method_id": "pm_abc",
        })
        assert result.success is False
        assert result.data["error_code"] == "card_declined"

    @pytest.mark.asyncio
    async def test_save_address(self):
        commerce = AsyncMock()
        customer_repo = AsyncMock()
        stripe_service = AsyncMock()
        registry = CheckoutToolRegistry(
            commerce_client=commerce,
            customer_repo=customer_repo,
            stripe_service=stripe_service,
            customer_id="11111111-1111-1111-1111-111111111111",
            checkout_session_id="cs_456",
        )
        customer_repo.get_by_id.return_value = MagicMock(profile={"addresses": []})
        customer_repo.update_profile = AsyncMock()

        result = await registry.execute("save_address", {
            "full_name": "Raghav",
            "address_line": "42 MG Road",
            "city": "Bangalore",
            "pincode": "560001",
        })
        assert result.success is True
        assert "addr_" in result.data["address_id"]
        # First address should be default
        assert result.data["address"]["is_default"] is True
        customer_repo.get_by_id.assert_awaited_once_with(
            uuid.UUID("11111111-1111-1111-1111-111111111111")
        )
        customer_repo.update_profile.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_save_address_returns_failure_when_repo_errors(self):
        commerce = AsyncMock()
        customer_repo = AsyncMock()
        stripe_service = AsyncMock()
        registry = CheckoutToolRegistry(
            commerce_client=commerce,
            customer_repo=customer_repo,
            stripe_service=stripe_service,
            customer_id="11111111-1111-1111-1111-111111111111",
            checkout_session_id="cs_456",
        )
        customer_repo.get_by_id.side_effect = RuntimeError("db unavailable")

        result = await registry.execute("save_address", {
            "full_name": "Raghav",
            "address_line": "42 MG Road",
            "city": "Bangalore",
            "pincode": "560001",
        })

        assert result.success is False
        assert "db unavailable" in result.summary

    @pytest.mark.asyncio
    async def test_request_payment_setup(self, registry):
        registry._stripe.create_setup_intent.return_value = {
            "client_secret": "seti_secret_123",
        }
        result = await registry.execute("request_payment_setup", {})
        assert result.success is True
        assert result.data["setup_intent_secret"] == "seti_secret_123"
        assert result.checkout_action == "payment_setup"

    @pytest.mark.asyncio
    async def test_request_address_form(self, registry):
        result = await registry.execute("request_address_form", {
            "full_name": "Raghav",
            "city": "Bangalore",
        })
        assert result.success is True
        assert result.data["prefilled"]["full_name"] == "Raghav"
        assert result.data["prefilled"]["city"] == "Bangalore"
        assert result.checkout_action == "address_form"

    @pytest.mark.asyncio
    async def test_update_cart_remove(self, registry):
        registry._commerce.get_checkout_session.return_value = MagicMock(
            success=True,
            data={
                "lineItemsSnapshot": [
                    {"item": {"id": "prod_1", "title": "Nike"}, "quantity": 1},
                    {"item": {"id": "prod_2", "title": "Levi's"}, "quantity": 1},
                ],
            },
        )
        registry._commerce.update_checkout_session.return_value = MagicMock(
            success=True,
            data={"lineItemsSnapshot": [{"item": {"id": "prod_2"}, "quantity": 1}]},
        )
        result = await registry.execute("update_cart", {
            "action": "remove",
            "product_id": "prod_1",
        })
        assert result.success is True
        # Verify line_items passed to update excludes prod_1
        call_args = registry._commerce.update_checkout_session.call_args
        updated_items = call_args.kwargs.get("line_items") or call_args[1].get("line_items", [])
        assert all(li["item"]["id"] != "prod_1" for li in updated_items)

    @pytest.mark.asyncio
    async def test_exit_checkout(self, registry):
        result = await registry.execute("exit_checkout", {"reason": "user_cancelled"})
        assert result.success is True
        assert result.data["reason"] == "user_cancelled"
        assert result.checkout_action == "exit_checkout"

    @pytest.mark.asyncio
    async def test_unknown_tool(self, registry):
        result = await registry.execute("nonexistent_tool", {})
        assert result.success is False
        assert "Unknown" in result.summary


# ── Checkout mode integration tests ──────────────────────────────────────────


class TestCheckoutModeIntegration:
    """Test checkout mode switching in session context."""

    @pytest.mark.asyncio
    async def test_checkout_mode_entry(self):
        from app.services.memory_service import MemoryService

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
        from app.services.memory_service import MemoryService

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
        from app.services.memory_service import MemoryService

        session = MagicMock()
        memory = MemoryService(MagicMock(), MagicMock())

        session.context = {"active_agent": "checkout"}
        assert memory.get_active_agent(session) == "checkout"

        session.context = {}
        assert memory.get_active_agent(session) is None

        session.context = None
        assert memory.get_active_agent(session) is None
