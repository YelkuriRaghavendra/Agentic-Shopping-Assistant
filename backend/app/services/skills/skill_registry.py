"""
Skill registry.

Discovers which skills are relevant for a given message,
then merges their prompt addons into the base prompt.

Design:
  - Skills are evaluated in priority order
  - Multiple skills can be active simultaneously
  - Prompt addons are appended in order (later = higher priority)
  - Skills are stateless — no shared state between calls
"""

from __future__ import annotations

from app.services.skills.base_skill import SkillBase, SkillContext, SkillResult
from app.services.skills.skills import (
    StylistSkill,
    GiftAdvisorSkill,
    SizeExpertSkill,
    ReturningCustomerSkill,
    EmpathySkill,
)
from app.core.logging import get_logger

logger = get_logger(__name__)

# Ordered list — earlier skills have lower priority, later have higher
# EmpathySkill last so it always overrides tone when customer is frustrated
_ALL_SKILLS: list[SkillBase] = [
    ReturningCustomerSkill(),
    StylistSkill(),
    GiftAdvisorSkill(),
    SizeExpertSkill(),
    EmpathySkill(),
]


class SkillRegistry:
    """
    Evaluates all registered skills against the current context
    and merges the active ones into a combined prompt addon.
    """

    def __init__(self, skills: list[SkillBase] | None = None):
        self._skills = skills or _ALL_SKILLS

    def resolve(self, ctx: SkillContext) -> SkillResult:
        """
        Find all active skills for this context and merge their results.

        Returns a single SkillResult with:
          - Combined prompt_addon (all active skills' addons joined)
          - Merged extra_tools (union of all tool lists)
          - Metadata with list of active skill names (for logging)
        """
        active: list[tuple[SkillBase, SkillResult]] = []

        for skill in self._skills:
            if skill.can_handle(ctx):
                result = skill.build_prompt_addon(ctx)
                active.append((skill, result))

        if not active:
            return SkillResult()

        active_names = [s.name for s, _ in active]
        logger.info(
            "skills.activated",
            skills=active_names,
            intent=ctx.intent,
            turn=ctx.turn_count,
        )

        # Merge all results
        merged_addon = "\n".join(r.prompt_addon for _, r in active if r.prompt_addon)
        merged_tools = []
        seen_tool_names: set[str] = set()
        for _, r in active:
            for tool in r.extra_tools:
                name = tool.get("function", {}).get("name", "")
                if name not in seen_tool_names:
                    merged_tools.append(tool)
                    seen_tool_names.add(name)

        return SkillResult(
            prompt_addon=merged_addon,
            extra_tools=merged_tools,
            metadata={"active_skills": active_names},
        )

    def register(self, skill: SkillBase) -> None:
        """Add a new skill at runtime."""
        self._skills.append(skill)
        logger.info("skills.registered", skill=skill.name)

    @property
    def all_skill_names(self) -> list[str]:
        return [s.name for s in self._skills]
