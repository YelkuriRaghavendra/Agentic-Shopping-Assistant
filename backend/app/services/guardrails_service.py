"""
Guardrails service.

Input guardrails  — run before any LLM or RAG call
  1. Prompt injection
  2. Harmful content
  3. Off-topic (politics, medical, financial advice)
  4. PII warning (credit card, passwords — log but allow)

Output guardrails — run after LLM generates a response
  1. Citation hallucination (cited [P1] but nothing retrieved)
  2. Off-brand language (rude words in assistant reply)

Returns typed GuardrailResult — never raises exceptions.
The chat service decides what to do with the result.
"""

import re
from dataclasses import dataclass

from app.config.loader import guardrails_config
from app.core.logging import get_logger

logger = get_logger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Result type
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class GuardrailResult:
    passed:        bool
    category:      str = "passed"
    reason:        str | None = None
    safe_response: str | None = None


# ─────────────────────────────────────────────────────────────────────────────
# Compiled patterns — built once at import time
# ─────────────────────────────────────────────────────────────────────────────

def _compile_guardrail_patterns() -> dict:
    gc = guardrails_config()
    return {
        "injection": [re.compile(p, re.IGNORECASE) for p in gc["injection_patterns"]],
        "harmful": re.compile("|".join(gc["harmful_patterns"]), re.IGNORECASE),
        "off_topic": [re.compile(p, re.IGNORECASE) for p in gc["off_topic_signals"]],
        "shopping": re.compile("|".join(gc["shopping_signals"]), re.IGNORECASE),
        "credit_card": re.compile(gc["pii_patterns"]["credit_card"]),
        "password": re.compile(gc["pii_patterns"]["password"]),
    }


_PATTERNS = _compile_guardrail_patterns()

_CITATION_RE = re.compile(r'\[P\d+\]')


def _build_offbrand_re():
    from app.config.loader import business_rules
    words = business_rules()["guardrails"]["output"]["offbrand_words"]
    pattern = "|".join(re.escape(w) for w in words)
    return re.compile(rf'\b({pattern})\b', re.IGNORECASE)

_OFFBRAND_RE = _build_offbrand_re()

# Intent keywords — keyword-based, zero LLM cost
_INTENT_MAP: dict[str, list[str]] = guardrails_config()["intent_keywords"]


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────

class GuardrailsService:
    """
    Stateless service — all methods are pure functions.
    No DB, no HTTP, no external calls.
    """

    def check_input(self, message: str) -> GuardrailResult:
        msg = message.strip()
        responses = guardrails_config()["responses"]

        # 1. Prompt injection
        for pattern in _PATTERNS["injection"]:
            if pattern.search(msg):
                logger.warning("guardrails.injection_blocked", snippet=msg[:60])
                return GuardrailResult(
                    passed=False,
                    category="prompt_injection",
                    reason="Prompt injection pattern detected",
                    safe_response=responses["injection_blocked"],
                )

        # 2. Harmful content
        if _PATTERNS["harmful"].search(msg):
            logger.warning("guardrails.harmful_blocked", snippet=msg[:60])
            return GuardrailResult(
                passed=False,
                category="harmful",
                reason="Harmful content detected",
                safe_response=responses["harmful_blocked"],
            )

        # 3. Off-topic — only block if NO shopping signal present
        if not _PATTERNS["shopping"].search(msg):
            for signal_re in _PATTERNS["off_topic"]:
                if signal_re.search(msg):
                    logger.info("guardrails.off_topic", snippet=msg[:60])
                    return GuardrailResult(
                        passed=False,
                        category="off_topic",
                        reason="Off-topic message",
                        safe_response=self._off_topic_response(msg),
                    )

        # 4. PII warning — log but allow
        if _PATTERNS["credit_card"].search(msg) or _PATTERNS["password"].search(msg):
            logger.warning("guardrails.pii_detected", snippet=msg[:30])

        return GuardrailResult(passed=True, category="passed")

    def check_output(
        self,
        response_text: str,
        retrieved_titles: list[str],
    ) -> GuardrailResult:
        """
        Checks the LLM's generated response before sending to customer.
        """
        responses = guardrails_config()["responses"]

        # 1. Citation hallucination — cited a product that wasn't retrieved
        cited = _CITATION_RE.findall(response_text)
        if cited and not retrieved_titles:
            logger.warning("guardrails.hallucination_detected", citations=cited)
            return GuardrailResult(
                passed=False,
                category="hallucination",
                reason="LLM cited products but none were retrieved",
                safe_response=responses["generic_blocked"],
            )

        # 2. Off-brand language in assistant response
        if _OFFBRAND_RE.search(response_text):
            logger.warning("guardrails.offbrand_language")
            return GuardrailResult(
                passed=False,
                category="offbrand",
                reason="Off-brand language in response",
                safe_response=responses["generic_blocked"],
            )

        return GuardrailResult(passed=True, category="passed")

    def classify_intent(self, message: str) -> str:
        """
        Keyword-based intent classification.
        Zero LLM cost. Used for logging and routing hints only.
        """
        msg = message.lower()
        for intent, keywords in _INTENT_MAP.items():
            if any(kw in msg for kw in keywords):
                return intent
        return "unknown"

    def _off_topic_response(self, message: str) -> str:
        responses = guardrails_config()["responses"]
        greetings = guardrails_config()["intent_keywords"].get("general", [])
        if any(g in message.lower() for g in greetings):
            return responses["injection_blocked"]
        return responses["off_topic"]
