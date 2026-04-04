"""
Agent state — the single source of truth flowing through the graph.

Every node reads from and writes to this TypedDict. LangGraph
automatically merges partial updates returned by each node.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any, TypedDict

from app.api.dto.chat_dto import ChatRequest, ChatResponse, ProductCardDTO
from app.clients.llm_client import ToolCall, LLMResult, SuggestionItem
from app.db.models.enums.message_enums import GuardrailStatus
from app.services.memory_service import SlotState, ConversationHistory, PersonNote
from app.services.tool_registry import ToolResult


class AgentState(TypedDict, total=False):
    """
    Shared state for the shopping agent graph.

    Each node reads what it needs and returns a partial dict
    with the keys it wants to update. LangGraph merges updates.
    """

    # ── Input (set once at graph entry) ──────────────────────────────
    request: ChatRequest
    t_start: float

    # ── Context (set by load_context node) ───────────────────────────
    session: Any  # Session ORM object
    session_id: str
    customer_id: str | None
    customer_profile: dict
    conversation: ConversationHistory
    slots: SlotState
    shown_products: list[dict]
    people: list[PersonNote]

    # ── Intent & Guardrails (set by guardrails + extract nodes) ──────
    input_blocked: bool
    block_reason: str
    block_response: str
    intent: str
    guard_status: str  # "PASSED" | "WARNED" | "BLOCKED"

    # ── Skills (set by activate_skills node) ─────────────────────────
    skill_prompt_addon: str
    skill_extra_tools: list[dict]
    active_skills: list[str]

    # ── LLM Tool Decision (set by decide_tool node) ──────────────────
    llm_history: list[dict]
    tool_call: ToolCall | None
    tool_name: str
    tool_args: dict

    # ── Commerce routing ─────────────────────────────────────────────
    commerce_intent: str | None
    commerce_response: ChatResponse | None

    # ── Tool Execution (set by execute_tool node) ────────────────────
    tool_result: ToolResult | None

    # ── Response Generation (set by generate_response node) ──────────
    system_prompt: str
    citation_map: dict[str, dict]
    llm_result: LLMResult | None
    raw_response: str

    # ── Output Processing (set by process_output node) ───────────────
    answer: str
    answer_html: str
    cited_products: list[ProductCardDTO]
    suggestions: list[dict]
    final_guard_status: str

    # ── Final Response (set by persist node) ─────────────────────────
    response: ChatResponse | None
    error: str | None

    # ── Streaming events (for SSE) ───────────────────────────────────
    stream_events: list[dict]
