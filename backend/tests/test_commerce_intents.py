"""
Tests for commerce intent routing — Tasks 11.1, 11.2, 11.3.

Covers:
  - Intent_Classifier recognises all 7 commerce intents (Req 11.1)
  - FeatureFlagService defaults to disabled when SDK unavailable (Req 17.5)
  - FeatureFlagService returns graceful response when flag is off (Req 17.4)
  - CommerceClient parses requires_escalation and extracts continue_url (Req 11.4)
  - CommerceClient formats natural language responses (Req 11.4)
  - Slot extraction for commerce intents (Req 20.1)
  - Missing required slots trigger re-prompt (Req 20.2)
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.chat_service import _classify_commerce_intent, _REQUIRED_SLOTS, _SLOT_PROMPTS
from app.services.feature_flag_service import FeatureFlagService, COMMERCE_INTENTS
from app.clients.commerce_client import CommerceClient, CommerceResponse


# ─────────────────────────────────────────────────────────────────────────────
# Task 11.1 — Intent_Classifier commerce intents
# ─────────────────────────────────────────────────────────────────────────────

class TestCommerceIntentClassifier:
    """Validates: Requirements 11.1"""

    @pytest.mark.parametrize("message,expected_intent", [
        ("I want to checkout", "checkout_initiate"),
        ("proceed to checkout please", "checkout_initiate"),
        ("place my order now", "checkout_initiate"),
        ("add to cart", "add_to_cart"),
        ("add this to my cart", "add_to_cart"),
        ("put it in my cart", "add_to_cart"),
        ("remove from cart", "remove_from_cart"),
        ("take it out of my cart", "remove_from_cart"),
        ("view cart", "view_cart"),
        ("show my cart", "view_cart"),
        ("what's in my cart?", "view_cart"),
        ("order status", "order_status"),
        ("where is my order?", "order_status"),
        ("track my order #12345", "order_status"),
        ("order history", "order_history"),
        ("show my orders", "order_history"),
        ("my previous orders", "order_history"),
        ("cancel order", "cancel_order"),
        ("cancel my order", "cancel_order"),
    ])
    def test_classifies_commerce_intent(self, message, expected_intent):
        result = _classify_commerce_intent(message)
        assert result == expected_intent, f"Expected {expected_intent} for '{message}', got {result}"

    def test_non_commerce_message_returns_none(self):
        assert _classify_commerce_intent("show me running shoes") is None
        assert _classify_commerce_intent("what is the return policy?") is None
        assert _classify_commerce_intent("hello") is None

    def test_all_seven_intents_are_covered(self):
        """All 7 required commerce intents must be classifiable."""
        required_intents = {
            "checkout_initiate", "add_to_cart", "remove_from_cart",
            "view_cart", "order_status", "order_history", "cancel_order",
        }
        sample_messages = {
            "checkout_initiate": "checkout now",
            "add_to_cart": "add to cart",
            "remove_from_cart": "remove from cart",
            "view_cart": "view cart",
            "order_status": "order status",
            "order_history": "order history",
            "cancel_order": "cancel order",
        }
        for intent, message in sample_messages.items():
            result = _classify_commerce_intent(message)
            assert result == intent, f"Intent {intent} not classified from '{message}'"

    def test_required_slots_defined_for_all_intents(self):
        """Every commerce intent must have a required slots definition."""
        for intent in COMMERCE_INTENTS:
            assert intent in _REQUIRED_SLOTS, f"Missing required slots for intent: {intent}"

    def test_slot_prompts_cover_all_required_slots(self):
        """Every required slot must have a re-prompt question."""
        all_required = {slot for slots in _REQUIRED_SLOTS.values() for slot in slots}
        for slot in all_required:
            assert slot in _SLOT_PROMPTS, f"Missing slot prompt for: {slot}"


# ─────────────────────────────────────────────────────────────────────────────
# Task 11.2 — FeatureFlagService
# ─────────────────────────────────────────────────────────────────────────────

class TestFeatureFlagService:
    """Validates: Requirements 17.1, 17.2, 17.3, 17.4, 17.5"""

    def test_defaults_to_disabled_when_sdk_not_installed(self):
        """Req 17.5: If LaunchDarkly is unreachable, default to disabled."""
        # Simulate uninitialized state (SDK not available)
        svc = FeatureFlagService.__new__(FeatureFlagService)
        svc._client = None
        svc._initialized = False
        svc._sdk_key = "some-key"
        # Without initialization, all flags default to disabled
        assert svc.is_commerce_enabled("customer-123") is False

    def test_defaults_to_disabled_when_no_sdk_key(self):
        """Req 17.5: No SDK key → default to disabled."""
        with patch.dict("os.environ", {}, clear=True):
            svc = FeatureFlagService.__new__(FeatureFlagService)
            svc._client = None
            svc._initialized = False
            svc._sdk_key = ""
            assert svc.is_commerce_enabled("customer-123") is False

    def test_is_intent_enabled_checks_global_flag_first(self):
        """Req 17.1: Global flag must be enabled before per-intent flag is checked."""
        svc = FeatureFlagService.__new__(FeatureFlagService)
        svc._client = None
        svc._initialized = False
        svc._sdk_key = ""
        # Global flag is disabled → per-intent flag is never checked
        assert svc.is_intent_enabled("add_to_cart", "customer-123") is False

    def test_commerce_intents_set_contains_all_seven(self):
        """Req 17.1: All 7 commerce intents must be in the gated set."""
        expected = {
            "checkout_initiate", "add_to_cart", "remove_from_cart",
            "view_cart", "order_status", "order_history", "cancel_order",
        }
        assert expected == COMMERCE_INTENTS

    def test_evaluate_returns_default_on_exception(self):
        """Req 17.5: Any evaluation error must return the default (False)."""
        svc = FeatureFlagService.__new__(FeatureFlagService)
        svc._initialized = True
        mock_client = MagicMock()
        mock_client.variation.side_effect = RuntimeError("LD connection lost")
        svc._client = mock_client
        svc._sdk_key = "test-key"
        result = svc._evaluate("commerce.enabled", "customer-123", default=False)
        assert result is False

    def test_close_is_safe_when_client_is_none(self):
        """close() must not raise when client was never initialized."""
        svc = FeatureFlagService.__new__(FeatureFlagService)
        svc._client = None
        svc._initialized = False
        svc._sdk_key = ""
        svc.close()  # should not raise


# ─────────────────────────────────────────────────────────────────────────────
# Task 11.3 — CommerceClient
# ─────────────────────────────────────────────────────────────────────────────

class TestCommerceClientResponseParsing:
    """Validates: Requirements 11.2, 11.3, 11.4, 14.5"""

    def test_parse_response_success(self):
        data = {"session_id": "sess-1", "ucp_status": "incomplete"}
        result = CommerceClient._parse_response(data)
        assert result.success is True
        assert result.requires_escalation is False
        assert result.continue_url is None
        assert result.data == data

    def test_parse_response_requires_escalation(self):
        """Req 11.4: requires_escalation must extract continue_url."""
        data = {
            "status": "requires_escalation",
            "continue_url": "https://merchant.com/checkout/abc",
            "messages": ["Please complete checkout on our site"],
        }
        result = CommerceClient._parse_response(data)
        assert result.success is True
        assert result.requires_escalation is True
        assert result.continue_url == "https://merchant.com/checkout/abc"

    def test_parse_response_no_continue_url_when_not_escalated(self):
        data = {"status": "incomplete", "continue_url": "https://merchant.com/checkout/abc"}
        result = CommerceClient._parse_response(data)
        assert result.requires_escalation is False
        assert result.continue_url is None  # only extracted on requires_escalation

    def test_parse_error_extracts_error_code(self):
        mock_response = MagicMock()
        mock_response.status_code = 422
        mock_response.json.return_value = {
            "error": "out_of_stock",
            "message": "Item is out of stock",
        }
        import httpx
        exc = httpx.HTTPStatusError("422", request=MagicMock(), response=mock_response)
        result = CommerceClient._parse_error(exc)
        assert result.success is False
        assert result.error_code == "out_of_stock"
        assert result.error_message == "Item is out of stock"

    def test_parse_error_fallback_on_non_json(self):
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.json.side_effect = ValueError("not json")
        import httpx
        exc = httpx.HTTPStatusError("500", request=MagicMock(), response=mock_response)
        result = CommerceClient._parse_error(exc)
        assert result.success is False
        assert result.error_code == "commerce_error"


class TestCommerceClientNaturalLanguageFormatting:
    """Validates: Req 11.4 — format structured responses into natural language."""

    def _make_service(self):
        """Create a minimal ChatService-like object with _format_commerce_response."""
        from app.services.chat_service import ChatService
        # We only need the formatting method — no DB or LLM needed
        svc = object.__new__(ChatService)
        return svc

    def test_requires_escalation_formats_as_markdown_link(self):
        svc = self._make_service()
        response = CommerceResponse(
            success=True,
            data={},
            requires_escalation=True,
            continue_url="https://merchant.com/checkout/abc",
        )
        result = svc._format_commerce_response("checkout_initiate", response)
        assert "[Complete your checkout here](https://merchant.com/checkout/abc)" in result

    def test_out_of_stock_error_returns_friendly_message(self):
        svc = self._make_service()
        response = CommerceResponse(
            success=False, data={}, error_code="out_of_stock"
        )
        result = svc._format_commerce_response("add_to_cart", response)
        assert "out of stock" in result.lower()

    def test_add_to_cart_success_mentions_item_count(self):
        svc = self._make_service()
        response = CommerceResponse(
            success=True,
            data={"line_items_snapshot": [{"item": {"id": "p1"}, "quantity": 1}]},
        )
        result = svc._format_commerce_response("add_to_cart", response)
        assert "cart" in result.lower()
        assert "1 item" in result

    def test_view_cart_empty_returns_empty_message(self):
        svc = self._make_service()
        response = CommerceResponse(success=True, data={"line_items_snapshot": []})
        result = svc._format_commerce_response("view_cart", response)
        assert "empty" in result.lower()

    def test_view_cart_with_items_shows_subtotal(self):
        svc = self._make_service()
        response = CommerceResponse(
            success=True,
            data={
                "line_items_snapshot": [
                    {"item": {"id": "p1", "title": "Nike Air Max", "price": 12000}, "quantity": 2}
                ],
                "totals_snapshot": {"subtotal_cents": 24000, "tax_cents": 0, "grand_total_cents": 24000},
            },
        )
        result = svc._format_commerce_response("view_cart", response)
        assert "Nike Air Max" in result
        assert "$240.00" in result

    def test_order_status_includes_status_text(self):
        svc = self._make_service()
        response = CommerceResponse(
            success=True,
            data={"status": "shipped", "ucp_order_id": "ORD-999"},
        )
        result = svc._format_commerce_response("order_status", response)
        assert "shipped" in result
        assert "ORD-999" in result

    def test_order_history_empty_returns_no_orders_message(self):
        svc = self._make_service()
        response = CommerceResponse(success=True, data={"orders": []})
        result = svc._format_commerce_response("order_history", response)
        assert "no" in result.lower() or "don't have" in result.lower()

    def test_cancel_order_success_confirms_cancellation(self):
        svc = self._make_service()
        response = CommerceResponse(
            success=True,
            data={"ucp_order_id": "ORD-123"},
        )
        result = svc._format_commerce_response("cancel_order", response)
        assert "cancelled" in result.lower() or "canceled" in result.lower()
        assert "ORD-123" in result

    def test_cancellation_not_allowed_returns_friendly_message(self):
        svc = self._make_service()
        response = CommerceResponse(
            success=False, data={}, error_code="cancellation_not_allowed"
        )
        result = svc._format_commerce_response("cancel_order", response)
        assert "shipped" in result.lower() or "cancel" in result.lower()


class TestCommerceClientSlotExtraction:
    """Validates: Requirements 20.1, 20.2, 20.4"""

    @pytest.mark.asyncio
    async def test_extracts_order_id_from_message(self):
        from app.services.chat_service import ChatService
        svc = object.__new__(ChatService)
        svc._rag = AsyncMock()
        svc._rag.retrieve = AsyncMock(return_value=[])

        session = MagicMock()
        session.context = {}

        slots = await svc._extract_commerce_slots(
            message="What's the status of order #ORD-12345?",
            intent="order_status",
            session=session,
        )
        assert slots.get("order_id") == "ORD-12345"

    @pytest.mark.asyncio
    async def test_extracts_quantity_from_message(self):
        from app.services.chat_service import ChatService
        svc = object.__new__(ChatService)
        svc._rag = AsyncMock()
        svc._rag.retrieve = AsyncMock(return_value=[])

        session = MagicMock()
        session.context = {}

        slots = await svc._extract_commerce_slots(
            message="Add 3 pairs of Nike Air Max to my cart",
            intent="add_to_cart",
            session=session,
        )
        assert slots.get("quantity") == 3

    @pytest.mark.asyncio
    async def test_resolves_ambiguous_product_via_rag(self):
        """Req 20.4: Ambiguous references resolved via RAG_Pipeline."""
        from app.services.chat_service import ChatService
        from app.clients.rag_client import RetrievedChunk

        svc = object.__new__(ChatService)
        mock_chunk = RetrievedChunk(
            product_id="prod-abc",
            content="Nike Air Max 90",
            document_type="product",
            metadata={},
            similarity=0.95,
        )
        svc._rag = AsyncMock()
        svc._rag.retrieve = AsyncMock(return_value=[mock_chunk])

        session = MagicMock()
        session.context = {}

        slots = await svc._extract_commerce_slots(
            message="Add the blue one to my cart",
            intent="add_to_cart",
            session=session,
        )
        assert slots.get("product_id") == "prod-abc"
        svc._rag.retrieve.assert_called_once()

    @pytest.mark.asyncio
    async def test_checkout_initiate_uses_cart_from_session(self):
        """Req 20.1: checkout_initiate uses line_items from session cart."""
        from app.services.chat_service import ChatService

        svc = object.__new__(ChatService)
        svc._rag = AsyncMock()
        svc._rag.retrieve = AsyncMock(return_value=[])

        session = MagicMock()
        session.context = {
            "cart": {
                "line_items": [{"item": {"id": "p1"}, "quantity": 2}]
            }
        }

        slots = await svc._extract_commerce_slots(
            message="I want to checkout",
            intent="checkout_initiate",
            session=session,
        )
        assert slots.get("line_items") == [{"item": {"id": "p1"}, "quantity": 2}]


# ─────────────────────────────────────────────────────────────────────────────
# Task 2.5 — add_to_cart routes to correct CommerceClient method
# ─────────────────────────────────────────────────────────────────────────────

class TestAddToCartSessionRouting:
    """
    Validates: Requirements 4.1, 7.1, 7.2
    Property 14: add_to_cart routes to correct CommerceClient method
    Property 21: Active session is reused across cart intents
    """

    def _make_service(self, commerce_mock):
        from app.services.chat_service import ChatService
        svc = object.__new__(ChatService)
        svc._commerce = commerce_mock
        return svc

    @pytest.mark.asyncio
    async def test_add_to_cart_calls_create_when_no_session(self):
        """No checkout_session_id in context → create_checkout_session called."""
        commerce = AsyncMock()
        commerce.create_checkout_session = AsyncMock(
            return_value=CommerceResponse(
                success=True,
                data={"sessionId": "new-session-123", "line_items_snapshot": []},
            )
        )
        commerce.update_checkout_session = AsyncMock()

        svc = self._make_service(commerce)

        session = MagicMock()
        session.context = {}  # no cart key

        slots = {"product_id": "prod-1", "quantity": 2}
        await svc._dispatch_commerce_intent(
            intent="add_to_cart",
            slots=slots,
            customer_id="cust-1",
            request_id="req-1",
            session=session,
        )

        commerce.create_checkout_session.assert_called_once()
        commerce.update_checkout_session.assert_not_called()

    @pytest.mark.asyncio
    async def test_add_to_cart_stores_session_id_in_context(self):
        """After create_checkout_session, sessionId stored in session.context['cart']."""
        commerce = AsyncMock()
        commerce.create_checkout_session = AsyncMock(
            return_value=CommerceResponse(
                success=True,
                data={"sessionId": "new-session-abc"},
            )
        )

        svc = self._make_service(commerce)

        session = MagicMock()
        session.context = {}

        await svc._dispatch_commerce_intent(
            intent="add_to_cart",
            slots={"product_id": "prod-1", "quantity": 1},
            customer_id="cust-1",
            request_id="req-1",
            session=session,
        )

        assert session.context.get("cart", {}).get("checkout_session_id") == "new-session-abc"

    @pytest.mark.asyncio
    async def test_add_to_cart_calls_update_when_session_exists(self):
        """Existing checkout_session_id in context → update_checkout_session called."""
        commerce = AsyncMock()
        commerce.update_checkout_session = AsyncMock(
            return_value=CommerceResponse(
                success=True,
                data={"sessionId": "existing-session-456", "line_items_snapshot": []},
            )
        )
        commerce.create_checkout_session = AsyncMock()

        svc = self._make_service(commerce)

        session = MagicMock()
        session.context = {"cart": {"checkout_session_id": "existing-session-456"}}

        await svc._dispatch_commerce_intent(
            intent="add_to_cart",
            slots={"product_id": "prod-2", "quantity": 1},
            customer_id="cust-1",
            request_id="req-1",
            session=session,
        )

        commerce.update_checkout_session.assert_called_once_with(
            session_id="existing-session-456",
            line_items=[{
                "item": {
                    "id": "prod-2",
                    "title": "prod-2",
                    "price": 0,
                },
                "quantity": 1,
            }],
            request_id="req-1",
        )
        commerce.create_checkout_session.assert_not_called()

    @pytest.mark.asyncio
    async def test_add_to_cart_never_calls_wrong_method(self):
        """
        Property 14: For any add_to_cart intent, exactly one of create or update is called,
        never both, and the choice depends solely on whether checkout_session_id is present.
        """
        for has_session in [True, False]:
            commerce = AsyncMock()
            commerce.create_checkout_session = AsyncMock(
                return_value=CommerceResponse(success=True, data={"sessionId": "s1"})
            )
            commerce.update_checkout_session = AsyncMock(
                return_value=CommerceResponse(success=True, data={})
            )

            svc = self._make_service(commerce)
            session = MagicMock()
            session.context = (
                {"cart": {"checkout_session_id": "existing-id"}} if has_session else {}
            )

            await svc._dispatch_commerce_intent(
                intent="add_to_cart",
                slots={"product_id": "p1", "quantity": 1},
                customer_id="c1",
                request_id="r1",
                session=session,
            )

            if has_session:
                commerce.update_checkout_session.assert_called_once()
                commerce.create_checkout_session.assert_not_called()
            else:
                commerce.create_checkout_session.assert_called_once()
                commerce.update_checkout_session.assert_not_called()
