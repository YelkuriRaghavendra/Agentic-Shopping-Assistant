# Chat Service

Production-grade e-commerce shopping assistant.
Clean architecture: controllers → services → repositories → clients.

## Quick Start

```bash
cp .env.example .env
# add OPENAI_API_KEY or Azure credentials
docker compose up -d
curl http://localhost:8000/health
```

## Architecture

```
app/
├── api/
│   ├── controllers/     HTTP boundary — validate input, call service, return response
│   ├── dto/             Pydantic request/response shapes
│   └── routes/v1/       URL → controller mappings (zero logic)
│
├── services/            Business logic — no HTTP, no SQL, no external APIs
│   ├── chat_service.py        Main orchestrator
│   ├── guardrails_service.py  Input + output safety
│   ├── memory_service.py      Session + customer memory
│   ├── rate_limiter_service.py  Per-customer rate limiting
│   ├── prompt_builder_service.py  Assembles LLM prompt
│   ├── citation_service.py    [P1] → real links
│   ├── tool_registry.py       All agent tools + handlers
│   └── style_advisor_service.py  Colour pairing + size advice
│
├── db/
│   ├── repositories/    All SQL lives here — services never touch SQLAlchemy
│   ├── models/          ORM table definitions
│   └── session.py       Engine + get_db dependency
│
├── clients/             External API wrappers
│   ├── base_client.py   Shared retry, timeout, error handling
│   ├── llm_client.py    OpenAI / Azure OpenAI (swap via USE_AZURE=true)
│   └── rag_client.py    RAG service HTTP calls
│
└── core/
    ├── config.py        All settings via environment variables
    ├── exceptions.py    Typed domain exceptions → HTTP status codes
    ├── logging.py       Structured logging (structlog)
    └── security.py      API key auth
```

## API Usage

All endpoints require:
```
X-API-Key: your-api-key
```

### Send a message (main endpoint)

```bash
# Guest user — no customer_id needed
curl -X POST http://localhost:8000/api/v1/chat \
  -H "X-API-Key: dev-secret-change-in-prod" \
  -H "Content-Type: application/json" \
  -d '{"message": "I want to buy running shoes"}'

# Returning customer — session auto-resolved
curl -X POST http://localhost:8000/api/v1/chat \
  -H "X-API-Key: dev-secret-change-in-prod" \
  -H "Content-Type: application/json" \
  -d '{
    "customer_id": "uuid-here",
    "message": "show me Nike shoes under $150"
  }'
```

Response:
```json
{
  "message_id": "uuid",
  "session_id": "uuid",
  "answer": "Here are some great running shoes...",
  "answer_html": "Here are some great <a href='/products/...' class='product-chip'>Nike Air Max ↗</a>...",
  "cited_products": [
    {"citation_id": "P1", "title": "Nike Air Max 270", "url": "/products/...", "price": 150.0, ...}
  ],
  "intent": "product_search",
  "guardrail_status": "passed",
  "blocked": false,
  "latency_ms": 820,
  "tokens_used": 1243
}
```

### Register a customer (for persistent memory)

```bash
curl -X POST http://localhost:8000/api/v1/chat/customers \
  -H "X-API-Key: dev-secret-change-in-prod" \
  -d '{"name": "Jane Smith", "email": "jane@example.com"}'
```

### Load message history (on page reload)

```bash
curl http://localhost:8000/api/v1/chat/sessions/{session_id}/messages \
  -H "X-API-Key: dev-secret-change-in-prod"
```

### Submit feedback

```bash
curl -X POST http://localhost:8000/api/v1/chat/messages/{message_id}/feedback \
  -H "X-API-Key: dev-secret-change-in-prod" \
  -d '{"rating": 1, "feedback_type": "helpful"}'
```

## Key Design Decisions

**Auto-session** — `POST /chat` finds the customer's active session or creates
one automatically. No separate "create session" call needed.

**LLM-led conversation** — The LLM decides when to ask clarifying questions
vs when to search. Slot extraction (regex) enriches RAG queries but doesn't
gate the conversation.

**OpenAI / Azure OpenAI** — Switch by setting `USE_AZURE=true` and filling
in Azure credentials. No code changes needed.

**Background tasks** — Profile updates and conversation summarisation run in
background tasks that each create their own DB session, never sharing the
request session.

## Switching to Azure OpenAI

```bash
USE_AZURE=true
AZURE_OPENAI_API_KEY=your-key
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com
AZURE_OPENAI_DEPLOYMENT_CHAT=gpt-4o        # your deployment name
AZURE_OPENAI_DEPLOYMENT_FALLBACK=gpt-4o-mini
```

## Running Tests

```bash
pip install -r requirements.txt
OPENAI_API_KEY=sk-test pytest tests/ -v
```
