"""Shopping agent — product discovery, comparison, stock checks."""

from pathlib import Path

from langchain_core.language_models import BaseChatModel
from langgraph.prebuilt import create_react_agent

from app.agent.tools.shopping_tools import (
    create_compare_products_tool,
    create_search_products_tool,
    create_stock_check_tool,
)
from app.clients.rag_client import RAGClient
from app.core.logging import get_logger

logger = get_logger(__name__)
_PROMPT_PATH = Path(__file__).parent.parent.parent / "config" / "agent_prompts" / "shopping.md"


def create_shopping_agent(llm: BaseChatModel, rag_client: RAGClient):
    tools = [
        create_search_products_tool(rag_client),
        create_compare_products_tool(rag_client),
        create_stock_check_tool(rag_client),
    ]
    prompt = _PROMPT_PATH.read_text(encoding="utf-8")
    agent = create_react_agent(model=llm, tools=tools, prompt=prompt)
    logger.info("shopping_agent.created", tools=[t.name for t in tools])
    return agent
