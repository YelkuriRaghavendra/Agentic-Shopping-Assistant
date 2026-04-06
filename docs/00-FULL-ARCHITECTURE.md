# Vikrai — Full System Architecture

## The Commerce AI | 4-Service Agentic Shopping Platform

---

## System Overview

Vikrai is an agentic e-commerce platform where an AI assistant guides users from product discovery to checkout through natural conversation, photo-based outfit matching, and intelligent product comparison.

```mermaid
graph TB
    subgraph "Client Layer"
        FE["Frontend<br/>Next.js 14 :4001<br/>React 18 + TailwindCSS"]
    end

    subgraph "Application Layer"
        CB["Chat Backend<br/>FastAPI :8000<br/>Python 3.12<br/><b>THE ORCHESTRATOR</b>"]
        COS["Checkout-Order Service<br/>NestJS 10 :3001<br/>TypeScript"]
        RAG["RAG Service<br/>FastAPI :8001<br/>Python 3.12"]
    end

    subgraph "AI Layer"
        LLM["GPT-4o<br/>Azure OpenAI<br/>Tool Calling + Vision"]
        EMB["text-embedding-3-large<br/>1536 dimensions"]
        CE["Cross-Encoder<br/>ms-marco-MiniLM"]
    end

    subgraph "External Services"
        STRIPE["Stripe<br/>Payments"]
        UCP["UCP Merchants<br/>Fulfillment"]
    end

    subgraph "Data Layer"
        PG1["PostgreSQL<br/>Chat DB<br/>customers · sessions · messages"]
        PG2["PostgreSQL + pgvector<br/>RAG DB<br/>documents · chunks · embeddings"]
        PG3["PostgreSQL<br/>Orders DB<br/>checkout_sessions · orders · audit_log"]
        REDIS["Redis 7<br/>Cache + BullMQ Queues"]
    end

    FE -- "SSE Stream" --> CB
    FE -- "REST / Stripe Redirect" --> COS
    CB -- "3-Way Hybrid Search" --> RAG
    CB -- "2x LLM Calls / Message" --> LLM
    CB -- "Checkout + Orders API" --> COS
    COS -- "Index Orders" --> RAG
    COS -- "Payments" --> STRIPE
    COS -- "Signed Requests" --> UCP
    STRIPE -- "Webhooks" --> COS
    UCP -- "Webhooks" --> COS
    RAG -- "Embed" --> EMB
    RAG -- "Rerank" --> CE
    CB --> PG1 & REDIS
    RAG --> PG2
    COS --> PG3 & REDIS
```

---

## How A Message Flows Through The System

```mermaid
sequenceDiagram
    participant U as User
    participant FE as Frontend :4001
    participant CB as Chat Backend :8000
    participant LLM as GPT-4o
    participant RAG as RAG Service :8001
    participant PG as pgvector DB

    U->>FE: "I want black Nike running shoes under 3000"
    FE->>CB: POST /chat/stream (SSE)

    Note over CB: 1. Rate limit check
    Note over CB: 2. Session resolution
    Note over CB: 3. Load memory (profile + history + slots)
    Note over CB: 4. Input guardrails (injection, harmful)
    Note over CB: 5. Intent: product_search
    Note over CB: 6. Slots: type=running, brand=Nike, color=black, budget=3000
    Note over CB: 7. Skill: ReturningCustomer (has profile)

    CB->>LLM: 8. decide_tool(slots=READY)
    LLM-->>CB: search_products(query, brand=Nike, color=black, max_price=3000)

    CB->>RAG: 9. POST /retrieve (enriched query + filters)

    Note over RAG: Dense: embed → pgvector ANN (cosine)
    Note over RAG: Sparse: ts_vector → ts_rank (BM25)
    Note over RAG: RRF merge (k=60)
    Note over RAG: Cross-encoder rerank

    RAG-->>CB: Top-5 products

    CB->>LLM: 10. generate_stream(products context)
    LLM-->>CB: JSON {answer, suggestions} (streamed)

    Note over CB: 11. Citation processing [P1][P2] → product cards
    Note over CB: 12. Persist messages + update session

    CB-->>FE: SSE tokens + product cards + suggestion chips
    FE-->>U: Shows products with images, prices, ratings
```

---

## The Four Services

### 1. Chat Backend (The Orchestrator)
**Port 8000 | FastAPI | Python 3.12**

The brain. Receives messages, runs a 12-step agentic pipeline, coordinates all other services.

```mermaid
graph LR
    subgraph "12-Step Pipeline"
        A["Rate Limit"] --> B["Session"]
        B --> C["Memory<br/>(3 layers)"]
        C --> D["Guardrails"]
        D --> E["Intent"]
        E --> F["Slots"]
        F --> G["Skills<br/>(5 types)"]
        G --> H["LLM Tool<br/>Decision"]
        H --> I["Tool<br/>Execution"]
        I --> J["LLM Response<br/>(streamed)"]
        J --> K["Citations"]
        K --> L["Persist"]
    end
```

**Key capabilities:**
- 14 agent tools (search, compare, outfit matching, size advice, order lookup, etc.)
- 3-layer memory (turn history, session context, customer profile)
- 5 skills (stylist, gift advisor, size expert, empathy, returning customer)
- Photo upload with GPT-4o vision analysis
- Conversational slot gathering (max 2 questions before search)
- Input/output guardrails (injection, hallucination, off-topic)

---

### 2. RAG Service (Search & Embeddings)
**Port 8001 | FastAPI | Python 3.12**

3-way hybrid retrieval combining dense, sparse, and neural reranking.

```mermaid
graph TD
    Q["Query"] --> D["Dense<br/>pgvector ANN<br/>(semantic meaning)"]
    Q --> S["Sparse<br/>ts_vector/ts_rank<br/>(exact keywords, BM25)"]
    D --> RRF["RRF Merge<br/>(k=60)"]
    S --> RRF
    RRF --> R["Cross-Encoder<br/>Rerank"]
    R --> TOP["Top-5<br/>Results"]
```

**Key capabilities:**
- Dense retrieval: OpenAI embeddings (1536d) + pgvector HNSW
- Sparse retrieval: PostgreSQL ts_vector + ts_rank (BM25-like)
- Reciprocal Rank Fusion for merging
- Cross-encoder reranking (ms-marco-MiniLM)
- Metadata filtering (brand, price, color, customer scope)
- Token-aware chunking with overlap
- SHA-256 deduplication

---

### 3. Checkout-Order Service (Commerce Engine)
**Port 3001 | NestJS 10 | TypeScript**

Full commerce lifecycle with Stripe payments and UCP merchant integration.

```mermaid
graph LR
    subgraph "Checkout"
        CS["Create Session"] --> PAY["Stripe Payment"]
        PAY --> COMP["Complete"]
    end

    subgraph "Orders"
        COMP --> ORD["Create Order"]
        ORD --> AUDIT["Audit Log"]
        ORD --> IDX["RAG Index"]
    end

    subgraph "Lifecycle"
        ORD --> CANCEL["Cancel"]
        ORD --> FULFILL["Fulfill"]
        FULFILL --> RETURN["Return"]
    end
```

**Key capabilities:**
- Stripe PaymentIntent + Payment Links
- UCP merchant integration (signed requests, webhook verification)
- BullMQ async order processing
- Append-only audit trail (transactional with order mutations)
- Order indexing to RAG for search context
- Circuit breaker + retry + idempotency for merchant calls

---

### 4. Frontend (Chat Interface)
**Port 4001 | Next.js 14 | React 18**

Real-time chat UI with photo upload, product cards, and multi-step checkout.

```mermaid
graph TD
    WELCOME["Welcome Screen<br/>Quick-start chips"] --> CHAT["Chat Conversation<br/>Streaming SSE"]
    CHAT --> PHOTO["Photo Upload<br/>WebP compression<br/>Server upload"]
    CHAT --> PRODUCTS["Product Cards<br/>Image + Price + Rating"]
    PRODUCTS --> COMPARE["Compare Products<br/>Side-by-side table"]
    PRODUCTS --> BUY["Checkout Modal<br/>Address + Stripe"]
    BUY --> ORDER["Order Confirmation"]
```

**Key capabilities:**
- Photo upload with WebP compression + server-side validation
- SSE streaming with real-time typing indicator
- Markdown rendering (bold, lists, tables)
- Product card carousel with multi-select compare
- Contextual suggestion chips
- Session management with titles
- Error boundary for crash recovery

---

## Memory Architecture

```mermaid
graph TB
    subgraph "Layer 1: Turn History (per-request)"
        L1["Last 6 turns<br/>Token-budget: 800 tokens<br/>Minimum 2 turns kept"]
    end

    subgraph "Layer 2: Session Context (JSONB)"
        L2["Slots: category, brand, budget, size, color<br/>Shown products (max 20)<br/>Session summary"]
    end

    subgraph "Layer 3: Customer Profile (JSONB, Redis cached)"
        L3["Preferred brands (top 3)<br/>Usual sizes (category → size)<br/>Price sensitivity (budget/mid/premium)<br/>Known people: name, relation, interests<br/>Products seen (last 20)"]
    end

    L1 & L2 & L3 --> PROMPT["Assembled System Prompt<br/>→ GPT-4o"]

    NEW_SESSION["New Session Start"] -.->|"Pre-fill slots<br/>from profile"| L2
```

---

## Photo Upload Pipeline

```mermaid
flowchart LR
    A["User selects photo"] --> B["Frontend: resize 1024px<br/>WebP compression (0.75)"]
    B --> C["POST /upload-image<br/>(multipart)"]
    C --> D["Backend validates:<br/>Magic bytes (JPEG/PNG/WebP)<br/>Max 5MB<br/>Save to /tmp/vikrai-uploads/"]
    D --> E["Returns image URL"]
    E --> F["URL sent in chat request"]
    F --> G["GPT-4o Vision<br/>detail: auto<br/>Analyzes outfit colors/style"]
    G --> H["Asks preferences<br/>(brand/budget/color)"]
    H --> I["outfit_pairing tool<br/>RAG search for matching shoes"]
```

---

## Conversational Flow

```mermaid
flowchart TD
    START["User starts conversation"] --> TYPE{"Has shoe type?"}
    TYPE -->|No| ASK_TYPE["Bot: 'What kind — running, casual, formal?'<br/>Chips: [Running] [Casual] [Formal]"]
    ASK_TYPE --> TYPE

    TYPE -->|Yes| PREF{"Has brand/budget/color?"}
    PREF -->|No| ASK_PREF["Bot: 'Any preferences — brand, budget, or color?'<br/>Chips: [Nike] [Under ₹2000] [Black] [Open to anything]"]
    ASK_PREF --> PREF

    PREF -->|Yes| SEARCH["RAG Search<br/>(3-way hybrid)"]
    SEARCH --> PRODUCTS["Show product cards<br/>Chips: [Compare] [Under ₹1000] [Waterproof?]"]

    PRODUCTS --> COMPARE["Compare 2 products<br/>HTML table"]
    PRODUCTS --> BUY["Checkout flow<br/>Stripe payment"]
    PRODUCTS --> REFINE["Refine search<br/>(different color/budget)"]

    PHOTO["User uploads photo"] --> ANALYZE["GPT-4o Vision<br/>Describes outfit"]
    ANALYZE --> ASK_PREF
```

---

## Database Schemas

### Chat Backend

```mermaid
erDiagram
    customers ||--o{ sessions : has
    sessions ||--o{ messages : contains
    sessions ||--o| session_feedback : has

    customers {
        uuid customer_id PK
        varchar email
        varchar name
        jsonb profile "brands, sizes, people"
        varchar status
    }
    sessions {
        uuid session_id PK
        uuid customer_id FK
        varchar channel
        varchar status "active|ended"
        jsonb context "slots, shown_products"
        int message_count
    }
    messages {
        uuid message_id PK
        uuid session_id FK
        varchar role "user|assistant"
        text content
        varchar intent
        jsonb cited_products
        varchar llm_model
        int latency_ms
    }
```

### RAG Service

```mermaid
erDiagram
    sources ||--o{ documents : contains
    documents ||--o{ chunks : split_into
    chunks ||--o{ embeddings : embedded_as

    documents {
        uuid document_id PK
        text product_id
        enum document_type "PRODUCT|ORDER|FAQ|POLICY"
        text content
        varchar content_hash "SHA-256"
        enum status "PENDING|READY|FAILED"
        jsonb metadata "brand, price, color"
    }
    chunks {
        uuid chunk_id PK
        uuid document_id FK
        text content
        int token_count
    }
    embeddings {
        uuid embedding_id PK
        uuid chunk_id FK
        vector_1536 embedding "pgvector HNSW"
    }
```

### Checkout-Order Service

```mermaid
erDiagram
    checkout_sessions ||--o| orders : creates
    orders ||--o{ order_status_history : tracks
    orders ||--o{ audit_log : audits

    checkout_sessions {
        uuid session_id PK
        varchar customer_id
        enum ucp_status
        jsonb totals_snapshot
        varchar stripe_payment_intent_id
    }
    orders {
        uuid order_id PK
        uuid checkout_id FK
        enum status "PROCESSING|FULFILLED|CANCELLED"
        jsonb line_items
        jsonb adjustments "append-only"
    }
    audit_log {
        uuid audit_id PK
        uuid order_id FK
        varchar action_type
        jsonb before_state
        jsonb after_state
    }
```

---

## API Surface

### Chat Backend (:8000) — 12 endpoints
| Method | Path | Purpose |
|--------|------|---------|
| POST | `/api/v1/chat/stream` | Send message (SSE) |
| POST | `/api/v1/chat` | Send message (sync) |
| POST | `/api/v1/chat/upload-image` | Upload image |
| GET | `/api/v1/chat/uploads/:file` | Serve image |
| POST | `/api/v1/chat/sessions` | Create session |
| POST | `/api/v1/chat/sessions/:id/end` | End session |
| GET | `/api/v1/chat/sessions/:id/messages` | Message history |
| POST | `/api/v1/chat/customers` | Create customer |
| GET | `/api/v1/chat/customers/:id` | Get customer |
| PATCH | `/api/v1/chat/customers/:id/profile` | Update profile |
| GET | `/api/v1/chat/customers/:id/sessions` | List sessions |

### RAG Service (:8001) — 7 endpoints
| Method | Path | Purpose |
|--------|------|---------|
| POST | `/api/v1/retrieve` | 3-way hybrid search |
| POST | `/api/v1/ingest/product` | Ingest product |
| POST | `/api/v1/ingest/products/bulk` | Bulk ingest |
| GET | `/api/v1/ingest/jobs/:id` | Job status |
| POST | `/api/v1/orders/index` | Index order |
| POST | `/api/v1/sources` | Create source |

### Checkout-Order (:3001) — 14 endpoints
| Method | Path | Purpose |
|--------|------|---------|
| POST | `/commerce/checkout/sessions` | Create checkout |
| POST | `/commerce/checkout/sessions/:id/payment-link` | Stripe link |
| POST | `/commerce/checkout/sessions/:id/complete` | Complete |
| GET | `/commerce/orders` | List orders |
| GET | `/commerce/orders/:id` | Order detail |
| POST | `/commerce/orders/:id/cancel` | Cancel |
| POST | `/commerce/orders/:id/return` | Return |
| POST | `/stripe/webhooks` | Stripe hooks |
| POST | `/commerce/webhooks/ucp/orders` | Merchant hooks |

---

## Security Layers

```mermaid
graph LR
    subgraph "Input"
        A1["API Key Auth<br/>(X-API-Key)"]
        A2["Input Guardrails<br/>(Injection, Harmful)"]
        A3["File Validation<br/>(Magic bytes, 5MB)"]
    end

    subgraph "Processing"
        B1["Customer Scoping<br/>(Order privacy)"]
        B2["Stripe Webhook Sig<br/>(Payment verification)"]
        B3["JWT Request Signing<br/>(Merchant comms)"]
    end

    subgraph "Output"
        C1["Output Guardrails<br/>(Hallucination check)"]
        C2["DOMPurify<br/>(XSS prevention)"]
        C3["Audit Trail<br/>(Append-only)"]
    end
```

---

## Tech Stack Summary

| Layer | Technology |
|-------|-----------|
| Frontend | Next.js 14, React 18, TailwindCSS, TanStack Query, Framer Motion |
| Chat Backend | FastAPI, Python 3.12, SQLAlchemy async, Pydantic v2 |
| RAG Service | FastAPI, pgvector, OpenAI Embeddings, Cross-Encoder, ts_vector |
| Commerce | NestJS 10, TypeORM, Stripe SDK, BullMQ, jose (JWT) |
| LLM | GPT-4o (Azure OpenAI) — tool calling + vision |
| Embeddings | text-embedding-3-large (1536 dimensions) |
| Reranker | ms-marco-MiniLM-L-12-v2 (cross-encoder) |
| Database | PostgreSQL 15 + pgvector (HNSW) |
| Cache/Queue | Redis 7 (cache TTL + BullMQ) |
| Streaming | Server-Sent Events (SSE) |
| Payments | Stripe (PaymentIntent + Payment Links) |
| Merchants | UCP (Universal Commerce Protocol) |

---

## Key Design Decisions

| Decision | Why |
|----------|-----|
| 4 microservices | Chat (CPU-bound), RAG (memory-bound), Checkout (I/O-bound) scale independently |
| Agentic pattern | LLM picks tools — more flexible than hardcoded routing for ambiguous queries |
| 2-call LLM loop | Separates tool selection from response generation for better control |
| 3-way hybrid retrieval | Dense handles synonyms, sparse handles exact terms, reranker boosts precision |
| RRF over learned fusion | No training data needed, works out-of-box, provably effective |
| Conversational slots | 2 questions max — better UX than forms, worse than zero-shot but more accurate |
| Base64 → server upload | Reduces JSON payload from 1.3MB to 50 bytes, enables validation/moderation |
| BullMQ for orders | Decouples checkout from order creation — retry on failure, no lost orders |
| Append-only audit | Compliance-ready, transactional with mutations — can't accidentally lose history |
| Cross-session memory | "My friend who runs" persists across sessions — differentiating feature |
