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

from app.core.config import get_settings
from app.core.logging import get_logger

settings = get_settings()
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

_INJECTION_PATTERNS = [
    re.compile(p, re.IGNORECASE)
    for p in settings.BLOCKED_PATTERNS
]

_HARMFUL_RE = re.compile(
    r'\b(kill|murder|suicide|bomb|attack|threat|abuse|'
    r'harass|stalk|hack|exploit|malware|ransomware)\b',
    re.IGNORECASE,
)

_OFF_TOPIC_SIGNALS = [
    re.compile(r, re.IGNORECASE)
    for r in [
        r'\b(politics|election|president|government|war|military|vote|voting|democrat|republican)\b',
        r'\b(diagnos|disease|symptom|medication|prescription|therapy)\b',
        r'\b(stock\s*market|crypto|bitcoin|invest|trading|forex)\b',
        r'\b(porn|explicit|nude|naked)\b',
    ]
]

# Shopping signals — if present, message is allowed even if off-topic words appear
_SHOPPING_SIGNAL_RE = re.compile(
    r'\b(buy|purchase|order|product|price|brand|size|'
    r'delivery|shipping|return|refund|discount|gift|stock|'
    r'recommend|compare|review|available|shop|cart|checkout|'
    r'payment|item|sale|deal|offer)\b',
    re.IGNORECASE,
)

_CREDIT_CARD_RE = re.compile(r'\b(?:\d[ -]?){13,16}\b')
_PASSWORD_RE    = re.compile(
    r'\b(password|passwd|secret|token)\s*[:=]\s*\S+',
    re.IGNORECASE,
)

_CITATION_RE   = re.compile(r'\[P\d+\]')
def _build_offbrand_re():
    from app.config.loader import business_rules
    words = business_rules()["guardrails"]["output"]["offbrand_words"]
    pattern = "|".join(re.escape(w) for w in words)
    return re.compile(rf'\b({pattern})\b', re.IGNORECASE)

_OFFBRAND_RE = _build_offbrand_re()

# Intent keywords — keyword-based, zero LLM cost
_INTENT_MAP: list[tuple[list[str], str]] = [
    (["track", "where is my order", "order status", "shipment", "shipped"], "order_status"),
    (["return", "refund", "send back", "exchange"], "return_request"),
    (["price", "cost", "how much", "discount", "sale", "coupon", "deal"], "price_query"),
    (["vs", "versus", "compare", "difference between", "better"], "comparison"),
    (["hi", "hello", "hey", "good morning", "good evening", "howdy"], "greeting"),
    (["size", "fit", "wide", "narrow", "measurement"], "size_query"),
    (["buy", "purchase", "add to cart", "checkout"], "purchase_intent"),
    (["recommend", "suggest", "what should i", "help me find", "best"], "recommendation"),
    (["looking for", "find", "show me", "search", "want"], "product_search"),
]


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

        # 1. Prompt injection
        for pattern in _INJECTION_PATTERNS:
            if pattern.search(msg):
                logger.warning("guardrails.injection_blocked", snippet=msg[:60])
                return GuardrailResult(
                    passed=False,
                    category="prompt_injection",
                    reason="Prompt injection pattern detected",
                    safe_response=(
                        "I'm here to help you with shopping and orders. "
                        "What can I find for you today?"
                    ),
                )

        # 2. Harmful content
        if _HARMFUL_RE.search(msg):
            logger.warning("guardrails.harmful_blocked", snippet=msg[:60])
            return GuardrailResult(
                passed=False,
                category="harmful",
                reason="Harmful content detected",
                safe_response=(
                    "I can only help with shopping-related questions. "
                    "Please contact our support team if you need further assistance."
                ),
            )

        # 3. Off-topic — only block if NO shopping signal present
        if not _SHOPPING_SIGNAL_RE.search(msg):
            for signal_re in _OFF_TOPIC_SIGNALS:
                if signal_re.search(msg):
                    logger.info("guardrails.off_topic", snippet=msg[:60])
                    return GuardrailResult(
                        passed=False,
                        category="off_topic",
                        reason="Off-topic message",
                        safe_response=self._off_topic_response(msg),
                    )

        # 4. PII warning — log but allow
        if _CREDIT_CARD_RE.search(msg) or _PASSWORD_RE.search(msg):
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
        # 1. Citation hallucination — cited a product that wasn't retrieved
        cited = _CITATION_RE.findall(response_text)
        if cited and not retrieved_titles:
            logger.warning("guardrails.hallucination_detected", citations=cited)
            return GuardrailResult(
                passed=False,
                category="hallucination",
                reason="LLM cited products but none were retrieved",
                safe_response=(
                    "I wasn't able to find specific products for that query right now. "
                    "Would you like to try a different search?"
                ),
            )

        # 2. Off-brand language in assistant response
        if _OFFBRAND_RE.search(response_text):
            logger.warning("guardrails.offbrand_language")
            return GuardrailResult(
                passed=False,
                category="offbrand",
                reason="Off-brand language in response",
                safe_response=(
                    "I had trouble generating a response. "
                    "Could you rephrase your question?"
                ),
            )

        return GuardrailResult(passed=True, category="passed")

    def classify_intent(self, message: str) -> str:
        """
        Keyword-based intent classification.
        Zero LLM cost. Used for logging and routing hints only.
        """
        msg = message.lower()
        for keywords, intent in _INTENT_MAP:
            if any(kw in msg for kw in keywords):
                return intent
        return "unknown"

    def _off_topic_response(self, message: str) -> str:
        greetings = ["hi", "hello", "hey", "good morning", "good evening"]
        if any(g in message.lower() for g in greetings):
            return (
                "Hello! I'm your shopping assistant. "
                "I can help you find products, track orders, or answer shopping questions. "
                "What are you looking for today?"
            )
        return (
            "I'm your shopping assistant — I can help with products, "
            "orders, returns, and more. What can I help you find?"
        )
