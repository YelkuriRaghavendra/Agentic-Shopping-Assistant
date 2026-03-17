"""
Domain exceptions.

Each exception maps to a specific HTTP status code.
Controllers catch these and return the correct HTTP response.
Services raise these — they never import FastAPI or HTTP status codes.

Hierarchy:
  ChatServiceError        (base)
    ├── NotFoundError
    │     ├── CustomerNotFoundError
    │     ├── SessionNotFoundError
    │     └── MessageNotFoundError
    ├── ValidationError
    │     ├── SessionExpiredError
    │     └── SessionInactiveError
    ├── RateLimitError
    │     └── CustomerRateLimitError
    ├── GuardrailError
    │     ├── PromptInjectionError
    │     ├── HarmfulContentError
    │     └── OffTopicError
    ├── UpstreamError
    │     ├── LLMError
    │     └── RAGServiceError
    └── TokenBudgetExceededError
"""


class ChatServiceError(Exception):
    """Base class for all domain errors."""
    http_status: int = 500
    default_message: str = "An unexpected error occurred."

    def __init__(self, message: str | None = None):
        self.message = message or self.default_message
        super().__init__(self.message)


# ─────────────────────────────────────────────────────────────────────────────
# 404 Not Found
# ─────────────────────────────────────────────────────────────────────────────

class NotFoundError(ChatServiceError):
    http_status = 404
    default_message = "Resource not found."


class CustomerNotFoundError(NotFoundError):
    default_message = "Customer not found."


class SessionNotFoundError(NotFoundError):
    default_message = "Session not found."


class MessageNotFoundError(NotFoundError):
    default_message = "Message not found."


# ─────────────────────────────────────────────────────────────────────────────
# 400 / 422 Validation
# ─────────────────────────────────────────────────────────────────────────────

class DomainValidationError(ChatServiceError):
    http_status = 400
    default_message = "Invalid request."


class SessionExpiredError(DomainValidationError):
    http_status = 400
    default_message = "Session has expired. Please start a new conversation."


class SessionInactiveError(DomainValidationError):
    http_status = 400
    default_message = "Session is no longer active."


class CustomerBlockedError(DomainValidationError):
    http_status = 403
    default_message = "This account has been blocked."


# ─────────────────────────────────────────────────────────────────────────────
# 429 Rate Limit
# ─────────────────────────────────────────────────────────────────────────────

class RateLimitError(ChatServiceError):
    http_status = 429
    default_message = "Too many requests. Please wait a moment."


class CustomerRateLimitError(RateLimitError):
    default_message = "You're sending messages too quickly. Please slow down."


# ─────────────────────────────────────────────────────────────────────────────
# Guardrail violations — return 200 with blocked=True (not HTTP error)
# These are handled by the chat service, not raised to controller
# ─────────────────────────────────────────────────────────────────────────────

class GuardrailError(ChatServiceError):
    http_status = 200
    safe_response: str = "I'm here to help with shopping. How can I assist?"

    def __init__(self, message: str | None = None, safe_response: str | None = None):
        super().__init__(message)
        if safe_response:
            self.safe_response = safe_response


class PromptInjectionError(GuardrailError):
    safe_response = "I'm here to help you with shopping and orders. What can I find for you?"


class HarmfulContentError(GuardrailError):
    safe_response = "I can only help with shopping-related questions. Please contact our support team if you need further assistance."


class OffTopicError(GuardrailError):
    safe_response = "I'm your shopping assistant. I can help with products, orders, returns, and more."


# ─────────────────────────────────────────────────────────────────────────────
# Upstream failures
# ─────────────────────────────────────────────────────────────────────────────

class UpstreamError(ChatServiceError):
    http_status = 503
    default_message = "An external service is temporarily unavailable."


class LLMError(UpstreamError):
    default_message = "The AI service is temporarily unavailable. Please try again."


class RAGServiceError(UpstreamError):
    default_message = "Product search is temporarily unavailable."


# ─────────────────────────────────────────────────────────────────────────────
# Token budget
# ─────────────────────────────────────────────────────────────────────────────

class TokenBudgetExceededError(ChatServiceError):
    http_status = 429
    default_message = (
        "This conversation has reached its length limit. "
        "Please start a new chat to continue."
    )
