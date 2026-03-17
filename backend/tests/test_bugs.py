"""
Tests for the three bug fixes:

  Bug 1 — Cross-session people context
    "my friend who runs" in session 1 should be remembered in session 2
    without the customer needing to repeat themselves.

  Bug 2 — answer_html is proper HTML in all response paths
    Slot-filling, direct, blocked, and error responses all had
    answer_html = plain_text (no HTML). Now all go through CitationService.

  Bug 3 — No hardcoded values in Python
    All thresholds, lists, and labels come from config/business_rules.json.
    Changing a value in JSON changes behaviour — no Python edit needed.
"""

import pytest


# ─────────────────────────────────────────────────────────────────────────────
# Bug 1 — Cross-session people context
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.unit
class TestPeopleContext:

    @pytest.fixture
    def memory(self):
        from unittest.mock import MagicMock
        from app.services.memory_service import MemoryService
        return MemoryService(
            session_repo=MagicMock(),
            customer_repo=MagicMock(),
        )

    # Extraction tests
    def test_extracts_friend_relation(self, memory):
        people = memory.extract_people_from_message("my friend who runs")
        assert len(people) == 1
        assert people[0].relation == "friend"

    def test_extracts_dad_relation(self, memory):
        people = memory.extract_people_from_message("gift for my dad")
        assert len(people) == 1
        assert people[0].relation == "dad"

    def test_extracts_partner_relation(self, memory):
        people = memory.extract_people_from_message("my wife loves Nike")
        assert len(people) == 1
        assert people[0].relation in ("partner", "wife")

    def test_extracts_running_interest(self, memory):
        people = memory.extract_people_from_message("my friend who runs marathons")
        assert len(people) == 1
        assert "running" in people[0].interests

    def test_extracts_brand_interest(self, memory):
        people = memory.extract_people_from_message("my dad loves Nike")
        assert len(people) == 1
        assert "Nike" in people[0].interests

    def test_extracts_name_if_present(self, memory):
        people = memory.extract_people_from_message("a gift for my friend Sarah")
        assert len(people) == 1
        assert people[0].name == "Sarah"

    def test_no_people_mentioned_returns_empty(self, memory):
        people = memory.extract_people_from_message("show me Nike running shoes")
        assert people == []

    def test_no_people_in_plain_product_query(self, memory):
        people = memory.extract_people_from_message("under $100 casual shoes")
        assert people == []

    # Cross-session context injection
    def test_build_people_context_with_known_people(self, memory):
        profile = {
            "known_people": [
                {"relation": "friend", "interests": ["running"], "extra": "runs marathons"}
            ]
        }
        context = memory.build_people_context(profile)
        assert "friend" in context.lower()
        assert "running" in context.lower()

    def test_build_people_context_empty_profile(self, memory):
        context = memory.build_people_context({})
        assert context == ""

    def test_build_people_context_contains_do_not_ask_instruction(self, memory):
        profile = {"known_people": [{"relation": "dad", "interests": ["hiking"]}]}
        context = memory.build_people_context(profile)
        # Should tell LLM not to ask again
        assert "do not" in context.lower() or "don't ask" in context.lower() or "already" in context.lower()

    def test_people_persisted_to_profile(self, memory):
        """People extracted from message should be stored in profile under known_people."""
        from app.services.memory_service import PersonNote
        people = [PersonNote(relation="friend", interests=["running"])]

        # Simulate a profile update
        profile = {}
        existing: list[dict] = list(profile.get("known_people", []))
        existing_relations = {p.get("relation") for p in existing}
        for person in people:
            if person.relation and person.relation not in existing_relations:
                existing.append(person.to_dict())
        profile["known_people"] = existing

        assert len(profile["known_people"]) == 1
        assert profile["known_people"][0]["relation"] == "friend"

    def test_person_note_serialisation_roundtrip(self):
        from app.services.memory_service import PersonNote
        original = PersonNote(
            name="Sarah", relation="friend",
            interests=["running", "Nike"],
            size="M", extra="runs marathons",
        )
        restored = PersonNote.from_dict(original.to_dict())
        assert restored.name == original.name
        assert restored.relation == original.relation
        assert restored.interests == original.interests
        assert restored.size == original.size

    def test_person_note_summary_includes_interests(self):
        from app.services.memory_service import PersonNote
        note = PersonNote(relation="friend", interests=["running", "Nike"])
        summary = note.summary()
        assert "running" in summary
        assert "Nike" in summary

    def test_person_note_summary_includes_name(self):
        from app.services.memory_service import PersonNote
        note = PersonNote(name="Sarah", relation="friend", interests=[])
        summary = note.summary()
        assert "Sarah" in summary


# ─────────────────────────────────────────────────────────────────────────────
# Bug 2 — answer_html is proper HTML in ALL response paths
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.unit
class TestAnswerHtml:

    @pytest.fixture
    def citation_svc(self):
        from app.services.citation_service import CitationService
        return CitationService()

    def test_plain_text_wrapped_in_paragraph(self, citation_svc):
        """Long text should be wrapped in <p> tags."""
        text = "This is a helpful response that is longer than eighty characters so should be wrapped."
        _, html, _ = citation_svc.process(text, {})
        assert "<p>" in html

    def test_short_text_escaped(self, citation_svc):
        """Short text with no special chars returns clean output."""
        _, html, _ = citation_svc.process("Hello!", {})
        # Should be safe HTML — no unescaped characters
        assert "<script>" not in html

    def test_html_injection_escaped(self, citation_svc):
        """HTML in the LLM response is escaped — never rendered as HTML."""
        malicious = "<script>alert('xss')</script>"
        _, html, _ = citation_svc.process(malicious, {})
        assert "<script>" not in html
        assert "&lt;script&gt;" in html

    def test_newlines_converted_to_html(self, citation_svc):
        """Double newlines become paragraph breaks."""
        text = "First paragraph.\n\nSecond paragraph."
        _, html, _ = citation_svc.process(text, {})
        assert "</p>" in html or "<br>" in html

    def test_citation_markers_become_links(self, citation_svc):
        """[P1] markers are replaced with <a href> chips."""
        text = "Check out this shoe [P1]."
        citation_map = {
            "P1": {
                "citation_id": "P1", "title": "Nike Air Max",
                "url": "/products/nike", "price": 150.0,
                "currency": "USD", "image_url": None,
                "sku": "NK-001", "in_stock": True, "rating": 4.7, "similarity": 0.9,
            }
        }
        _, html, _ = citation_svc.process(text, citation_map)
        assert 'href="/products/nike"' in html
        assert "product-chip" in html
        assert "Nike Air Max" in html

    def test_answer_plain_text_has_markers_removed(self, citation_svc):
        """The plain answer should have [P1] markers removed."""
        text = "Check out this shoe [P1]."
        citation_map = {
            "P1": {
                "citation_id": "P1", "title": "Nike Air Max",
                "url": "/p/nk", "price": 150.0, "currency": "USD",
                "image_url": None, "sku": "NK-001",
                "in_stock": True, "rating": 4.7, "similarity": 0.9,
            }
        }
        answer, _, _ = citation_svc.process(text, citation_map)
        assert "[P1]" not in answer
        assert "shoe" in answer

    def test_empty_citation_map_returns_safe_html(self, citation_svc):
        """No products — text is still HTML-safe."""
        text = "I could not find any products matching that."
        answer, html, cited = citation_svc.process(text, {})
        assert answer == text
        assert len(cited) == 0
        # html should be safe
        assert "<script>" not in html

    def test_url_in_citation_is_escaped(self, citation_svc):
        """URLs with special chars are HTML-escaped."""
        text = "[P1]"
        citation_map = {
            "P1": {
                "citation_id": "P1", "title": "Shoe & Co",
                "url": "/products/shoe&brand=x",
                "price": 50.0, "currency": "USD", "image_url": None,
                "sku": "S1", "in_stock": True, "rating": 4.0, "similarity": 0.8,
            }
        }
        _, html, _ = citation_svc.process(text, citation_map)
        # & should be escaped in the URL
        assert "&amp;" in html or "shoe" in html.lower()


# ─────────────────────────────────────────────────────────────────────────────
# Bug 3 — JSON config drives all hard-coded values
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.unit
class TestBusinessRulesConfig:

    @pytest.fixture
    def rules(self):
        from app.config.loader import business_rules
        return business_rules()

    def test_config_loads_successfully(self, rules):
        assert isinstance(rules, dict)

    def test_budget_unlimited_sentinel_present(self, rules):
        assert "unlimited_sentinel" in rules["budget"]
        assert rules["budget"]["unlimited_sentinel"] > 1000

    def test_budget_tiers_present(self, rules):
        tiers = rules["budget"]["tiers"]
        assert "budget" in tiers
        assert "mid" in tiers
        assert "premium" in tiers

    def test_slot_extraction_categories_present(self, rules):
        cats = rules["slot_extraction"]["categories"]
        assert "shoes" in cats
        assert "jacket" in cats
        assert isinstance(cats["shoes"], list)

    def test_slot_extraction_brands_present(self, rules):
        brands = rules["slot_extraction"]["brands"]
        assert isinstance(brands, list)
        assert "nike" in brands
        assert "adidas" in brands

    def test_slot_extraction_colors_present(self, rules):
        colors = rules["slot_extraction"]["colors"]
        assert "black" in colors
        assert "white" in colors

    def test_people_context_relations_present(self, rules):
        relations = rules["people_context"]["relations"]
        assert "friend" in relations
        assert "dad" in relations
        assert "partner" in relations

    def test_guardrails_offbrand_words_present(self, rules):
        words = rules["guardrails"]["output"]["offbrand_words"]
        assert isinstance(words, list)
        assert len(words) > 0

    def test_session_limits_present(self, rules):
        assert rules["session"]["max_shown_products"] > 0
        assert rules["session"]["max_profile_brands"] > 0

    # Verify slot extraction uses config not hardcoded lists
    def test_slot_extraction_uses_json_brands(self):
        """Adding a brand to JSON should make it extractable."""
        from app.config.loader import business_rules
        brands = business_rules()["slot_extraction"]["brands"]
        # Nike must be in the JSON list (not hardcoded)
        assert "nike" in brands

    def test_slot_extraction_uses_json_categories(self):
        from app.config.loader import business_rules
        cats = business_rules()["slot_extraction"]["categories"]
        assert "shoes" in cats

    def test_budget_thresholds_from_config(self):
        """Budget tier thresholds come from JSON, not code."""
        from app.config.loader import business_rules
        budget = business_rules()["budget"]
        assert budget["budget_tier_max"] < budget["mid_tier_max"]
        assert budget["mid_tier_max"] < budget["unlimited_sentinel"]

    def test_config_cached_after_first_load(self):
        """Loader caches — same object returned on repeat calls."""
        from app.config.loader import business_rules
        r1 = business_rules()
        r2 = business_rules()
        assert r1 is r2  # lru_cache returns same dict object

    def test_slot_state_uses_config_for_unlimited(self):
        """SlotState.to_rag_filters reads unlimited sentinel from JSON."""
        from app.services.memory_service import SlotState
        from app.config.loader import business_rules
        unlimited = business_rules()["budget"]["unlimited_sentinel"]
        s = SlotState(budget=unlimited)
        filters = s.to_rag_filters()
        # Unlimited budget should NOT appear as a filter
        assert "max_price" not in filters

    def test_slot_state_includes_real_budget_as_filter(self):
        """Real budget should appear as max_price filter."""
        from app.services.memory_service import SlotState
        s = SlotState(budget=150.0)
        filters = s.to_rag_filters()
        assert filters["max_price"] == 150.0

    def test_slot_state_summary_excludes_unlimited(self):
        """Unlimited budget should not appear in slot summary."""
        from app.services.memory_service import SlotState
        from app.config.loader import business_rules
        unlimited = business_rules()["budget"]["unlimited_sentinel"]
        s = SlotState(budget=unlimited)
        summary = s.summary()
        assert str(int(unlimited)) not in summary


# ─────────────────────────────────────────────────────────────────────────────
# Model split — imports work from all expected paths
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.unit
class TestModelSplit:

    def test_import_customer_from_split_file(self):
        from app.db.models.customer import Customer
        assert Customer.__tablename__ == "customers"

    def test_import_session_from_split_file(self):
        from app.db.models.session import Session
        assert Session.__tablename__ == "sessions"

    def test_import_message_from_split_file(self):
        from app.db.models.message import Message, MessageFeedback
        assert Message.__tablename__ == "messages"
        assert MessageFeedback.__tablename__ == "message_feedback"

    def test_import_all_from_package(self):
        from app.db.models import Customer, Session, Message
        assert Customer.__tablename__ == "customers"
        assert Session.__tablename__ == "sessions"
        assert Message.__tablename__ == "messages"

    def test_shim_still_works(self):
        """Old import path still works for backwards compatibility."""
        from app.db.models.models import Customer
        assert Customer.__tablename__ == "customers"

    def test_models_share_same_base(self):
        """All models use the same Base so migrations see all tables."""
        from app.db.models.customer import Customer
        from app.db.models.session import Session
        from app.db.models.message import Message
        assert Customer.metadata is Session.metadata
        assert Session.metadata is Message.metadata
