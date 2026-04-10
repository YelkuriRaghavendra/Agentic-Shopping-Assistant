"""Support agent — orders, returns, policies, escalation."""

from pathlib import Path

from langchain_core.language_models import BaseChatModel
from langgraph.prebuilt import create_react_agent

from app.agent.tools.support_tools import (
    create_escalate_tool,
    create_order_history_tool,
    create_order_lookup_tool,
    create_policy_faq_tool,
    create_return_request_tool,
)
from app.clients.rag_client import RAGClient

_PROMPT_PATH = Path(__file__).parent.parent.parent / "config" / "agent_prompts" / "support.md"


def create_support_agent(llm: BaseChatModel, rag_client: RAGClient):
    tools = [
        create_order_lookup_tool(),
        create_order_history_tool(rag_client),
        create_return_request_tool(rag_client),
        create_policy_faq_tool(rag_client),
        create_escalate_tool(),
    ]
    prompt = _PROMPT_PATH.read_text(encoding="utf-8")
    return create_react_agent(model=llm, tools=tools, prompt=prompt)
