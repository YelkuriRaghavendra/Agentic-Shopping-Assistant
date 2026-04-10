"""
Guardrails graph node.

Checks user input for injection, harmful content, PII, and off-topic messages.
Returns state updates: guardrail_status + optional agent_response (for blocked).
"""

import re

from app.config.loader import guardrails_config
from app.core.logging import get_logger

logger = get_logger(__name__)

_gc = guardrails_config()
_INJECTION_PHRASES = [p.lower() for p in _gc["injection_patterns"]]
_HARMFUL_RE = re.compile("|".join(_gc["harmful_patterns"]), re.IGNORECASE)
_OFF_TOPIC_RES = [re.compile(p, re.IGNORECASE) for p in _gc["off_topic_signals"]]
_SHOPPING_RE = re.compile("|".join(_gc["shopping_signals"]), re.IGNORECASE)
_CREDIT_CARD_RE = re.compile(_gc["pii_patterns"]["credit_card"])
_PASSWORD_RE = re.compile(_gc["pii_patterns"]["password"])
_RESPONSES = _gc["responses"]


def guardrails_node(state: dict) -> dict:
    messages = state.get("messages", [])
    if not messages:
        return {"guardrail_status": "passed"}

    last_msg = messages[-1]
    text = last_msg.content if hasattr(last_msg, "content") else str(last_msg)
    text_lower = text.lower()

    # 1. Injection check
    for phrase in _INJECTION_PHRASES:
        if phrase in text_lower:
            logger.warning("guardrails.injection_blocked", preview=text_lower[:80])
            return {"guardrail_status": "blocked", "agent_response": _RESPONSES["injection_blocked"]}

    # 2. Harmful content
    if _HARMFUL_RE.search(text_lower):
        logger.warning("guardrails.harmful_blocked", preview=text_lower[:80])
        return {"guardrail_status": "blocked", "agent_response": _RESPONSES["harmful_blocked"]}

    # 3. PII check (warn but don't block)
    if _CREDIT_CARD_RE.search(text) or _PASSWORD_RE.search(text):
        logger.warning("guardrails.pii_detected", preview=text[:40])

    # 4. Off-topic — only block if an explicit off-topic pattern matches
    #    AND no shopping signal is present. Short replies like "yes", "size 9",
    #    "open to anything" should pass through to the agent.
    has_shopping_signal = bool(_SHOPPING_RE.search(text_lower))
    if not has_shopping_signal:
        for pattern in _OFF_TOPIC_RES:
            if pattern.search(text_lower):
                logger.info("guardrails.off_topic", preview=text_lower[:80])
                return {"guardrail_status": "blocked", "agent_response": _RESPONSES["off_topic"]}

    return {"guardrail_status": "passed"}
