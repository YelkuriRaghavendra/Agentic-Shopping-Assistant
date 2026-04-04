"""
Agent state — the single source of truth flowing through the graph.

Every node reads from and writes to this TypedDict. LangGraph
automatically merges partial updates returned by each node.

Grouped by pipeline phase for clarity.
"""

from __future__ import annotations

from typing import Any, TypedDict

from app.api.dto.chat_dto import ChatRequest, ChatResponse, ProductCardDTO
from app.clients.llm_client import ToolCall, LLMResult
from app.services.memory_service import SlotState, ConversationHistory, PersonNote
from app.services.tool_registry import ToolResult


class AgentState(TypedDict, total=False):
    """Shared state for the shopping agent graph."""

    # ── Input (set at graph entry) ───────────────────────────────────
    request: ChatRequest
    t_start: float

    # ── Context (load_context node) ──────────────────────────────────
    session: Any
    session_id: str
    customer_id: str | None
    customer_profile: dict
    conversation: ConversationHistory
    slots: SlotState
    shown_products: list[dict]
    people: list[PersonNote]

    # ── Guardrails (check_guardrails node) ───────────────────────────
    input_blocked: bool
    block_response: str

    # ── Intent (extract_intent node) ─────────────────────────────────
    intent: str
    commerce_intent: str | None

    # ── Skills (activate_skills node) ────────────────────────────────
    skill_prompt_addon: str
    skill_extra_tools: list[dict]
    active_skills: list[str]

    # ── Tool Decision (decide_tool node) ─────────────────────────────
    llm_history: list[dict]
    tool_call: ToolCall | None
    tool_name: str
    tool_args: dict

    # ── Tool Execution (execute_tool node) ───────────────────────────
    tool_result: ToolResult | None

    # ── Response (generate_response node) ────────────────────────────
    system_prompt: str
    citation_map: dict[str, dict]
    llm_result: LLMResult | None

    # ── Output (process_output node) ─────────────────────────────────
    answer: str
    answer_html: str
    cited_products: list[ProductCardDTO]
    suggestions: list[dict]
    guard_status: str

    # ── Final (persist node) ─────────────────────────────────────────
    response: ChatResponse | None
    error: str | None

    # ── Streaming (SSE events emitted by nodes) ──────────────────────
    node_status: str
