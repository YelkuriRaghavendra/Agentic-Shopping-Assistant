"""
Chat routes v1.

This file only registers URL patterns → controller method mappings.
Zero business logic here.
"""

from fastapi import APIRouter, Depends, UploadFile, File
from app.api.controllers.chat_controller import chat_controller
from app.api.dto.chat_dto import (
    ChatResponse,
    CustomerResponse,
    SessionResponse, MessageHistoryResponse,
    FeedbackResponse,
)
from app.core.security import verify_api_key

router = APIRouter(
    prefix="/chat",
    tags=["Chat"],
    # dependencies=[Depends(verify_api_key)],
)

# ── Main chat endpoint ────────────────────────────────────────────────────────
router.post(
    "",
    response_model=ChatResponse,
    summary="Send a message",
    description=(
        "Send a customer message and receive a bot response. "
        "Session is auto-created if not provided. "
        "Pass customer_id to enable memory across sessions."
    ),
)(chat_controller.send_message)

# ── LangGraph-powered chat endpoint ──────────────────────────────────────────
router.post(
    "/graph",
    summary="Send a message (LangGraph agent)",
    description=(
        "LangGraph-powered agentic endpoint with state checkpointing. "
        "Same functionality as /chat but uses a declarative state graph."
    ),
)(chat_controller.send_message_graph)

# ── Streaming chat endpoint ──────────────────────────────────────────────────
router.post(
    "/stream",
    summary="Send a message (streaming)",
    description=(
        "Streaming version of the chat endpoint. "
        "Returns Server-Sent Events with tokens as they arrive."
    ),
)(chat_controller.send_message_stream)

# ── Session management ────────────────────────────────────────────────────────
router.post(
    "/sessions",
    response_model=SessionResponse,
    summary="Create a session",
    description="Explicitly create a session. Most clients don't need this — POST /chat auto-creates sessions.",
)(chat_controller.create_session)

router.get(
    "/sessions/{session_id}",
    response_model=SessionResponse,
    summary="Get a session",
)(chat_controller.get_session)

router.post(
    "/sessions/{session_id}/end",
    response_model=SessionResponse,
    summary="End a session",
)(chat_controller.end_session)

router.get(
    "/sessions/{session_id}/messages",
    response_model=MessageHistoryResponse,
    summary="Get message history",
    description="Cursor-paginated. Pass next_cursor as before_id for the next page.",
)(chat_controller.get_history)

# ── Customer management ───────────────────────────────────────────────────────
router.post(
    "/customers",
    response_model=CustomerResponse,
    summary="Create a customer",
    description="Register a customer to enable persistent memory across sessions.",
)(chat_controller.create_customer)

router.get(
    "/customers/{customer_id}",
    response_model=CustomerResponse,
    summary="Get a customer",
)(chat_controller.get_customer)

router.patch(
    "/customers/{customer_id}/profile",
    response_model=CustomerResponse,
    summary="Update customer profile",
    description="Merge new data into the customer profile JSONB. Used to save addresses, preferences, etc.",
)(chat_controller.update_customer_profile)

router.get(
    "/customers/{customer_id}/sessions",
    response_model=list[SessionResponse],
    summary="List customer sessions",
    description="Returns all sessions for a customer, ordered newest first.",
)(chat_controller.get_customer_sessions)

# ── Image upload ─────────────────────────────────────────────────────────────
router.post(
    "/upload-image",
    summary="Upload an image",
    description=(
        "Upload an image file (jpeg, png, webp) for use in chat. "
        "Returns a URL that can be used as image_base64 in chat requests."
    ),
)(chat_controller.upload_image)

router.get(
    "/uploads/{filename}",
    summary="Serve uploaded image",
    description="Serve a previously uploaded image by filename.",
)(chat_controller.serve_upload)

# ── Feedback ──────────────────────────────────────────────────────────────────
router.post(
    "/sessions/{session_id}/feedback",
    response_model=FeedbackResponse,
    summary="Submit session feedback",
    description="Thumbs up (1) or thumbs down (-1) on a completed session.",
)(chat_controller.add_feedback)
