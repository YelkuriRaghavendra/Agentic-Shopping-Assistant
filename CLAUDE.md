# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Agentic e-commerce shopping assistant with three services: a Next.js frontend, a FastAPI chat backend (the orchestrator), and a FastAPI RAG service (vector search + ingestion). The chat backend uses an agentic pattern where the LLM picks tools (RAG search, style advice, etc.) to answer user queries.

## Repository Structure

```
Frontend/       → Next.js 14 app (port 4001), React 18, TailwindCSS, TanStack Query
backend/        → FastAPI chat service (port 8000), Python 3.12
rag-service/    → FastAPI RAG service (port 8001), pgvector, OpenAI embeddings
```

## Development Commands

### Frontend (`Frontend/`)
```bash
npm run dev          # Dev server on port 4001
npm run build        # Production build
npm run lint         # ESLint
npx vitest run       # Run tests
npx vitest run __tests__/some-test.test.ts  # Single test
```

### Backend (`backend/`)
```bash
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000     # Dev server
OPENAI_API_KEY=sk-test pytest tests/ -v       # Run all tests
pytest tests/test_bugs.py -v                  # Single test file
pytest tests/ -v -m unit                      # Unit tests only
ruff check app/ tests/                        # Lint
black app/ tests/ && isort app/ tests/        # Format
alembic upgrade head                          # Run migrations
```

### RAG Service (`rag-service/`)
```bash
make install         # Install deps
make dev             # Dev server on port 8001
make test            # Tests with coverage (75% threshold)
make test-unit       # Unit tests only
make lint            # Ruff linter
make format          # Black + isort
make check           # All checks (format + lint + test)
make migrate         # Run DB migrations
docker compose up -d # Start with PostgreSQL + pgvector
```

## Architecture

### Chat Backend (the orchestrator)
Clean layered architecture: `controllers → services → repositories → clients`. No business logic in controllers, no SQL in services.

**Request lifecycle** in `ChatService` (the heart):
1. Rate limit → 2. Load session/memory → 3. Input guardrails → 4. Extract intent & slots (budget, size, color) → 5. LLM picks tool → 6. Execute tool (RAG search, etc.) → 7. Build final prompt → 8. Output guardrails + citations → 9. Persist + background tasks

**Key components:**
- `app/services/chat_service.py` — main orchestrator
- `app/services/tool_registry.py` — agent tools + handlers (extend here for new capabilities)
- `app/services/skills/` — skill system with registry, base class, and prompt templates
- `app/agent/` — agent definitions (markdown), commands, and skill loader
- `app/clients/llm_client.py` — OpenAI/Azure OpenAI (swap via `USE_AZURE=true`), auto-fallback to cheaper models
- `app/clients/rag_client.py` — calls RAG service at `/api/v1/retrieve`

### RAG Service
Ingest flow: content → dedup → chunk → embed (OpenAI) → store in pgvector (HNSW index)
Query flow: embed query → ANN search → metadata filter → LLM rerank → top-5 results

### Frontend
Next.js with TanStack Query for data fetching. Chat interface talks to backend via `services/chatService.ts` and `services/httpClient.ts`. HTML answers are sanitized with DOMPurify (`lib/sanitize.ts`).

## Code Style

- **Backend**: Black (line-length 100), isort (profile=black), Ruff linter, mypy strict-ish. See `pyproject.toml` for full config.
- **Frontend**: ESLint with Next.js config, TypeScript.
- Both services use `structlog` for structured logging.
- Pytest markers: `unit`, `integration`, `slow`. Asyncio mode is `auto`.
- API auth: all endpoints require `X-API-Key` header.

## Environment

Backend and RAG service each need a `.env` file (copy from `.env.example`). Key variable: `OPENAI_API_KEY`. For Azure: set `USE_AZURE=true` plus Azure credentials.
