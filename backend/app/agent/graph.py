"""
Main LangGraph state graph.
Assembles all agents and nodes into a single compiled graph.
"""

from langgraph.graph import END, StateGraph

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

    # Wrapper that invokes a react agent and extracts the response
    def _make_agent_wrapper(agent):
        async def wrapper(state: dict) -> dict:
            messages = state.get("messages", [])
            result = await agent.ainvoke({"messages": messages})
            # Extract the last AI message as agent_response
            ai_messages = [
                m
                for m in result.get("messages", [])
                if hasattr(m, "type") and m.type == "ai"
            ]
            agent_response = ai_messages[-1].content if ai_messages else ""
            return {"agent_response": agent_response, "messages": result.get("messages", [])}

        return wrapper

    graph = StateGraph(AgentState)

    # Add nodes
    graph.add_node("guardrails", guardrails_node)
    graph.add_node("supervisor", supervisor)
    graph.add_node("shopping", _make_agent_wrapper(shopping_agent))
    graph.add_node("style_advisor", _make_agent_wrapper(style_agent))
    graph.add_node("gift_finder", _make_agent_wrapper(gift_agent))
    graph.add_node("support", _make_agent_wrapper(support_agent))
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
            "checkout": "post_process",  # checkout handled per-request
        },
    )

    for agent_name in ["shopping", "style_advisor", "gift_finder", "support"]:
        graph.add_edge(agent_name, "post_process")

    graph.add_edge("post_process", "suggestions")
    graph.add_edge("suggestions", END)

    compiled = graph.compile(checkpointer=checkpointer)
    logger.info("graph.compiled")
    return compiled
