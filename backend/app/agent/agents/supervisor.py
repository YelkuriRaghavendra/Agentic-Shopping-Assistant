"""
Supervisor agent — routes messages to the correct domain agent.
Uses cheap model for classification. Falls back to keyword matching for commerce intents.
"""

import json
from pathlib import Path

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage

from app.config.loader import commerce_intents as commerce_intents_config
from app.core.logging import get_logger

logger = get_logger(__name__)

_PROMPT_PATH = Path(__file__).parent.parent.parent / "config" / "agent_prompts" / "supervisor.md"
_VALID_AGENTS = {"shopping", "style_advisor", "gift_finder", "support", "checkout"}


def _classify_commerce_intent(text: str) -> str | None:
    ci = commerce_intents_config()
    text_lower = text.lower()
    for intent, keywords in ci["intent_keywords"].items():
        for kw in keywords:
            if kw in text_lower:
                return intent
    return None


def _is_purchase_confirmation(text: str, history_messages: list) -> bool:
    """Check if the user is confirming a purchase based on conversation context."""
    text_lower = text.lower().strip()
    confirm_words = {"yes", "yeah", "yep", "sure", "go ahead", "confirm", "ok", "okay", "do it", "proceed", "let's do it", "yes please"}
    if text_lower not in confirm_words:
        return False
    # Check if recent bot messages mention purchase/buy/checkout
    for msg in reversed(history_messages[-4:]):
        content = msg.content if hasattr(msg, "content") else str(msg)
        content_lower = content.lower()
        if any(w in content_lower for w in ["purchase", "buy", "checkout", "assist with the purchase", "confirm purchase", "place the order"]):
            return True
    return False


def create_supervisor_node(llm: BaseChatModel):
    prompt_text = _PROMPT_PATH.read_text(encoding="utf-8")

    async def supervisor_node(state: dict) -> dict:
        messages = state.get("messages", [])
        if not messages:
            return {"current_agent": "shopping", "intent": "general"}

        last_msg = messages[-1]
        user_text = last_msg.content if hasattr(last_msg, "content") else str(last_msg)

        # Fast path: checkout agent already active
        if state.get("current_agent") == "checkout":
            checkout_state = state.get("checkout_state", {})
            if checkout_state:
                logger.info("supervisor.checkout_active", message_preview=user_text[:60])
                return {"current_agent": "checkout", "intent": "checkout_continue"}

        # Fast path: commerce keyword match
        commerce_intent = _classify_commerce_intent(user_text)
        if commerce_intent:
            logger.info("supervisor.commerce_keyword", intent=commerce_intent)
            return {"current_agent": "checkout", "intent": commerce_intent}

        # Fast path: purchase confirmation ("yes" after "would you like to buy?")
        if _is_purchase_confirmation(user_text, messages):
            logger.info("supervisor.purchase_confirmation", message_preview=user_text[:60])
            return {"current_agent": "checkout", "intent": "checkout_initiate"}

        # LLM classification — include recent history for context
        history_for_llm = []
        for msg in messages[-6:]:  # last 3 turns
            if hasattr(msg, "type"):
                role = "user" if msg.type == "human" else "assistant"
            else:
                role = "user"
            history_for_llm.append({"role": role, "content": msg.content if hasattr(msg, "content") else str(msg)})

        try:
            llm_messages = [SystemMessage(content=prompt_text)]
            for h in history_for_llm[:-1]:  # history except last (added separately)
                if h["role"] == "user":
                    llm_messages.append(HumanMessage(content=h["content"]))
                else:
                    from langchain_core.messages import AIMessage
                    llm_messages.append(AIMessage(content=h["content"]))
            llm_messages.append(HumanMessage(content=user_text))

            response = await llm.ainvoke(llm_messages)
            raw = response.content.strip()
            data = json.loads(raw)
            agent = data.get("agent", "shopping")
            intent = data.get("intent", "general")

            if agent not in _VALID_AGENTS:
                agent = "shopping"

            logger.info("supervisor.routed", agent=agent, intent=intent)
            return {"current_agent": agent, "intent": intent}
        except (json.JSONDecodeError, Exception) as exc:
            logger.warning("supervisor.llm_fallback", error=str(exc))
            return {"current_agent": "shopping", "intent": "general"}

    return supervisor_node
