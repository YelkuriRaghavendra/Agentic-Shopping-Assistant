"""
Tests for suggestions, skills, and prompt library.

Follows pytest best practices from the python-testing skill:
  - One assertion per test where possible
  - Descriptive names: test_<what>_<condition>_<expected>
  - Fixtures for shared setup
  - Parametrize for data-driven cases
  - Marks: unit (no IO), integration (needs DB)
"""

import pytest


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture
def empty_slots():
    from app.services.memory_service import SlotState
    return SlotState()


@pytest.fixture
def full_slots():
    from app.services.memory_service import SlotState
    return SlotState(
        category="shoes", use_case="running",
        brand="Nike", budget=150.0, size="10",
    )


@pytest.fixture
def product_cards():
    from app.api.dto.chat_dto import ProductCardDTO
    return [
        ProductCardDTO(
            productId="P1", productName="Nike Air Max 270",
            price=150.0, rating=4.7, productImageUrl=None,
        ),
        ProductCardDTO(
            productId="P2", productName="Adidas Ultraboost",
            price=180.0, rating=4.8, productImageUrl=None,
        ),
    ]


@pytest.fixture
def skill_ctx(empty_slots):
    from app.services.skills.base_skill import SkillContext
    return SkillContext(
        message="show me Nike shoes",
        intent="product_search",
        slots=empty_slots,
        customer_profile={},
        session_context={},
        turn_count=0,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Suggestion service
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.unit
class TestSuggestionService:

    @pytest.fixture
    def svc(self):
        from app.services.suggestion_service import SuggestionService
        return SuggestionService()

    def test_blocked_returns_no_chips(self, svc, empty_slots):
        r = svc.generate(
            intent="product_search", slots=empty_slots,
            cited_products=[], blocked=True,
        )
        assert r.chips == []

    def test_greeting_returns_four_chips(self, svc, empty_slots):
        r = svc.generate(
            intent="greeting", slots=empty_slots,
            cited_products=[], blocked=False,
        )
        assert len(r.chips) == 4

    def test_greeting_chips_have_icons(self, svc, empty_slots):
        r = svc.generate(intent="greeting", slots=empty_slots, cited_products=[], blocked=False)
        icons = [c.icon for c in r.chips]
        assert all(icon is not None for icon in icons)

    def test_product_search_with_results_offers_refinement(self, svc, empty_slots, product_cards):
        r = svc.generate(
            intent="product_search", slots=empty_slots,
            cited_products=product_cards, blocked=False,
        )
        chip_types = {c.chip_type for c in r.chips}
        assert "refine" in chip_types

    def test_product_search_no_size_suggests_find_size(self, svc, empty_slots, product_cards):
        r = svc.generate(
            intent="product_search", slots=empty_slots,
            cited_products=product_cards, blocked=False,
        )
        labels = [c.label.lower() for c in r.chips]
        assert any("size" in l for l in labels)

    def test_product_search_with_size_skips_size_chip(self, svc, full_slots, product_cards):
        r = svc.generate(
            intent="product_search", slots=full_slots,
            cited_products=product_cards, blocked=False,
        )
        labels = [c.label.lower() for c in r.chips]
        # size already known — should not ask again
        assert not any(l == "find my size" for l in labels)

    def test_two_products_offers_compare_chip(self, svc, empty_slots, product_cards):
        r = svc.generate(
            intent="product_search", slots=empty_slots,
            cited_products=product_cards, blocked=False,
        )
        labels = [c.label.lower() for c in r.chips]
        assert any("compare" in l for l in labels)

    def test_order_status_shows_return_chip(self, svc, empty_slots):
        r = svc.generate(
            intent="order_status", slots=empty_slots,
            cited_products=[], blocked=False,
        )
        labels = [c.label.lower() for c in r.chips]
        assert any("return" in l for l in labels)

    def test_return_request_shows_policy_chip(self, svc, empty_slots):
        r = svc.generate(
            intent="return_request", slots=empty_slots,
            cited_products=[], blocked=False,
        )
        labels = [c.label.lower() for c in r.chips]
        assert any("policy" in l for l in labels)

    def test_max_four_chips_enforced(self, svc, empty_slots, product_cards):
        r = svc.generate(
            intent="greeting", slots=empty_slots,
            cited_products=product_cards, blocked=False,
        )
        assert len(r.chips) <= 4

    def test_chip_label_max_forty_chars(self, svc, empty_slots):
        r = svc.generate(intent="greeting", slots=empty_slots, cited_products=[], blocked=False)
        for chip in r.chips:
            assert len(chip.label) <= 40, f"Label too long: {chip.label!r}"

    def test_chip_message_is_sendable_string(self, svc, empty_slots):
        r = svc.generate(intent="greeting", slots=empty_slots, cited_products=[], blocked=False)
        for chip in r.chips:
            assert isinstance(chip.message, str)
            assert len(chip.message) > 0

    @pytest.mark.parametrize("intent,expected_chips", [
        ("greeting",      4),
        ("order_status",  4),
        ("return_request", 3),
    ])
    def test_intent_chip_counts(self, svc, empty_slots, intent, expected_chips):
        r = svc.generate(
            intent=intent, slots=empty_slots,
            cited_products=[], blocked=False,
        )
        assert len(r.chips) == expected_chips

    def test_outfit_pairing_includes_style_chips(self, svc, empty_slots, product_cards):
        r = svc.generate(
            intent="outfit_pairing", slots=empty_slots,
            cited_products=product_cards, blocked=False,
        )
        assert len(r.chips) > 0

    def test_size_query_chips_mention_size_guide(self, svc, empty_slots):
        r = svc.generate(
            intent="size_query", slots=empty_slots,
            cited_products=[], blocked=False,
        )
        messages = [c.message.lower() for c in r.chips]
        assert any("size" in m for m in messages)

    def test_price_query_shows_budget_options(self, svc, empty_slots):
        r = svc.generate(
            intent="price_query", slots=empty_slots,
            cited_products=[], blocked=False,
        )
        labels = [c.label for c in r.chips]
        assert any("$" in l for l in labels)


# ─────────────────────────────────────────────────────────────────────────────
# Skill registry
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.unit
class TestSkillRegistry:

    @pytest.fixture
    def registry(self):
        from app.services.skills.skill_registry import SkillRegistry
        return SkillRegistry()

    def test_no_skills_active_for_plain_search(self, registry, skill_ctx):
        # Plain search with no profile → only matching skills should fire
        result = registry.resolve(skill_ctx)
        # Should not crash
        assert isinstance(result.prompt_addon, str)

    def test_returning_customer_skill_activates_with_profile(self, registry, empty_slots):
        from app.services.skills.base_skill import SkillContext
        ctx = SkillContext(
            message="show me shoes",
            intent="product_search",
            slots=empty_slots,
            customer_profile={"preferred_brands": ["Nike"], "total_sessions": 3},
            session_context={},
        )
        result = registry.resolve(ctx)
        assert "returning_customer" in result.metadata.get("active_skills", [])

    def test_no_returning_customer_skill_for_guest(self, registry, empty_slots):
        from app.services.skills.base_skill import SkillContext
        ctx = SkillContext(
            message="show me shoes",
            intent="product_search",
            slots=empty_slots,
            customer_profile={},   # no profile
            session_context={},
        )
        result = registry.resolve(ctx)
        assert "returning_customer" not in result.metadata.get("active_skills", [])

    def test_stylist_skill_activates_for_outfit_intent(self, registry, empty_slots):
        from app.services.skills.base_skill import SkillContext
        ctx = SkillContext(
            message="I have a blue shirt, what pants go with it?",
            intent="outfit_pairing",
            slots=empty_slots,
            customer_profile={},
            session_context={},
        )
        result = registry.resolve(ctx)
        assert "stylist" in result.metadata.get("active_skills", [])

    def test_stylist_skill_activates_for_outfit_keywords(self, registry, empty_slots):
        from app.services.skills.base_skill import SkillContext
        ctx = SkillContext(
            message="what matches my grey jeans?",
            intent="product_search",
            slots=empty_slots,
            customer_profile={},
            session_context={},
        )
        result = registry.resolve(ctx)
        assert "stylist" in result.metadata.get("active_skills", [])

    def test_gift_advisor_activates_for_gift_message(self, registry, empty_slots):
        from app.services.skills.base_skill import SkillContext
        ctx = SkillContext(
            message="I need a birthday gift for my dad",
            intent="gift_finder",
            slots=empty_slots,
            customer_profile={},
            session_context={},
        )
        result = registry.resolve(ctx)
        assert "gift_advisor" in result.metadata.get("active_skills", [])

    def test_size_expert_activates_for_size_question(self, registry, empty_slots):
        from app.services.skills.base_skill import SkillContext
        ctx = SkillContext(
            message="do Nike shoes run small?",
            intent="size_query",
            slots=empty_slots,
            customer_profile={},
            session_context={},
        )
        result = registry.resolve(ctx)
        assert "size_expert" in result.metadata.get("active_skills", [])

    def test_empathy_skill_activates_for_frustration(self, registry, empty_slots):
        from app.services.skills.base_skill import SkillContext
        ctx = SkillContext(
            message="this is terrible, I've been waiting 3 weeks",
            intent="order_status",
            slots=empty_slots,
            customer_profile={},
            session_context={},
        )
        result = registry.resolve(ctx)
        assert "empathy" in result.metadata.get("active_skills", [])

    def test_multiple_skills_can_be_active(self, registry, empty_slots):
        from app.services.skills.base_skill import SkillContext
        ctx = SkillContext(
            message="gift for my dad, what size should I get him?",
            intent="gift_finder",
            slots=empty_slots,
            customer_profile={},
            session_context={},
        )
        result = registry.resolve(ctx)
        active = result.metadata.get("active_skills", [])
        assert "gift_advisor" in active
        assert "size_expert" in active

    def test_merged_prompt_contains_all_active_skill_prompts(self, registry, empty_slots):
        from app.services.skills.base_skill import SkillContext
        ctx = SkillContext(
            message="gift for my dad",
            intent="gift_finder",
            slots=empty_slots,
            customer_profile={},
            session_context={},
        )
        result = registry.resolve(ctx)
        # Gift advisor skill should load from SKILL.md — contains gift content
        assert len(result.prompt_addon) > 50
        assert "gift" in result.prompt_addon.lower() or "SKILL: gift-finding" in result.prompt_addon

    def test_empty_result_when_no_skills_match(self, registry, empty_slots):
        from app.services.skills.base_skill import SkillContext
        ctx = SkillContext(
            message="where is my order?",
            intent="order_status",
            slots=empty_slots,
            customer_profile={},
            session_context={},
        )
        result = registry.resolve(ctx)
        # Should return a result (possibly empty) without crashing
        assert result is not None

    def test_register_new_skill(self, registry):
        from app.services.skills.base_skill import SkillBase, SkillResult

        class FakeSkill(SkillBase):
            name = "fake"
            description = "test skill"

            def can_handle(self, ctx):
                return True

            def build_prompt_addon(self, ctx):
                return SkillResult(prompt_addon="FAKE SKILL ACTIVE")

        registry.register(FakeSkill())
        assert "fake" in registry.all_skill_names


# ─────────────────────────────────────────────────────────────────────────────
# Individual skills
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.unit
class TestIndividualSkills:

    def _ctx(self, message, intent="product_search", profile=None, slots=None):
        from app.services.skills.base_skill import SkillContext
        from app.services.memory_service import SlotState
        return SkillContext(
            message=message,
            intent=intent,
            slots=slots or SlotState(),
            customer_profile=profile or {},
            session_context={},
        )

    # StylistSkill
    def test_stylist_handles_outfit_intent(self):
        from app.services.skills.skills import StylistSkill
        skill = StylistSkill()
        assert skill.can_handle(self._ctx("show me shoes", "outfit_pairing"))

    def test_stylist_handles_match_keyword(self):
        from app.services.skills.skills import StylistSkill
        skill = StylistSkill()
        assert skill.can_handle(self._ctx("what matches my blue shirt?"))

    def test_stylist_does_not_handle_plain_order(self):
        from app.services.skills.skills import StylistSkill
        skill = StylistSkill()
        assert not skill.can_handle(self._ctx("where is my order?", "order_status"))

    def test_stylist_prompt_contains_fashion_vocabulary(self):
        from app.services.skills.skills import StylistSkill
        skill = StylistSkill()
        ctx = self._ctx("what pairs with my jeans?", "outfit_pairing")
        result = skill.build_prompt_addon(ctx)
        # Should contain content from outfit-pairing SKILL.md
        assert len(result.prompt_addon) > 100
        assert "SKILL: outfit-pairing" in result.prompt_addon

    # GiftAdvisorSkill
    def test_gift_advisor_handles_birthday_keyword(self):
        from app.services.skills.skills import GiftAdvisorSkill
        skill = GiftAdvisorSkill()
        assert skill.can_handle(self._ctx("birthday present for my wife"))

    def test_gift_advisor_handles_gift_intent(self):
        from app.services.skills.skills import GiftAdvisorSkill
        skill = GiftAdvisorSkill()
        assert skill.can_handle(self._ctx("x", "gift_finder"))

    def test_gift_advisor_extracts_recipient(self):
        from app.services.skills.skills import GiftAdvisorSkill
        skill = GiftAdvisorSkill()
        ctx = self._ctx("I need a gift for my dad who runs")
        result = skill.build_prompt_addon(ctx)
        assert "dad" in result.prompt_addon.lower()

    def test_gift_advisor_does_not_handle_self_purchase(self):
        from app.services.skills.skills import GiftAdvisorSkill
        skill = GiftAdvisorSkill()
        assert not skill.can_handle(self._ctx("show me Nike running shoes"))

    # SizeExpertSkill
    def test_size_expert_handles_wide_feet(self):
        from app.services.skills.skills import SizeExpertSkill
        skill = SizeExpertSkill()
        assert skill.can_handle(self._ctx("I have wide feet"))

    def test_size_expert_handles_size_intent(self):
        from app.services.skills.skills import SizeExpertSkill
        skill = SizeExpertSkill()
        assert skill.can_handle(self._ctx("x", "size_query"))

    def test_size_expert_detects_flat_feet(self):
        from app.services.skills.skills import SizeExpertSkill
        skill = SizeExpertSkill()
        ctx = self._ctx("I have flat feet, what should I get?")
        result = skill.build_prompt_addon(ctx)
        assert "flat" in result.metadata.get("foot_type", "")

    def test_size_expert_includes_brand_in_prompt(self):
        from app.services.skills.skills import SizeExpertSkill
        from app.services.memory_service import SlotState
        skill = SizeExpertSkill()
        ctx = self._ctx(
            "do Nike shoes run small?", "size_query",
            slots=SlotState(brand="Nike"),
        )
        result = skill.build_prompt_addon(ctx)
        assert "Nike" in result.prompt_addon

    # ReturningCustomerSkill
    def test_returning_customer_handles_returning_user(self):
        from app.services.skills.skills import ReturningCustomerSkill
        skill = ReturningCustomerSkill()
        ctx = self._ctx("x", profile={"preferred_brands": ["Nike"], "total_sessions": 5})
        assert skill.can_handle(ctx)

    def test_returning_customer_does_not_handle_guest(self):
        from app.services.skills.skills import ReturningCustomerSkill
        skill = ReturningCustomerSkill()
        assert not skill.can_handle(self._ctx("x", profile={}))

    def test_returning_customer_prompt_includes_brands(self):
        from app.services.skills.skills import ReturningCustomerSkill
        skill = ReturningCustomerSkill()
        ctx = self._ctx("show me shoes", profile={"preferred_brands": ["Nike", "Adidas"], "total_sessions": 3})
        result = skill.build_prompt_addon(ctx)
        assert "Nike" in result.prompt_addon

    # EmpathySkill
    def test_empathy_handles_escalation_intent(self):
        from app.services.skills.skills import EmpathySkill
        skill = EmpathySkill()
        assert skill.can_handle(self._ctx("x", "escalate_to_human"))

    def test_empathy_handles_frustrated_message(self):
        from app.services.skills.skills import EmpathySkill
        skill = EmpathySkill()
        assert skill.can_handle(self._ctx("this is terrible service"))

    def test_empathy_detects_wants_human(self):
        from app.services.skills.skills import EmpathySkill
        skill = EmpathySkill()
        ctx = self._ctx("I want to speak to a manager")
        result = skill.build_prompt_addon(ctx)
        assert result.metadata.get("wants_human") is True

    def test_empathy_no_escalation_for_normal_message(self):
        from app.services.skills.skills import EmpathySkill
        skill = EmpathySkill()
        ctx = self._ctx("show me Nike running shoes")
        result = skill.build_prompt_addon(ctx)
        assert result.metadata.get("wants_human") is False


# ─────────────────────────────────────────────────────────────────────────────
# Prompts library
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.unit
class TestPromptsLibrary:
    """
    Ensure all required prompts are defined and non-empty.
    These tests catch accidental deletions from prompts.py.
    """

    def test_tool_selection_prompt_exists(self):
        from app.services.skills.prompts import TOOL_SELECTION_PROMPT
        assert len(TOOL_SELECTION_PROMPT) > 100

    def test_response_base_prompt_exists(self):
        from app.services.skills.prompts import RESPONSE_BASE_PROMPT
        assert len(RESPONSE_BASE_PROMPT) > 100

    def test_skill_stylist_prompt_exists(self):
        from app.services.skills.prompts import SKILL_STYLIST_PROMPT
        assert "STYLIST" in SKILL_STYLIST_PROMPT.upper()

    def test_skill_gift_advisor_prompt_exists(self):
        from app.services.skills.prompts import SKILL_GIFT_ADVISOR_PROMPT
        assert "GIFT" in SKILL_GIFT_ADVISOR_PROMPT.upper()

    def test_skill_size_expert_prompt_exists(self):
        from app.services.skills.prompts import SKILL_SIZE_EXPERT_PROMPT
        assert "SIZE" in SKILL_SIZE_EXPERT_PROMPT.upper()

    def test_skill_returning_customer_prompt_exists(self):
        from app.services.skills.prompts import SKILL_RETURNING_CUSTOMER_PROMPT
        assert "RETURNING" in SKILL_RETURNING_CUSTOMER_PROMPT.upper()

    def test_skill_empathy_prompt_exists(self):
        from app.services.skills.prompts import SKILL_EMPATHY_PROMPT
        assert "EMPATHY" in SKILL_EMPATHY_PROMPT.upper()

    def test_tool_selection_mentions_all_tools(self):
        from app.services.skills.prompts import TOOL_SELECTION_PROMPT
        required_tools = [
            "search_products", "outfit_pairing", "gift_finder",
            "order_lookup", "return_request", "policy_faq",
            "escalate_to_human", "clarify_question",
        ]
        for tool in required_tools:
            assert tool in TOOL_SELECTION_PROMPT, f"Missing tool in prompt: {tool}"

    def test_response_base_contains_citation_instructions(self):
        from app.services.skills.prompts import RESPONSE_BASE_PROMPT
        assert "[P1]" in RESPONSE_BASE_PROMPT


# ─────────────────────────────────────────────────────────────────────────────
# Suggestion chip DTO validation
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.unit
class TestSuggestionDTO:

    def test_chip_label_max_length_enforced(self):
        from app.api.dto.suggestion_dto import SuggestionChip
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            SuggestionChip(
                label="x" * 41,   # 41 chars — over limit
                message="valid message",
            )

    def test_chip_message_max_length_enforced(self):
        from app.api.dto.suggestion_dto import SuggestionChip
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            SuggestionChip(
                label="valid",
                message="x" * 501,  # over 500 char limit
            )

    def test_chip_valid_creation(self):
        from app.api.dto.suggestion_dto import SuggestionChip
        chip = SuggestionChip(label="Find my size", message="What size should I get?", icon="📏")
        assert chip.label == "Find my size"
        assert chip.chip_type == "quick_reply"  # default

    def test_chip_types_are_valid(self):
        from app.api.dto.suggestion_dto import SuggestionChip
        for chip_type in ("quick_reply", "refine", "action", "navigate"):
            chip = SuggestionChip(label="Test", message="test", chip_type=chip_type)
            assert chip.chip_type == chip_type

    def test_invalid_chip_type_rejected(self):
        from app.api.dto.suggestion_dto import SuggestionChip
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            SuggestionChip(label="Test", message="test", chip_type="invalid_type")
