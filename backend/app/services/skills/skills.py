"""
Concrete skill implementations.

Each skill is self-contained:
  - Knows when it should activate (can_handle)
  - Knows what to add to the prompt (build_prompt_addon)
  - Has no dependencies on other skills

Skills in this file:
  StylistSkill            — outfit pairing, fashion advice, colour theory
  GiftAdvisorSkill        — buying for someone else
  SizeExpertSkill         — sizing, fit, foot types, brand quirks
  ReturningCustomerSkill  — personalisation for returning customers
  EmpathySkill            — frustrated or upset customers
"""

from __future__ import annotations
import re
from app.services.skills.base_skill import SkillBase, SkillContext, SkillResult
from app.services.skills.prompts import (
    SKILL_STYLIST_PROMPT,
    SKILL_GIFT_ADVISOR_PROMPT,
    SKILL_SIZE_EXPERT_PROMPT,
    SKILL_RETURNING_CUSTOMER_PROMPT,
    SKILL_EMPATHY_PROMPT,
)


class StylistSkill(SkillBase):
    """
    Activates when the customer wants style advice, outfit pairing,
    or fashion recommendations.

    Prompt loaded from: app/agent/skills/outfit-pairing/SKILL.md
    Agent definition:   app/agent/agents/stylist-agent.md
    Command:            app/agent/commands/style.md
    """

    name        = "stylist"
    description = "Personal stylist — outfit pairing, colour theory, fashion advice"

    _SIGNALS = [
        "outfit", "match", "matches", "goes with", "pair", "pairs with",
        "style", "look", "wear with", "i have a", "what to wear",
        "fashion", "combination", "put together", "coordinate",
    ]

    def can_handle(self, ctx: SkillContext) -> bool:
        msg = ctx.message.lower()
        return (
            ctx.intent == "outfit_pairing"
            or any(s in msg for s in self._SIGNALS)
        )

    def build_prompt_addon(self, ctx: SkillContext) -> SkillResult:
        from app.agent.skill_loader import skill_loader
        try:
            skill_content = skill_loader.load_skill_for_prompt("outfit-pairing")
        except FileNotFoundError:
            skill_content = SKILL_STYLIST_PROMPT  # fallback to inline prompt
        return SkillResult(
            prompt_addon=skill_content,
            metadata={"skill": self.name},
        )


class GiftAdvisorSkill(SkillBase):
    """
    Activates when the customer is buying for someone else.

    Shifts the LLM's focus to the recipient — their interests,
    occasion, age, and what would delight them.
    """

    name        = "gift_advisor"
    description = "Gift advisor — buying for someone else, occasion-aware recommendations"

    _SIGNALS = [
        "gift", "present", "birthday", "christmas", "anniversary",
        "for my", "for him", "for her", "for them", "for a friend",
        "for my dad", "for my mum", "for my mom", "for my wife",
        "for my husband", "for my partner", "surprise",
    ]

    def can_handle(self, ctx: SkillContext) -> bool:
        msg = ctx.message.lower()
        return (
            ctx.intent == "gift_finder"
            or any(s in msg for s in self._SIGNALS)
        )

    def build_prompt_addon(self, ctx: SkillContext) -> SkillResult:
        from app.agent.skill_loader import skill_loader
        try:
            skill_content = skill_loader.load_skill_for_prompt("gift-finding")
        except FileNotFoundError:
            skill_content = SKILL_GIFT_ADVISOR_PROMPT

        addon = skill_content
        recipient = self._extract_recipient(ctx.message)
        if recipient:
            addon += f"\nRECIPIENT: {recipient}. Tailor all recommendations to them."

        return SkillResult(
            prompt_addon=addon,
            metadata={"skill": self.name, "recipient": recipient},
        )

    def _extract_recipient(self, message: str) -> str | None:
        match = re.search(
            r'for\s+my\s+([\w\s]+?)(?:\s+who|\s+that|$|,|\.)',
            message, re.IGNORECASE,
        )
        return match.group(1).strip() if match else None


class SizeExpertSkill(SkillBase):
    """
    Activates when the customer needs sizing guidance.

    Makes the LLM give specific, accurate sizing advice —
    brand quirks, foot conditions, between-sizes decisions.
    """

    name        = "size_expert"
    description = "Size and fit expert — sizing advice, foot conditions, brand quirks"

    _SIGNALS = [
        "size", "sizing", "fit", "fitting", "wide feet", "narrow feet",
        "flat feet", "high arch", "overpronation", "between sizes",
        "runs small", "runs large", "true to size", "half size",
        "size guide", "measurements", "what size", "which size",
    ]

    def can_handle(self, ctx: SkillContext) -> bool:
        msg = ctx.message.lower()
        return (
            ctx.intent == "size_query"
            or any(s in msg for s in self._SIGNALS)
        )

    def build_prompt_addon(self, ctx: SkillContext) -> SkillResult:
        from app.agent.skill_loader import skill_loader
        try:
            skill_content = skill_loader.load_skill_for_prompt("size-fitting")
        except FileNotFoundError:
            skill_content = SKILL_SIZE_EXPERT_PROMPT

        addon = skill_content
        if ctx.slots.brand and ctx.slots.brand.lower() != "any":
            addon += f"\nBRAND FOCUS: {ctx.slots.brand}. Include specific sizing notes for this brand."

        foot_type = self._detect_foot_type(ctx.message)
        if foot_type:
            addon += f"\nFOOT TYPE: {foot_type}. Prioritise recommendations for this condition."

        return SkillResult(
            prompt_addon=addon,
            metadata={
                "skill":     self.name,
                "brand":     ctx.slots.brand,
                "foot_type": foot_type,
            },
        )

    def _detect_foot_type(self, message: str) -> str | None:
        msg = message.lower()
        if "wide" in msg:
            return "wide"
        if "narrow" in msg:
            return "narrow"
        if "flat" in msg:
            return "flat"
        if "high arch" in msg:
            return "high arch"
        if "overpronat" in msg:
            return "overpronation"
        return None


class ReturningCustomerSkill(SkillBase):
    """
    Activates when the customer has a known profile with preferences.

    Prevents the LLM from asking for info it already has,
    and enables personalised responses.
    """

    name        = "returning_customer"
    description = "Personalisation for returning customers with known preferences"

    def can_handle(self, ctx: SkillContext) -> bool:
        # Activate when we have meaningful profile data
        profile = ctx.customer_profile
        return bool(
            profile.get("preferred_brands")
            or profile.get("usual_sizes")
            or profile.get("total_sessions", 0) > 1
        )

    def build_prompt_addon(self, ctx: SkillContext) -> SkillResult:
        from app.agent.skill_loader import skill_loader
        try:
            skill_content = skill_loader.load_skill_for_prompt("returning-customer")
        except FileNotFoundError:
            skill_content = SKILL_RETURNING_CUSTOMER_PROMPT

        profile  = ctx.customer_profile
        brands   = profile.get("preferred_brands", [])
        sizes    = profile.get("usual_sizes", {})
        sessions = profile.get("total_sessions", 0)

        context_lines: list[str] = []
        if brands:
            context_lines.append(f"- Preferred brands: {', '.join(brands[:3])}")
        if sizes:
            size_str = ", ".join(f"{k} size {v}" for k, v in sizes.items())
            context_lines.append(f"- Usual sizes: {size_str}")
        if profile.get("price_sensitivity"):
            context_lines.append(f"- Price range: {profile['price_sensitivity']}")
        if profile.get("favourite_category"):
            context_lines.append(f"- Usually shops for: {profile['favourite_category']}")

        profile_summary = "\n".join(context_lines)
        addon = skill_content + f"\nKNOWN CUSTOMER DATA:\n{profile_summary}"

        return SkillResult(
            prompt_addon=addon,
            metadata={
                "skill":    self.name,
                "sessions": sessions,
                "brands":   brands[:2],
            },
        )


class EmpathySkill(SkillBase):
    """
    Activates when the customer shows signs of frustration or distress.

    Shifts the LLM's tone to be more empathetic and solution-focused
    rather than product-focused.
    """

    name        = "empathy"
    description = "Empathetic support for frustrated or upset customers"

    _FRUSTRATION_SIGNALS = [
        "terrible", "awful", "horrible", "disgusting", "worst",
        "useless", "garbage", "rubbish", "broken", "damaged",
        "never again", "waste of money", "ripped off", "scam",
        "angry", "furious", "unacceptable", "ridiculous", "ridiculus",
        "still waiting", "been waiting", "where is my", "3 weeks",
        "2 weeks", "a week ago", "spoke to someone", "no one helped",
        "your service is", "your company is",
    ]

    _ESCALATION_SIGNALS = [
        "speak to", "talk to", "manager", "supervisor",
        "real person", "human", "escalate",
    ]

    def can_handle(self, ctx: SkillContext) -> bool:
        msg = ctx.message.lower()
        return (
            ctx.intent == "escalate_to_human"
            or any(s in msg for s in self._FRUSTRATION_SIGNALS)
            or any(s in msg for s in self._ESCALATION_SIGNALS)
        )

    def build_prompt_addon(self, ctx: SkillContext) -> SkillResult:
        from app.agent.skill_loader import skill_loader
        try:
            skill_content = skill_loader.load_skill_for_prompt("customer-empathy")
        except FileNotFoundError:
            skill_content = SKILL_EMPATHY_PROMPT

        escalation_signals = self._ESCALATION_SIGNALS
        msg = ctx.message.lower()
        wants_human = any(s in msg for s in escalation_signals)

        addon = skill_content
        if wants_human:
            addon += (
                "\nCRITICAL: Customer has asked to speak to a human. "
                "Acknowledge this, then offer to connect them. "
                "Do not try to resolve the issue yourself — escalate."
            )

        return SkillResult(
            prompt_addon=addon,
            metadata={
                "skill":       self.name,
                "wants_human": wants_human,
            },
        )
