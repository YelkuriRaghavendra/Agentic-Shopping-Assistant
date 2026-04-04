"""
LangGraph-based agentic shopping assistant.

This module replaces the monolithic ChatService pipeline with a
declarative state graph. Each step of the pipeline is a node function
that reads from and writes to a shared AgentState.

Graph:
  load_context → guardrails → extract_intent → activate_skills
    → decide_tool → route_tool
      → [clarify]   → generate_response → process_output → persist
      → [direct]    → generate_response → process_output → persist
      → [commerce]  → handle_commerce   → persist
      → [tool]      → execute_tool → generate_response → process_output → persist
"""

from app.graph.graph import build_graph, create_agent

__all__ = ["build_graph", "create_agent"]
