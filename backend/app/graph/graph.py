"""
Graph definition — the declarative agentic pipeline.

Replaces the monolithic ChatService with a visual, testable, checkpointed
state graph. Each step is a node, each decision is a conditional edge.

Graph:
  load_context → guardrails → [blocked? → persist]
                             → extract_intent → activate_skills
                             → decide_tool → [error? → persist]
                             → execute_tool → generate_response
                             → process_output → persist → END
"""

from __future__ import annotations

import os

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from app.graph.state import AgentState
from app.graph.nodes import (
    NodeDeps,
    load_context,
    check_guardrails,
    extract_intent,
    activate_skills,
    decide_tool,
    execute_tool,
    generate_response,
    process_output,
    persist,
)
from app.core.logging import get_logger

logger = get_logger(__name__)


# ═════════════════════════════════════════════════════════════════════════════
# Routing (conditional edges)
# ═════════════════════════════════════════════════════════════════════════════

def _after_guardrails(state: AgentState) -> str:
    return "persist" if state.get("input_blocked") else "extract_intent"


def _after_decide(state: AgentState) -> str:
    return "persist" if state.get("error") else "execute_tool"


# ═════════════════════════════════════════════════════════════════════════════
# Graph builder
# ═════════════════════════════════════════════════════════════════════════════

def build_graph(deps: NodeDeps) -> StateGraph:
    """
    Build the 9-node shopping agent graph.
    Node functions are wrapped to inject dependencies.
    """

    # Wrap each node to inject deps
    async def n_load_context(s): return await load_context(s, deps)
    async def n_guardrails(s): return await check_guardrails(s, deps)
    async def n_extract(s): return await extract_intent(s, deps)
    async def n_skills(s): return await activate_skills(s, deps)
    async def n_decide(s): return await decide_tool(s, deps)
    async def n_execute(s): return await execute_tool(s, deps)
    async def n_generate(s): return await generate_response(s, deps)
    async def n_output(s): return await process_output(s, deps)
    async def n_persist(s): return await persist(s, deps)

    g = StateGraph(AgentState)

    # Nodes
    g.add_node("load_context", n_load_context)
    g.add_node("check_guardrails", n_guardrails)
    g.add_node("extract_intent", n_extract)
    g.add_node("activate_skills", n_skills)
    g.add_node("decide_tool", n_decide)
    g.add_node("execute_tool", n_execute)
    g.add_node("generate_response", n_generate)
    g.add_node("process_output", n_output)
    g.add_node("persist", n_persist)

    # Entry
    g.set_entry_point("load_context")

    # Edges
    g.add_edge("load_context", "check_guardrails")
    g.add_conditional_edges("check_guardrails", _after_guardrails, {"persist": "persist", "extract_intent": "extract_intent"})
    g.add_edge("extract_intent", "activate_skills")
    g.add_edge("activate_skills", "decide_tool")
    g.add_conditional_edges("decide_tool", _after_decide, {"persist": "persist", "execute_tool": "execute_tool"})
    g.add_edge("execute_tool", "generate_response")
    g.add_edge("generate_response", "process_output")
    g.add_edge("process_output", "persist")
    g.add_edge("persist", END)

    return g


# ═════════════════════════════════════════════════════════════════════════════
# Agent factory
# ═════════════════════════════════════════════════════════════════════════════

def _get_checkpointer():
    """
    Get the appropriate checkpointer based on environment.
    Production: PostgresSaver (requires langgraph-checkpoint-postgres)
    Development: MemorySaver (in-memory, lost on restart)
    """
    pg_url = os.getenv("DATABASE_URL")

    if pg_url and os.getenv("USE_PG_CHECKPOINTER", "false").lower() == "true":
        try:
            from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
            logger.info("graph.checkpointer", type="postgres")
            return AsyncPostgresSaver.from_conn_string(pg_url)
        except ImportError:
            logger.warning("graph.postgres_checkpointer_unavailable, falling back to memory")

    logger.info("graph.checkpointer", type="memory")
    return MemorySaver()


def create_agent(db):
    """
    Create a compiled LangGraph agent.

    Usage:
        agent = create_agent(db_session)
        result = await agent.ainvoke(
            {"request": chat_request, "t_start": time.monotonic()},
            config={"configurable": {"thread_id": str(session_id)}},
        )
        response = result["response"]
    """
    # LangSmith tracing (auto-enabled if env vars set)
    if os.getenv("LANGSMITH_API_KEY"):
        os.environ.setdefault("LANGCHAIN_TRACING_V2", "true")
        os.environ.setdefault("LANGCHAIN_PROJECT", os.getenv("LANGCHAIN_PROJECT", "vikrai"))
        logger.info("graph.langsmith_enabled", project=os.getenv("LANGCHAIN_PROJECT"))

    deps = NodeDeps(db)
    graph = build_graph(deps)
    # Note: Checkpointing disabled because AgentState contains non-serializable
    # ORM objects (Session). State is already persisted via our repositories.
    # To enable, store only session_id in state and re-fetch in each node.
    compiled = graph.compile()

    logger.info("graph.compiled", nodes=len(compiled.nodes))
    return compiled
