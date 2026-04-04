"""
SSE streaming adapter for the LangGraph agent.

Translates graph execution into Server-Sent Events:
  - node_progress: real-time status updates per node
  - token: streamed LLM response tokens
  - done: final response with products, suggestions, metadata
  - error: error messages

This replaces ChatService.handle_stream() entirely.
"""

from __future__ import annotations

import asyncio
import json
import time
from collections.abc import AsyncIterator

from app.api.dto.chat_dto import ChatRequest
from app.graph.graph import create_agent
from app.core.logging import get_logger

logger = get_logger(__name__)


def _sse(data: dict) -> str:
    """Format a dict as an SSE data event (single-line JSON)."""
    return f"data: {json.dumps(data, default=str, ensure_ascii=False)}\n\n"


async def stream_graph(request: ChatRequest, db) -> AsyncIterator[str]:
    """
    Execute the LangGraph agent and stream SSE events.

    Yields:
      ": heartbeat\\n\\n"                         — keep-alive
      "data: {"type":"node_progress",...}\\n\\n"   — node status updates
      "data: {"type":"token","content":"..."}\\n\\n" — response tokens
      "data: {"type":"done",...}\\n\\n"            — final response
      "data: {"type":"error",...}\\n\\n"           — errors
    """
    yield ": heartbeat\n\n"

    try:
        agent = create_agent(db)
        t_start = time.monotonic()

        # Run the graph and collect state updates
        # Stream node-by-node execution
        prev_node_status = ""

        async for event in agent.astream(
            {"request": request, "t_start": t_start},
            stream_mode="updates",
        ):
            # event is {node_name: {partial_state_update}}
            for node_name, update in event.items():
                if node_name == "__end__":
                    continue

                # Emit node progress
                status = update.get("node_status", "")
                if status and status != prev_node_status:
                    yield _sse({"type": "node_progress", "node": node_name, "status": status})
                    prev_node_status = status

                # If persist node returned a response, emit done event
                if node_name == "persist" and update.get("response"):
                    response = update["response"]
                    answer = response.answer if hasattr(response, "answer") else str(response)

                    # Stream the answer word by word for typewriter effect
                    words = answer.split(" ")
                    for i, word in enumerate(words):
                        token = word if i == 0 else " " + word
                        yield _sse({"type": "token", "content": token})
                        await asyncio.sleep(0.02)

                    # Emit done event with full metadata
                    done_data = {
                        "type": "done",
                        "message_id": str(response.message_id) if hasattr(response, "message_id") else "",
                        "session_id": str(response.session_id) if hasattr(response, "session_id") else "",
                        "answer_html": response.answer_html if hasattr(response, "answer_html") else answer,
                        "cited_products": (
                            [p.model_dump() if hasattr(p, "model_dump") else p for p in response.cited_products]
                            if hasattr(response, "cited_products") and response.cited_products
                            else []
                        ),
                        "suggestions": response.suggestions if hasattr(response, "suggestions") else [],
                        "intent": response.intent if hasattr(response, "intent") else "",
                        "checkout_data": response.checkout_data if hasattr(response, "checkout_data") else None,
                        "continue_url": response.continue_url if hasattr(response, "continue_url") else None,
                    }
                    yield _sse(done_data)

            # Heartbeat between long nodes
            yield ": heartbeat\n\n"

    except Exception as exc:
        logger.error("stream.graph_failed", error=str(exc))
        yield _sse({"type": "error", "content": "An unexpected error occurred. Please try again."})
