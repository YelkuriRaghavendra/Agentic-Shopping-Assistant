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
import uuid
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

    Uses ``ainvoke`` for the full graph run while emitting timed progress
    events in parallel so the frontend typing indicator stays alive.

    Yields:
      ": heartbeat\\n\\n"                         — keep-alive
      "data: {"type":"node_progress",...}\\n\\n"   — node status updates
      "data: {"type":"token","content":"..."}\\n\\n" — response tokens
      "data: {"type":"done",...}\\n\\n"            — final response
      "data: {"type":"error",...}\\n\\n"           — errors
    """
    yield ": heartbeat\n\n"
    yield _sse({"type": "node_progress", "node": "start", "status": "Loading your profile..."})

    try:
        agent = create_agent(db)
        t_start = time.monotonic()

        # Thread ID for the checkpointer (use customer_id when available)
        thread_id = str(request.customer_id) if request.customer_id else str(uuid.uuid4())
        config = {"configurable": {"thread_id": thread_id}}

        # Run the full graph in a background task
        task = asyncio.create_task(
            agent.ainvoke({"request": request, "t_start": t_start}, config=config)
        )

        # Emit progress events at timed intervals while the graph runs
        stages = [
            (1.5, "Understanding your request..."),
            (3.0, "Searching products..."),
            (5.0, "Generating response..."),
            (8.0, "Almost there..."),
        ]
        stage_idx = 0

        while not task.done():
            await asyncio.sleep(0.5)
            elapsed = time.monotonic() - t_start
            if stage_idx < len(stages) and elapsed >= stages[stage_idx][0]:
                yield _sse({
                    "type": "node_progress",
                    "node": "pipeline",
                    "status": stages[stage_idx][1],
                })
                stage_idx += 1
            yield ": heartbeat\n\n"

        result = await task  # re-raise any exception from the graph

        response = result.get("response")
        if not response:
            yield _sse({"type": "error", "content": "Something went wrong. Please try again."})
            return

        # Signal that we are now streaming the answer
        yield _sse({"type": "node_progress", "node": "persist", "status": "Writing response..."})

        # Stream the answer word-by-word for typewriter effect
        answer = response.answer if hasattr(response, "answer") else str(response)
        words = answer.split(" ")
        for i, word in enumerate(words):
            token = word if i == 0 else " " + word
            yield _sse({"type": "token", "content": token})
            await asyncio.sleep(0.02)

        # Emit the final done event with full payload
        resp_dict = response.model_dump() if hasattr(response, "model_dump") else {}
        done_data = {
            "type": "done",
            "message_id": str(resp_dict.get("message_id", "")),
            "session_id": str(resp_dict.get("session_id", "")),
            "answer_html": resp_dict.get("answer_html", answer),
            "cited_products": resp_dict.get("cited_products", []),
            "suggestions": resp_dict.get("suggestions", []),
            "intent": resp_dict.get("intent", ""),
            "checkout_data": resp_dict.get("checkout_data"),
            "continue_url": resp_dict.get("continue_url"),
        }
        yield _sse(done_data)

    except Exception as exc:
        logger.error("stream.graph_failed", error=str(exc))
        yield _sse({"type": "error", "content": "An unexpected error occurred. Please try again."})
