"""
Prompt library — every prompt string lives here.

This is the single file you edit to change how the agent talks.
No prompt strings anywhere else in the codebase.

Naming convention:
  TOOL_SELECTION_PROMPT     — main agent tool selection
  SKILL_<NAME>_PROMPT       — per-skill system prompt addon
  RESPONSE_<NAME>_PROMPT    — response generation instructions
"""

from app.config.loader import prompts

# ─────────────────────────────────────────────────────────────────────────────
# Main agent tool selection prompt
# ─────────────────────────────────────────────────────────────────────────────

TOOL_SELECTION_PROMPT = prompts()["system"]["tool_selection"]


# ─────────────────────────────────────────────────────────────────────────────
# Base response generation prompt
# ─────────────────────────────────────────────────────────────────────────────

RESPONSE_BASE_PROMPT = prompts()["system"]["response_base"]


# ─────────────────────────────────────────────────────────────────────────────
# Skill: Stylist
# Activated when: outfit pairing, style advice, gift for fashion lover
# ─────────────────────────────────────────────────────────────────────────────

SKILL_STYLIST_PROMPT = prompts()["skills"]["stylist"]


# ─────────────────────────────────────────────────────────────────────────────
# Skill: Gift Advisor
# Activated when: buying for someone else, gift, present, birthday, etc.
# ─────────────────────────────────────────────────────────────────────────────

SKILL_GIFT_ADVISOR_PROMPT = prompts()["skills"]["gift_advisor"]


# ─────────────────────────────────────────────────────────────────────────────
# Skill: Returning Customer
# Activated when: customer has profile data (past purchases, preferences)
# ─────────────────────────────────────────────────────────────────────────────

SKILL_RETURNING_CUSTOMER_PROMPT = prompts()["skills"]["returning_customer"]


# ─────────────────────────────────────────────────────────────────────────────
# Skill: Size Expert
# Activated when: customer asks about sizing, mentions foot type, fit concerns
# ─────────────────────────────────────────────────────────────────────────────

SKILL_SIZE_EXPERT_PROMPT = prompts()["skills"]["size_expert"]


# ─────────────────────────────────────────────────────────────────────────────
# Skill: Dispute / Frustration Handler
# Activated when: customer is frustrated, mentions complaint, poor experience
# ─────────────────────────────────────────────────────────────────────────────

SKILL_EMPATHY_PROMPT = prompts()["skills"]["empathy"]
