"""
Suggestions agent — generates contextual suggestion chips.
Uses cheap model. Runs in parallel with citation processing.
"""

import json
from pathlib import Path

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage

from app.config.loader import memory_config
from app.core.logging import get_logger

logger = get_logger(__name__)

_PROMPT_PATH = Path(__file__).parent.parent.parent / "config" / "agent_prompts" / "suggestions.md"


def create_suggestions_node(llm: BaseChatModel):
    prompt_text = _PROMPT_PATH.read_text(encoding="utf-8")
    mc = memory_config()
    max_count = mc["suggestions"]["max_count"]
    max_label_len = mc["suggestions"]["label_max_length"]

    async def suggestions_node(state: dict) -> dict:
        intent = state.get("intent", "")
        slots = state.get("slots", {})
        agent_response = state.get("agent_response", "")
        shown = state.get("shown_products", [])
        current_agent = state.get("current_agent", "")

        context = (
            f"Intent: {intent}\nAgent: {current_agent}\n"
            f"Slots: {json.dumps(slots)}\nProducts shown: {len(shown)}\n"
            f"Agent response: {agent_response[:300]}\n"
        )

        try:
            response = await llm.ainvoke([
                SystemMessage(content=prompt_text),
                HumanMessage(content=context),
            ])
            data = json.loads(response.content.strip())
            suggestions = data.get("suggestions", [])
            valid = []
            for s in suggestions:
                if isinstance(s, dict) and s.get("label"):
                    valid.append({
                        "label": s["label"][:max_label_len],
                        "message": s.get("message", s["label"]),
                    })
                if len(valid) >= max_count:
                    break
            return {"suggestions": valid}
        except (json.JSONDecodeError, Exception) as exc:
            logger.warning("suggestions_agent.failed", error=str(exc))
            return {"suggestions": []}

    return suggestions_node
