"""
Graph definition — the declarative pipeline.

This module defines the StateGraph, adds nodes and conditional edges,
and compiles it into a runnable agent. The graph replaces the monolithic
ChatService.handle() method with a clear, visual, testable pipeline.

Graph Structure:
    ┌────────────┐
    │ load_context│
    └─────┬──────┘
          ▼
    ┌────────────┐     ┌─────────────┐
    │ guardrails │──►  │   persist   │  (if blocked)
    └─────┬──────┘     └─────────────┘
          ▼
    ┌──────────────┐
    │extract_intent│
    └─────┬────────┘
          ▼
    ┌───────────────┐
    │activate_skills│
    └─────┬─────────┘
          ▼
    ┌────────────┐
    │ decide_tool│
    └─────┬──────┘
          ▼
    ┌────────────┐
    │execute_tool│  (for all tools including clarify/direct)
    └─────┬──────┘
          ▼
    ┌─────────────────┐
    │generate_response│
    └─────┬───────────┘
          ▼
    ┌──────────────┐
    │process_output│
    └─────┬────────┘
          ▼
    ┌─────────┐
    │ persist │
    └─────────┘
"""

from __future__ import annotations

import time
from functools import partial
from typing import Any

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
# Routing functions (conditional edges)
# ═════════════════════════════════════════════════════════════════════════════

def _route_after_guardrails(state: AgentState) -> str:
    """If input is blocked, skip straight to persist."""
    if state.get("input_blocked"):
        return "persist"
    return "extract_intent"


def _route_after_decide(state: AgentState) -> str:
    """After LLM decides tool, route to execute or handle error."""
    if state.get("error"):
        return "persist"
    return "execute_tool"


# ═════════════════════════════════════════════════════════════════════════════
# Graph builder
# ═════════════════════════════════════════════════════════════════════════════

def build_graph(deps: NodeDeps) -> StateGraph:
    """
    Build the shopping agent graph.

    Each node function is wrapped with `partial` to inject dependencies.
    LangGraph calls each node with (state) → partial dict.
    """

    # Wrap async nodes to inject deps
    async def _load_context(state: AgentState) -> dict:
        return await load_context(state, deps)

    async def _check_guardrails(state: AgentState) -> dict:
        return await check_guardrails(state, deps)

    async def _extract_intent(state: AgentState) -> dict:
        return await extract_intent(state, deps)

    async def _activate_skills(state: AgentState) -> dict:
        return await activate_skills(state, deps)

    async def _decide_tool(state: AgentState) -> dict:
        return await decide_tool(state, deps)

    async def _execute_tool(state: AgentState) -> dict:
        return await execute_tool(state, deps)

    async def _generate_response(state: AgentState) -> dict:
        return await generate_response(state, deps)

    async def _process_output(state: AgentState) -> dict:
        return await process_output(state, deps)

    async def _persist(state: AgentState) -> dict:
        return await persist(state, deps)

    # ── Build the graph ──────────────────────────────────────────────────
    graph = StateGraph(AgentState)

    # Add nodes
    graph.add_node("load_context", _load_context)
    graph.add_node("check_guardrails", _check_guardrails)
    graph.add_node("extract_intent", _extract_intent)
    graph.add_node("activate_skills", _activate_skills)
    graph.add_node("decide_tool", _decide_tool)
    graph.add_node("execute_tool", _execute_tool)
    graph.add_node("generate_response", _generate_response)
    graph.add_node("process_output", _process_output)
    graph.add_node("persist", _persist)

    # Set entry point
    graph.set_entry_point("load_context")

    # Add edges
    graph.add_edge("load_context", "check_guardrails")

    # Conditional: if blocked → persist, else → extract_intent
    graph.add_conditional_edges(
        "check_guardrails",
        _route_after_guardrails,
        {
            "persist": "persist",
            "extract_intent": "extract_intent",
        },
    )

    graph.add_edge("extract_intent", "activate_skills")
    graph.add_edge("activate_skills", "decide_tool")

    # Conditional: if error → persist, else → execute_tool
    graph.add_conditional_edges(
        "decide_tool",
        _route_after_decide,
        {
            "persist": "persist",
            "execute_tool": "execute_tool",
        },
    )

    graph.add_edge("execute_tool", "generate_response")
    graph.add_edge("generate_response", "process_output")
    graph.add_edge("process_output", "persist")

    # Persist is the final node
    graph.add_edge("persist", END)

    return graph


# ═════════════════════════════════════════════════════════════════════════════
# Agent factory
# ═════════════════════════════════════════════════════════════════════════════

def create_agent(db):
    """
    Create a compiled agent with checkpointing.

    Usage:
        agent = create_agent(db_session)
        result = await agent.ainvoke({
            "request": chat_request,
            "t_start": time.monotonic(),
        })
        response = result["response"]
    """
    deps = NodeDeps(db)
    graph = build_graph(deps)

    # In-memory checkpointer for development.
    # For production, use PostgresSaver or RedisSaver:
    #   from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
    #   checkpointer = AsyncPostgresSaver(conn_string)
    checkpointer = MemorySaver()

    compiled = graph.compile(checkpointer=checkpointer)

    logger.info("graph.compiled", nodes=len(compiled.nodes))
    return compiled
