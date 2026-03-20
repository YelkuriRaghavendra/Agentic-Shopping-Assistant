# RAG Service

End-to-end Retrieval-Augmented Generation service for the e-commerce chatbot.
Handles ingestion, chunking, embedding, and retrieval backed by PostgreSQL + pgvector.

## Architecture

```
Ingest flow:
  raw content → deduplication check → chunk → embed (OpenAI) → store in pgvector

Query flow:
  user query → embed → ANN search (HNSW) → metadata filter → LLM rerank → top-5
```

## Quick Start

### 1. Copy env file
```bash
cp .env.example .env
# edit .env — add your OPENAI_API_KEY
```

### 2. Start everything
```bash
docker compose up -d
```

This starts:
- `ragdb` — PostgreSQL 16 with pgvector on port 5432
- `rag-service` — FastAPI on port 8001 (runs migrations on startup)

### 3. Check it's running
```bash
curl http://localhost:8001/health
```

---

## API Reference

All endpoints (except `/health`) require the header:
```
X-API-Key: your-api-key
```

### Step 1 — Create a knowledge source

Every document belongs to a source. Create one first:

```bash
curl -X POST http://localhost:8001/api/v1/sources \
  -H "X-API-Key: dev-secret-change-in-prod" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "My Product Catalog",
    "source_type": "manual",
    "config": {}
  }'
```

Save the `id` from the response — you need it for all ingestion calls.

---

### Step 2 — Add knowledge

#### Option A: Ingest a product
```bash
curl -X POST http://localhost:8001/api/v1/ingest/product \
  -H "X-API-Key: dev-secret-change-in-prod" \
  -H "Content-Type: application/json" \
  -d '{
    "source_id": "YOUR_SOURCE_ID",
    "title": "Nike Air Max 270",
    "description": "Lightweight running shoe with large Air unit heel cushioning.",
    "sku": "NK-AM270-BLK-10",
    "url": "/products/nike-air-max-270",
    "price": 150.00,
    "currency": "USD",
    "image_url": "/images/nike-am270.jpg",
    "brand": "Nike",
    "category": "running",
    "in_stock": true,
    "rating": 4.7,
    "reviews": 1243
  }'
```

#### Option B: Ingest raw text (FAQ, policy)
```bash
curl -X POST http://localhost:8001/api/v1/ingest/text \
  -H "X-API-Key: dev-secret-change-in-prod" \
  -H "Content-Type: application/json" \
  -d '{
    "source_id": "YOUR_SOURCE_ID",
    "title": "Return Policy",
    "doc_type": "policy",
    "content": "We accept returns within 30 days of purchase. Items must be unused and in original packaging. To start a return, visit our returns portal or contact support@store.com.",
    "metadata": {"policy_type": "returns", "version": "2024-01"}
  }'
```

#### Option C: Upload a file (PDF, CSV, TXT, DOCX)
```bash
curl -X POST http://localhost:8001/api/v1/ingest/file \
  -H "X-API-Key: dev-secret-change-in-prod" \
  -F "source_id=YOUR_SOURCE_ID" \
  -F "file=@/path/to/products.csv"
```

Your CSV should have columns like: `title, sku, price, brand, category, description, url, image_url, in_stock`

#### Option D: Bulk ingest (up to 500 items)
```bash
curl -X POST http://localhost:8001/api/v1/ingest/bulk \
  -H "X-API-Key: dev-secret-change-in-prod" \
  -H "Content-Type: application/json" \
  -d '{
    "source_id": "YOUR_SOURCE_ID",
    "items": [
      {
        "source_id": "YOUR_SOURCE_ID",
        "title": "Product 1",
        "description": "...",
        "sku": "P001",
        "url": "/products/p1",
        "price": 99.0
      }
    ]
  }'
```

---

### Step 3 — Poll job status

Ingestion is async. Poll until `status` is `done` or `failed`:

```bash
curl http://localhost:8001/api/v1/ingest/jobs/JOB_ID \
  -H "X-API-Key: dev-secret-change-in-prod"
```

Response:
```json
{
  "id": "...",
  "document_id": "...",
  "status": "done",
  "chunks_total": 3,
  "chunks_done": 3,
  "progress_pct": 100.0,
  "started_at": "...",
  "finished_at": "..."
}
```

---

### Step 4 — Retrieve (search)

```bash
curl -X POST http://localhost:8001/api/v1/retrieve \
  -H "X-API-Key: dev-secret-change-in-prod" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "lightweight running shoes under 150 dollars",
    "top_k": 5,
    "rerank": true,
    "filters": {
      "doc_type": "product",
      "brand": "Nike",
      "max_price": 150,
      "in_stock": true
    }
  }'
```

Response:
```json
{
  "query": "lightweight running shoes under 150 dollars",
  "results": [
    {
      "chunk_id": "...",
      "document_id": "...",
      "chunk_index": 0,
      "content": "Nike Air Max 270...",
      "similarity": 0.921,
      "doc_type": "product",
      "title": "Nike Air Max 270",
      "metadata": {
        "sku": "NK-AM270-BLK-10",
        "url": "/products/nike-air-max-270",
        "price": 150.0,
        "currency": "USD",
        "image_url": "/images/nike-am270.jpg",
        "brand": "Nike",
        "category": "running",
        "in_stock": true,
        "rating": 4.7
      }
    }
  ],
  "total_found": 5,
  "reranked": true,
  "latency_ms": 312
}
```

The `metadata` field on every result contains everything the chat service
needs to build product cards with real links — url, image, price, sku.

---

### Document management

```bash
# List all documents
GET /api/v1/documents?source_id=...&doc_type=product&status=ready

# Get one document
GET /api/v1/documents/{doc_id}

# Update title or metadata
PATCH /api/v1/documents/{doc_id}
  {"metadata": {"in_stock": false}}

# Delete one document (removes chunks + embeddings)
DELETE /api/v1/documents/{doc_id}

# Delete entire source (bulk delete everything)
DELETE /api/v1/sources/{source_id}
```

---

## Running Tests

```bash
pip install -r requirements.txt
pytest tests/ -v
```

---

## Project Structure

```
rag-service/
├── app/
│   ├── main.py                  ← FastAPI app, middleware, routers
│   ├── api/routes/
│   │   ├── ingest.py            ← POST /ingest/text|product|file|bulk
│   │   ├── retrieve.py          ← POST /retrieve, CRUD /documents /sources
│   │   └── health.py            ← GET /health
│   ├── services/
│   │   ├── chunking.py          ← semantic + fixed-size chunking
│   │   ├── embedding.py         ← OpenAI batched embedding with retries
│   │   ├── file_parser.py       ← PDF, CSV, TXT, DOCX parsing
│   │   ├── ingestion.py         ← full pipeline orchestrator
│   │   └── retrieval.py         ← vector search + LLM reranking
│   ├── models/models.py         ← SQLAlchemy ORM models
│   ├── schemas/schemas.py       ← Pydantic request/response schemas
│   ├── db/session.py            ← async engine + session factory
│   └── core/
│       ├── config.py            ← all settings via pydantic-settings
│       ├── logging.py           ← structured logging (structlog)
│       └── security.py          ← API key auth
├── alembic/
│   ├── env.py
│   └── versions/001_initial.py  ← creates all tables + HNSW index
├── tests/test_rag.py
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
└── .env.example
```

---

## What the Chat Service Needs to Do

The chat service calls this RAG service at query time:

```python
# 1. POST /api/v1/retrieve with the user's query
# 2. Use returned results to build prompt with [P1], [P2] citations
# 3. Send to LLM
# 4. Post-process: replace [P1] → real URL from results[0].metadata.url
# 5. Return structured response with answer + product cards
```

See the chat service for the full integration code.
