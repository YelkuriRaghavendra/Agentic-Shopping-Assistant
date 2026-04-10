"""
Graph state schema for the multi-agent shopping assistant.

All agents read and write to this shared state.
The checkpointer persists it after every node execution.
"""

from typing import Annotated, TypedDict

from langchain_core.messages import AnyMessage
from langgraph.graph.message import add_messages


class AgentState(TypedDict):
    # Conversation (managed by checkpointer via add_messages reducer)
    messages: Annotated[list[AnyMessage], add_messages]

    # Routing
    current_agent: str | None
    intent: str | None

    # Shopping context
    slots: dict
    shown_products: list[dict]

    # Customer context
    customer_id: str | None
    customer_profile: dict

    # Checkout context
    checkout_session_id: str | None
    checkout_state: dict

    # Agent working memory (current turn)
    agent_response: str | None
    retrieved_chunks: list[dict]
    tool_results: list[dict]

    # Post-processing outputs
    cited_products: list[dict]
    suggestions: list[dict]
    guardrail_status: str

    # SSE streaming metadata
    stream_events: list[dict]
