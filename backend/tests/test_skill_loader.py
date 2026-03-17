"""
Tests for the skill loader and agent architecture.

Verifies:
  - SkillLoader reads SKILL.md files correctly
  - All expected skills, agents, and commands have their files
  - Skills fall back to inline prompts when SKILL.md missing
  - Skills load the correct SKILL.md file when present

Marks:
  @pytest.mark.unit — no DB, no HTTP, no LLM
"""

import pytest
from pathlib import Path


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture
def loader():
    from app.agent.skill_loader import SkillLoader
    return SkillLoader()


@pytest.fixture
def agent_root():
    return Path(__file__).parent.parent / "app" / "agent"


# ─────────────────────────────────────────────────────────────────────────────
# File existence — every skill, agent, command must have its file
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.unit
class TestSkillFilesExist:
    """Catch missing files before they cause runtime failures."""

    @pytest.mark.parametrize("skill_name", [
        "outfit-pairing",
        "gift-finding",
        "size-fitting",
        "customer-empathy",
        "returning-customer",
        "tdd-workflow",
        "python-patterns",
        "api-design",
        "python-testing",
    ])
    def test_skill_md_exists(self, agent_root, skill_name):
        path = agent_root / "skills" / skill_name / "SKILL.md"
        assert path.exists(), f"Missing: {path}"

    @pytest.mark.parametrize("agent_name", [
        "tdd-guide",
        "stylist-agent",
        "gift-advisor-agent",
        "size-expert-agent",
    ])
    def test_agent_md_exists(self, agent_root, agent_name):
        path = agent_root / "agents" / f"{agent_name}.md"
        assert path.exists(), f"Missing: {path}"

    @pytest.mark.parametrize("command_name", [
        "tdd",
        "style",
        "gift",
        "size",
    ])
    def test_command_md_exists(self, agent_root, command_name):
        path = agent_root / "commands" / f"{command_name}.md"
        assert path.exists(), f"Missing: {path}"


# ─────────────────────────────────────────────────────────────────────────────
# SkillLoader — reading files
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.unit
class TestSkillLoader:

    def test_load_skill_returns_string(self, loader):
        content = loader.load_skill("tdd-workflow")
        assert isinstance(content, str)
        assert len(content) > 100

    def test_load_skill_contains_expected_content(self, loader):
        content = loader.load_skill("tdd-workflow")
        # TDD skill should mention the cycle
        assert "RED" in content
        assert "GREEN" in content
        assert "REFACTOR" in content

    def test_load_outfit_pairing_skill(self, loader):
        content = loader.load_skill("outfit-pairing")
        assert "colour" in content.lower() or "color" in content.lower()

    def test_load_gift_finding_skill(self, loader):
        content = loader.load_skill("gift-finding")
        assert "recipient" in content.lower()

    def test_load_size_fitting_skill(self, loader):
        content = loader.load_skill("size-fitting")
        assert "Nike" in content

    def test_load_python_patterns_skill(self, loader):
        content = loader.load_skill("python-patterns")
        assert "type hint" in content.lower() or "type_hint" in content.lower() or "Type Hints" in content

    def test_load_api_design_skill(self, loader):
        content = loader.load_skill("api-design")
        assert "status code" in content.lower() or "Status Code" in content

    def test_load_python_testing_skill(self, loader):
        content = loader.load_skill("python-testing")
        assert "pytest" in content.lower()

    def test_load_agent(self, loader):
        content = loader.load_agent("tdd-guide")
        assert len(content) > 100

    def test_load_command(self, loader):
        content = loader.load_command("tdd")
        assert "/tdd" in content

    def test_load_for_prompt_wraps_with_markers(self, loader):
        content = loader.load_skill_for_prompt("tdd-workflow")
        assert "--- SKILL: tdd-workflow ---" in content
        assert "--- END SKILL ---" in content

    def test_load_for_prompt_contains_skill_content(self, loader):
        content = loader.load_skill_for_prompt("tdd-workflow")
        assert "RED" in content

    def test_missing_skill_raises_file_not_found(self, loader):
        with pytest.raises(FileNotFoundError):
            loader.load_skill("non-existent-skill")

    def test_missing_skill_error_message_is_helpful(self, loader):
        with pytest.raises(FileNotFoundError) as exc_info:
            loader.load_skill("non-existent-skill")
        assert "SKILL.md" in str(exc_info.value)
        assert "Create" in str(exc_info.value)

    def test_list_skills_returns_all_skills(self, loader):
        skills = loader.list_skills()
        assert "tdd-workflow" in skills
        assert "outfit-pairing" in skills
        assert "gift-finding" in skills
        assert "size-fitting" in skills
        assert "python-patterns" in skills
        assert "api-design" in skills
        assert "python-testing" in skills

    def test_list_agents_returns_all_agents(self, loader):
        agents = loader.list_agents()
        assert "tdd-guide" in agents
        assert "stylist-agent" in agents
        assert "gift-advisor-agent" in agents
        assert "size-expert-agent" in agents

    def test_list_commands_returns_all_commands(self, loader):
        commands = loader.list_commands()
        assert "tdd" in commands
        assert "style" in commands
        assert "gift" in commands
        assert "size" in commands

    def test_loader_caches_after_first_read(self, loader):
        """Second read should not hit the filesystem."""
        content1 = loader.load_skill("tdd-workflow")
        content2 = loader.load_skill("tdd-workflow")
        assert content1 is content2   # same object — from cache

    def test_clear_cache_forces_reload(self, loader):
        content1 = loader.load_skill("tdd-workflow")
        loader.clear_cache()
        content2 = loader.load_skill("tdd-workflow")
        assert content1 == content2   # same content but different object
        assert content1 is not content2


# ─────────────────────────────────────────────────────────────────────────────
# Skill SKILL.md content validation
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.unit
class TestSkillMdContent:
    """
    Validates SKILL.md files contain the expected sections.
    Prevents broken skill files being silently loaded.
    """

    def test_tdd_skill_has_red_green_refactor(self, loader):
        content = loader.load_skill("tdd-workflow")
        for section in ["RED", "GREEN", "REFACTOR"]:
            assert section in content, f"TDD SKILL.md missing section: {section}"

    def test_tdd_skill_has_coverage_guidance(self, loader):
        content = loader.load_skill("tdd-workflow")
        assert "80" in content or "coverage" in content.lower()

    def test_outfit_skill_has_colour_table(self, loader):
        content = loader.load_skill("outfit-pairing")
        assert "Blue" in content or "blue" in content
        assert "Navy" in content or "navy" in content

    def test_outfit_skill_has_search_rule(self, loader):
        content = loader.load_skill("outfit-pairing")
        # Should have the rule about NOT searching the same colour
        assert "never search" in content.lower() or "search query rule" in content.lower()

    def test_gift_skill_has_price_tiers(self, loader):
        content = loader.load_skill("gift-finding")
        # Should mention budget/price options
        assert "$" in content or "budget" in content.lower()

    def test_size_skill_has_brand_table(self, loader):
        content = loader.load_skill("size-fitting")
        for brand in ["Nike", "Adidas", "Converse"]:
            assert brand in content, f"Size SKILL.md missing brand: {brand}"

    def test_python_patterns_skill_has_type_hints(self, loader):
        content = loader.load_skill("python-patterns")
        assert "Type Hints" in content or "type hints" in content.lower()

    def test_python_patterns_skill_has_anti_patterns(self, loader):
        content = loader.load_skill("python-patterns")
        assert "anti" in content.lower() or "avoid" in content.lower()

    def test_api_design_skill_has_status_codes(self, loader):
        content = loader.load_skill("api-design")
        assert "200" in content
        assert "404" in content
        assert "422" in content

    def test_api_design_skill_has_checklist(self, loader):
        content = loader.load_skill("api-design")
        assert "checklist" in content.lower() or "[ ]" in content

    def test_python_testing_skill_has_fixtures(self, loader):
        content = loader.load_skill("python-testing")
        assert "@pytest.fixture" in content or "fixture" in content.lower()

    def test_python_testing_skill_has_marks(self, loader):
        content = loader.load_skill("python-testing")
        assert "pytest.mark" in content or "@pytest.mark" in content

    def test_empathy_skill_has_escalation_guidance(self, loader):
        content = loader.load_skill("customer-empathy")
        assert "escalat" in content.lower()

    def test_empathy_skill_has_language_examples(self, loader):
        content = loader.load_skill("customer-empathy")
        assert "frustrat" in content.lower()


# ─────────────────────────────────────────────────────────────────────────────
# Skills use SKILL.md (integration between skill class and loader)
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.unit
class TestSkillsLoadFromMd:
    """
    Verify each skill class loads from its SKILL.md file
    and falls back gracefully when the file is missing.
    """

    def _ctx(self, message, intent="product_search"):
        from app.services.skills.base_skill import SkillContext
        from app.services.memory_service import SlotState
        return SkillContext(
            message=message,
            intent=intent,
            slots=SlotState(),
            customer_profile={},
            session_context={},
        )

    def test_stylist_skill_loads_outfit_pairing_md(self):
        from app.services.skills.skills import StylistSkill
        skill = StylistSkill()
        ctx = self._ctx("what matches my blue shirt?", "outfit_pairing")
        result = skill.build_prompt_addon(ctx)
        # Should contain content from the SKILL.md file
        assert len(result.prompt_addon) > 50
        assert "--- SKILL: outfit-pairing ---" in result.prompt_addon

    def test_gift_advisor_skill_loads_gift_finding_md(self):
        from app.services.skills.skills import GiftAdvisorSkill
        skill = GiftAdvisorSkill()
        ctx = self._ctx("gift for my dad", "gift_finder")
        result = skill.build_prompt_addon(ctx)
        assert "--- SKILL: gift-finding ---" in result.prompt_addon

    def test_size_expert_skill_loads_size_fitting_md(self):
        from app.services.skills.skills import SizeExpertSkill
        skill = SizeExpertSkill()
        ctx = self._ctx("do Nike shoes run small?", "size_query")
        result = skill.build_prompt_addon(ctx)
        assert "--- SKILL: size-fitting ---" in result.prompt_addon

    def test_empathy_skill_loads_customer_empathy_md(self):
        from app.services.skills.skills import EmpathySkill
        skill = EmpathySkill()
        ctx = self._ctx("this is terrible service", "order_status")
        result = skill.build_prompt_addon(ctx)
        assert "--- SKILL: customer-empathy ---" in result.prompt_addon

    def test_returning_customer_skill_loads_returning_customer_md(self):
        from app.services.skills.skills import ReturningCustomerSkill
        from app.services.skills.base_skill import SkillContext
        from app.services.memory_service import SlotState
        skill = ReturningCustomerSkill()
        ctx = SkillContext(
            message="show me shoes",
            intent="product_search",
            slots=SlotState(),
            customer_profile={"preferred_brands": ["Nike"], "total_sessions": 3},
            session_context={},
        )
        result = skill.build_prompt_addon(ctx)
        assert "--- SKILL: returning-customer ---" in result.prompt_addon

    def test_skill_prompt_contains_md_content_and_context(self):
        """Skill prompt = SKILL.md content + dynamic context appended."""
        from app.services.skills.skills import GiftAdvisorSkill
        skill = GiftAdvisorSkill()
        ctx = self._ctx("birthday gift for my dad who runs", "gift_finder")
        result = skill.build_prompt_addon(ctx)
        # Should contain SKILL.md content
        assert "--- SKILL: gift-finding ---" in result.prompt_addon
        # Should also contain dynamic context
        assert "dad" in result.prompt_addon.lower()

    def test_fallback_to_inline_when_skill_file_missing(self, tmp_path):
        """If SKILL.md file is missing, skill falls back to inline prompt."""
        from app.agent.skill_loader import SkillLoader
        from app.services.skills.skills import StylistSkill
        from app.services.skills.base_skill import SkillContext
        from app.services.memory_service import SlotState

        # Create a loader pointing at an empty directory
        empty_root = tmp_path / "agent"
        (empty_root / "skills").mkdir(parents=True)

        # Patch the skill_loader used inside the skill
        import app.agent.skill_loader as loader_module
        original_loader = loader_module.skill_loader
        loader_module.skill_loader = SkillLoader(agent_root=empty_root)

        try:
            skill = StylistSkill()
            ctx = SkillContext(
                message="what matches?",
                intent="outfit_pairing",
                slots=SlotState(),
                customer_profile={},
                session_context={},
            )
            result = skill.build_prompt_addon(ctx)
            # Should fall back to inline prompt — not crash
            assert len(result.prompt_addon) > 0
        finally:
            loader_module.skill_loader = original_loader
