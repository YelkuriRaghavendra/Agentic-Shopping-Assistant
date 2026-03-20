"""
Domain exceptions for the RAG service.
Each exception maps to an HTTP status code.
Controllers catch these and return the correct response.
"""


class RAGServiceError(Exception):
    http_status: int = 500
    default_message: str = "An unexpected error occurred."

    def __init__(self, message: str | None = None):
        self.message = message or self.default_message
        super().__init__(self.message)


class NotFoundError(RAGServiceError):
    http_status = 404
    default_message = "Resource not found."


class SourceNotFoundError(NotFoundError):
    default_message = "Knowledge source not found."


class DocumentNotFoundError(NotFoundError):
    default_message = "Document not found."


class JobNotFoundError(NotFoundError):
    default_message = "Ingestion job not found."


class DuplicateDocumentError(RAGServiceError):
    http_status = 409
    default_message = "Document already indexed."


class ValidationError(RAGServiceError):
    http_status = 422
    default_message = "Invalid request."


class EmbeddingError(RAGServiceError):
    http_status = 503
    default_message = "Embedding service temporarily unavailable."


class PageIndexError(RAGServiceError):
    http_status = 503
    default_message = "PageIndex service temporarily unavailable."
