"""
LangGraph-based agentic shopping assistant.

Replaces the monolithic ChatService with a declarative state graph.
Each pipeline step is a node. Each decision is a conditional edge.

Usage:
    from app.graph import create_agent, stream_graph

    # Sync
    agent = create_agent(db)
    result = await agent.ainvoke({"request": req, "t_start": time.monotonic()})
    response = result["response"]

    # Streaming SSE
    async for event in stream_graph(request, db):
        yield event
"""

from app.graph.graph import build_graph, create_agent
from app.graph.streaming import stream_graph

__all__ = ["build_graph", "create_agent", "stream_graph"]
