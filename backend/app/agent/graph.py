"""
Main LangGraph state graph.
Assembles all agents and nodes into a single compiled graph.
"""

import json
import re

from langgraph.graph import END, StateGraph

from langchain_core.messages import HumanMessage, SystemMessage

from app.agent.agents.gift_finder import create_gift_finder_agent
from app.agent.agents.shopping import create_shopping_agent
from app.agent.agents.style_advisor import create_style_advisor_agent
from app.agent.agents.suggestions import create_suggestions_node
from app.agent.agents.supervisor import create_supervisor_node
from app.agent.agents.support import create_support_agent
from app.agent.llm_factory import ModelTier, create_chat_model
from app.agent.nodes.citations import citations_node
from app.agent.nodes.guardrails import guardrails_node
from app.agent.state import AgentState
from app.clients.rag_client import RAGClient
from app.core.logging import get_logger

logger = get_logger(__name__)


def _route_after_guardrails(state: AgentState) -> str:
    if state.get("guardrail_status") == "blocked":
        return "post_process"
    return "supervisor"


def _route_after_supervisor(state: AgentState) -> str:
    agent = state.get("current_agent", "shopping")
    valid = {"shopping", "style_advisor", "gift_finder", "support", "checkout"}
    if agent in valid:
        return agent
    return "shopping"


def build_graph(rag_client: RAGClient, checkpointer=None):
    """Build and compile the multi-agent graph."""
    primary_llm = create_chat_model(ModelTier.PRIMARY)
    cheap_llm = create_chat_model(ModelTier.CHEAP)

    # Create agent nodes
    supervisor = create_supervisor_node(cheap_llm)
    suggestions = create_suggestions_node(cheap_llm)

    # Create react agents (these are compiled subgraphs)
    # We need wrapper functions that adapt between AgentState and the react agent's state
    shopping_agent = create_shopping_agent(primary_llm, rag_client)
    style_agent = create_style_advisor_agent(primary_llm, rag_client)
    gift_agent = create_gift_finder_agent(primary_llm, rag_client)
    support_agent = create_support_agent(primary_llm, rag_client)

    # Extract product cards from tool messages (embedded as <!--PRODUCTS:...-->)
    _PRODUCTS_RE = re.compile(r"<!--PRODUCTS:(.*?)-->", re.DOTALL)

    def _extract_products_from_messages(messages) -> list[dict]:
        """Extract product card JSON from tool messages."""
        all_products = []
        for msg in messages:
            if not hasattr(msg, "type"):
                continue
            content = msg.content if hasattr(msg, "content") else ""
            if not content or "<!--PRODUCTS:" not in content:
                continue
            for match in _PRODUCTS_RE.findall(content):
                try:
                    products = json.loads(match)
                    all_products.extend(products)
                except (json.JSONDecodeError, TypeError):
                    pass
        return all_products

    # Wrapper that invokes a react agent and extracts the response + product cards
    def _make_agent_wrapper(agent, agent_name: str):
        async def wrapper(state: dict) -> dict:
            messages = state.get("messages", [])
            try:
                result = await agent.ainvoke({"messages": messages})
            except Exception as exc:
                logger.error(
                    "agent_wrapper.failed",
                    agent=agent_name,
                    error=str(exc),
                    error_type=type(exc).__name__,
                )
                return {"agent_response": f"I'm having trouble right now. Please try again. ({exc})"}

            result_messages = result.get("messages", [])

            # Extract last AI message as agent_response
            ai_messages = [
                m for m in result_messages
                if hasattr(m, "type") and m.type == "ai" and m.content
            ]
            agent_response = ai_messages[-1].content if ai_messages else ""

            # Extract product cards from tool messages
            cited_products = _extract_products_from_messages(result_messages)

            return {
                "agent_response": agent_response,
                "messages": result_messages,
                "cited_products": cited_products,
            }

        return wrapper

    # Checkout node — uses primary LLM with checkout prompt to guide the flow
    checkout_prompt = (
        "You are a checkout assistant. The customer wants to complete a purchase.\n\n"
        "CHECKOUT FLOW:\n"
        "1. Confirm the product they want to buy (check conversation history)\n"
        "2. Ask for delivery address if not provided\n"
        "3. Present an order summary with product name, price, and delivery address\n"
        "4. Ask for final confirmation\n"
        "5. On confirmation, tell them the order is being processed\n\n"
        "Be concise and helpful. Reference the specific product from the conversation.\n"
        "If the customer wants to go back to shopping, let them know they can browse more products."
    )

    async def checkout_node(state: dict) -> dict:
        messages = state.get("messages", [])
        try:
            response = await primary_llm.ainvoke([
                SystemMessage(content=checkout_prompt),
                *messages,
            ])
            return {
                "agent_response": response.content,
                "current_agent": "checkout",
                "checkout_state": {"active": True},
            }
        except Exception as exc:
            logger.error("checkout_node.failed", error=str(exc))
            return {"agent_response": f"I'm having trouble with checkout. Please try again. ({exc})"}

    graph = StateGraph(AgentState)

    # Add nodes
    graph.add_node("guardrails", guardrails_node)
    graph.add_node("supervisor", supervisor)
    graph.add_node("shopping", _make_agent_wrapper(shopping_agent, "shopping"))
    graph.add_node("style_advisor", _make_agent_wrapper(style_agent, "style_advisor"))
    graph.add_node("gift_finder", _make_agent_wrapper(gift_agent, "gift_finder"))
    graph.add_node("support", _make_agent_wrapper(support_agent, "support"))
    graph.add_node("checkout", checkout_node)
    graph.add_node("post_process", citations_node)
    graph.add_node("suggestions", suggestions)

    # Entry point
    graph.set_entry_point("guardrails")

    # Edges
    graph.add_conditional_edges(
        "guardrails",
        _route_after_guardrails,
        {
            "supervisor": "supervisor",
            "post_process": "post_process",
        },
    )

    graph.add_conditional_edges(
        "supervisor",
        _route_after_supervisor,
        {
            "shopping": "shopping",
            "style_advisor": "style_advisor",
            "gift_finder": "gift_finder",
            "support": "support",
            "checkout": "checkout",
        },
    )

    for agent_name in ["shopping", "style_advisor", "gift_finder", "support", "checkout"]:
        graph.add_edge(agent_name, "post_process")

    graph.add_edge("post_process", "suggestions")
    graph.add_edge("suggestions", END)

    compiled = graph.compile(checkpointer=checkpointer)
    logger.info("graph.compiled")
    return compiled
