"""
Base skill interface.

A skill is a focused capability the agent can activate.
Each skill has:
  - A name and description (used to decide when to activate it)
  - Its own system prompt (modifies how the LLM responds)
  - A can_handle() method (rule-based check, zero LLM cost)
  - Optional tool overrides (some skills use different tools)

Skills are composable — multiple skills can be active at once.
The agent picks which skills are relevant, then merges their prompts.

Adding a new skill:
  1. Create a class inheriting SkillBase in this directory
  2. Register it in SkillRegistry
  That's it — no other changes needed.
"""

from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from app.services.memory_service import SlotState


@dataclass
class SkillContext:
    """
    Everything a skill knows about the current conversation.
    Passed to can_handle() and build_prompt_addon().
    """
    message:          str
    intent:           str
    slots:            SlotState
    customer_profile: dict
    session_context:  dict
    turn_count:       int = 0


@dataclass
class SkillResult:
    """
    What a skill contributes to the response.
    Multiple active skills have their results merged.
    """
    # Extra text appended to the system prompt
    prompt_addon:     str = ""
    # Extra tool definitions this skill provides (merged with base tools)
    extra_tools:      list[dict] = field(default_factory=list)
    # Metadata logged for debugging
    metadata:         dict = field(default_factory=dict)


class SkillBase(ABC):
    """
    Abstract base class every skill must implement.

    Rules:
      - can_handle() must be pure and fast (no IO, no LLM)
      - build_prompt_addon() must be deterministic
      - Skills must be stateless — all state comes from SkillContext
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique skill identifier. snake_case."""

    @property
    @abstractmethod
    def description(self) -> str:
        """One-sentence description shown in logs and docs."""

    @abstractmethod
    def can_handle(self, ctx: SkillContext) -> bool:
        """
        Return True if this skill should be active for this context.
        Must be fast — called on every message before any LLM call.
        """

    @abstractmethod
    def build_prompt_addon(self, ctx: SkillContext) -> SkillResult:
        """
        Build the prompt addition for this skill.
        Called only when can_handle() returns True.
        """

    def __repr__(self) -> str:
        return f"<Skill:{self.name}>"
