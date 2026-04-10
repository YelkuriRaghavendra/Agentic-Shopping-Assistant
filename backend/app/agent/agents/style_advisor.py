"""Style advisor agent — outfit matching, size advice, style tips."""

from pathlib import Path

from langchain_core.language_models import BaseChatModel
from langgraph.prebuilt import create_react_agent

from app.agent.tools.shopping_tools import create_search_products_tool
from app.agent.tools.style_tools import create_outfit_pairing_tool, create_size_advice_tool
from app.clients.rag_client import RAGClient

_PROMPT_PATH = Path(__file__).parent.parent.parent / "config" / "agent_prompts" / "style_advisor.md"


def create_style_advisor_agent(llm: BaseChatModel, rag_client: RAGClient):
    tools = [
        create_outfit_pairing_tool(rag_client),
        create_size_advice_tool(rag_client),
        create_search_products_tool(rag_client),
    ]
    prompt = _PROMPT_PATH.read_text(encoding="utf-8")
    return create_react_agent(model=llm, tools=tools, prompt=prompt)
