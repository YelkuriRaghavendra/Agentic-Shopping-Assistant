# Vikrai - The Commerce AI

## Agentic Shopping Assistant - Technical Documentation

---

## 1. System Architecture

### 1.1 High-Level Overview

Vikrai is a 4-service agentic e-commerce platform where an AI assistant guides users from product discovery to checkout through natural conversation.

```mermaid
graph TB
    subgraph "Client"
        FE["Frontend<br/>Next.js :4001"]
    end

    subgraph "Backend Services"
        CB["Chat Backend<br/>FastAPI :8000<br/>(Orchestrator)"]
        COS["Checkout-Order Service<br/>NestJS :3001<br/>(Commerce)"]
        RAG["RAG Service<br/>FastAPI :8001<br/>(Search & Embeddings)"]
    end

    subgraph "External"
        LLM["GPT-4o<br/>Azure OpenAI<br/>(Vision)"]
        STRIPE["Stripe<br/>(Payments)"]
        UCP["UCP Merchants<br/>(Fulfillment)"]
    end

    subgraph "Data"
        PG1["PostgreSQL<br/>(Chat DB)"]
        PG2["PostgreSQL + pgvector<br/>(RAG DB)"]
        PG3["PostgreSQL<br/>(Orders DB)"]
        REDIS["Redis<br/>(Cache + Queues)"]
    end

    FE -- "SSE Stream" --> CB
    FE -- "REST" --> COS
    CB -- "Semantic Search" --> RAG
    CB -- "Tool Calls" --> LLM
    CB -- "Checkout/Orders" --> COS
    COS -- "Index Orders" --> RAG
    COS -- "Payments" --> STRIPE
    COS -- "Fulfillment" --> UCP
    STRIPE -- "Webhooks" --> COS
    UCP -- "Webhooks" --> COS
    CB --> PG1
    CB --> REDIS
    RAG --> PG2
    COS --> PG3
    COS --> REDIS
```

### 1.2 Tech Stack

| Service | Technology | Port |
|---------|-----------|------|
| Frontend | Next.js 14, React 18, TailwindCSS, TanStack Query | 4001 |
| Chat Backend | FastAPI, Python 3.12, SQLAlchemy async, Pydantic v2 | 8000 |
| RAG Service | FastAPI, pgvector, OpenAI Embeddings, Cross-Encoder | 8001 |
| Checkout-Order | NestJS 10, TypeORM, Stripe SDK, BullMQ, jose | 3001 |
| Database | PostgreSQL 15 + pgvector extension | 5432 |
| Cache/Queue | Redis 7 | 6379 |
| LLM | GPT-4o (Azure OpenAI) with Vision | - |
| Payments | Stripe (PaymentIntent + Payment Links) | - |

---

## 2. Chat Backend (Orchestrator)

### 2.1 Request Lifecycle

Every user message goes through a 12-step agentic pipeline:

```mermaid
flowchart TD
    A["User Message"] --> B["1. Rate Limit"]
    B --> C["2. Session Resolution"]
    C --> D["3. Load Memory Layers<br/>(Profile + History + Slots)"]
    D --> E["4. Input Guardrails<br/>(Injection + Harmful + Off-topic)"]
    E --> F["5. Intent Classification<br/>(Keyword-based, zero LLM cost)"]
    F --> G["6. Slot Extraction<br/>(Category, Brand, Budget, Size, Color)"]
    G --> H["7. Skill Activation<br/>(Stylist, Gift, Size, Empathy)"]
    H --> I["8. LLM Tool Decision<br/>(1st GPT-4o call)"]
    I --> J["9. Tool Execution<br/>(RAG search, compare, etc.)"]
    J --> K["10. LLM Response Generation<br/>(2nd GPT-4o call, streamed)"]
    K --> L["11. Output Guardrails<br/>+ Citation Processing"]
    L --> M["12. Persist + Stream SSE"]

    style I fill:#1D9E75,color:#fff
    style K fill:#1D9E75,color:#fff
```

### 2.2 Services

| Service | File | Purpose |
|---------|------|---------|
| **ChatService** | `chat_service.py` | Main orchestrator — coordinates all services for one message |
| **ToolRegistry** | `tool_registry.py` | 14 agent tools — dispatches LLM tool calls to handlers |
| **LLMClient** | `llm_client.py` | GPT-4o wrapper — tool calling, streaming, vision, auto-fallback |
| **RAGClient** | `rag_client.py` | Semantic search client — Redis-cached, graceful degradation |
| **MemoryService** | `memory_service.py` | 3-layer memory — session slots, customer profile, people context |
| **GuardrailsService** | `guardrails_service.py` | Input/output safety — injection, hallucination, off-topic |
| **PromptBuilderService** | `prompt_builder_service.py` | Assembles system prompt from all context layers |
| **CitationService** | `citation_service.py` | Converts [P1][P2] markers to product cards + HTML |
| **SkillRegistry** | `skill_registry.py` | 5 skills — context-based prompt customization |
| **StyleAdvisorService** | `style_advisor_service.py` | Color pairing + size guidance (pure logic) |

### 2.3 Agentic Tool System

```mermaid
graph LR
    subgraph "LLM decides tool"
        LLM["GPT-4o"]
    end

    subgraph "Product Discovery"
        T1["search_products"]
        T2["outfit_pairing"]
        T3["gift_finder"]
        T4["compare_products"]
        T5["stock_check"]
    end

    subgraph "Customer Support"
        T6["order_lookup"]
        T7["return_request"]
        T8["policy_faq"]
        T9["size_advice"]
        T10["order_history"]
    end

    subgraph "Conversation"
        T11["clarify_question"]
        T12["direct_answer"]
        T13["escalate_to_human"]
    end

    LLM --> T1 & T2 & T3 & T4 & T5
    LLM --> T6 & T7 & T8 & T9 & T10
    LLM --> T11 & T12 & T13

    T1 & T2 & T3 & T4 & T5 --> RAG["RAG Service"]
```

### 2.4 Memory Architecture

```mermaid
graph TB
    subgraph "Layer 1: Turn History"
        L1["Last 6 turns<br/>Token-budget aware (800 tokens)<br/>Minimum 2 turns kept"]
    end

    subgraph "Layer 2: Session Context (JSONB)"
        L2A["Slots: category, brand, budget, size, color"]
        L2B["Shown products (max 20)"]
        L2C["Session summary"]
    end

    subgraph "Layer 3: Customer Profile (JSONB)"
        L3A["Preferred brands (top 3)"]
        L3B["Usual sizes (category → size)"]
        L3C["Price sensitivity"]
        L3D["Known people (cross-session)<br/>Name, relation, interests"]
    end

    L1 --> PROMPT["System Prompt"]
    L2A & L2B & L2C --> PROMPT
    L3A & L3B & L3C & L3D --> PROMPT
```

### 2.5 Skill System

| Skill | Trigger | Effect |
|-------|---------|--------|
| ReturningCustomer | Has profile data | Skip known questions, personalize |
| Stylist | "outfit", "match", "style" | Fashion vocabulary, colour theory |
| GiftAdvisor | "gift", "birthday", "for my dad" | Recipient-focused recommendations |
| SizeExpert | "size", "fit", "wide feet" | Brand-specific sizing quirks |
| Empathy | "terrible", "broken", "manager" | Empathetic tone, proactive escalation |

### 2.6 API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/v1/chat/stream` | Send message (SSE streaming) |
| POST | `/api/v1/chat` | Send message (sync) |
| POST | `/api/v1/chat/sessions` | Create session |
| GET | `/api/v1/chat/sessions/:id` | Get session |
| POST | `/api/v1/chat/sessions/:id/end` | End session |
| GET | `/api/v1/chat/sessions/:id/messages` | Message history |
| POST | `/api/v1/chat/customers` | Create customer |
| GET | `/api/v1/chat/customers/:id` | Get customer |
| PATCH | `/api/v1/chat/customers/:id/profile` | Update profile |
| GET | `/api/v1/chat/customers/:id/sessions` | List sessions |

---

## 3. RAG Service (Search & Embeddings)

### 3.1 Ingestion Pipeline

```mermaid
flowchart LR
    A["Product Data"] --> B["Dedup<br/>(SHA-256)"]
    B --> C["Chunk<br/>(Token-aware<br/>512 tokens)"]
    C --> D["Embed<br/>(OpenAI 3-large<br/>1536 dims)"]
    D --> E["Store<br/>(pgvector<br/>HNSW index)"]
```

### 3.2 Retrieval Pipeline (3-Way Hybrid)

```mermaid
flowchart TD
    A["User Query"] --> B["Dense: Embed Query<br/>(OpenAI text-embedding-3-large)"]
    A --> C["Sparse: BM25<br/>(PostgreSQL ts_vector + ts_rank)"]

    B --> D["pgvector ANN Search<br/>(Cosine distance, HNSW)"]
    C --> E["Full-Text Search<br/>(ts_rank with length norm)"]

    D --> F["Metadata Filters<br/>(brand, price, color)"]
    E --> F

    F --> G["RRF Merge<br/>(Reciprocal Rank Fusion, k=60)"]
    G --> H["Cross-Encoder Rerank<br/>(ms-marco-MiniLM)"]
    H --> I["Top-5 Results"]
```

**3-way hybrid approach:**
1. **Dense retrieval** — OpenAI embeddings (1536d) with pgvector HNSW cosine search
2. **Sparse retrieval (BM25)** — PostgreSQL `ts_vector` + `ts_rank` with document length normalization
3. **Reranking** — Cross-encoder (ms-marco-MiniLM) scores each (query, passage) pair

Results from dense and sparse are merged using **Reciprocal Rank Fusion (RRF)** before reranking. Falls back to ILIKE if `ts_vector` is unavailable.

### 3.3 Services

| Service | Purpose |
|---------|---------|
| **IngestionService** | Document dedup, chunking, embedding, storage pipeline |
| **RetrievalService** | Query embedding, vector search, filtering, reranking |
| **ChunkingService** | Token-aware text splitting with overlap |
| **OrderIngestionService** | Customer-scoped order indexing for search |

### 3.4 API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/v1/retrieve` | Semantic search with filters |
| POST | `/api/v1/ingest/product` | Ingest single product |
| POST | `/api/v1/ingest/products/bulk` | Bulk ingest (1-500) |
| GET | `/api/v1/ingest/jobs/:id` | Job status |
| POST | `/api/v1/orders/index` | Index order for search |
| POST | `/api/v1/sources` | Create knowledge source |

### 3.5 Database Schema

```mermaid
erDiagram
    sources ||--o{ documents : contains
    documents ||--o{ chunks : split_into
    chunks ||--o{ embeddings : embedded_as
    llm_models ||--o{ embeddings : model_used

    sources {
        uuid source_id PK
        varchar source_name
        enum source_type
        jsonb source_config
    }

    documents {
        uuid document_id PK
        uuid source_id FK
        text product_id
        enum document_type
        text content
        varchar content_hash
        enum status
        jsonb metadata
    }

    chunks {
        uuid chunk_id PK
        uuid document_id FK
        int chunk_index
        text content
        int token_count
        jsonb metadata
    }

    embeddings {
        uuid embedding_id PK
        uuid chunk_id FK
        uuid llm_model_id FK
        vector embedding
    }
```

---

## 4. Checkout-Order Service (Commerce)

### 4.1 Checkout Flow

```mermaid
sequenceDiagram
    participant FE as Frontend
    participant CB as Chat Backend
    participant COS as Checkout Service
    participant S as Stripe
    participant RAG as RAG Service

    FE->>CB: "I want to buy this shoe"
    CB->>COS: POST /checkout/sessions
    COS-->>CB: { session_id, totals }
    CB-->>FE: Checkout data in SSE

    FE->>COS: POST /sessions/:id/payment-link
    COS->>S: Create Payment Link
    S-->>COS: { url }
    COS-->>FE: { payment_url }

    FE->>S: Redirect to Stripe
    S-->>COS: Webhook: payment_intent.succeeded
    COS->>COS: Complete session
    COS->>COS: Enqueue order.confirmed
    COS->>COS: Create Order
    COS->>RAG: POST /orders/index
    FE->>COS: Poll session status
    COS-->>FE: { status: COMPLETED }
```

### 4.2 Services

| Service | Purpose |
|---------|---------|
| **CheckoutSessionService** | Create/update/complete checkout sessions, Stripe integration |
| **OrderService** | Order lifecycle — create, cancel, return with audit trail |
| **RagIndexingService** | Fire-and-forget order indexing to RAG service |
| **AuditService** | Append-only audit log for all order mutations |
| **MerchantProfileService** | UCP merchant discovery and caching |
| **RequestSigningService** | JWT signing for outbound merchant requests |
| **IdempotencyService** | Redis-backed request deduplication |
| **CircuitBreakerService** | Per-endpoint circuit breaker for merchant calls |

### 4.3 API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/commerce/checkout/sessions` | Create checkout session |
| GET | `/commerce/checkout/sessions/:id` | Get session |
| POST | `/commerce/checkout/sessions/:id/payment-link` | Create Stripe Payment Link |
| POST | `/commerce/checkout/sessions/:id/complete` | Complete checkout |
| GET | `/commerce/orders` | List orders (cursor-paginated) |
| GET | `/commerce/orders/:id` | Get order detail + history |
| POST | `/commerce/orders/:id/cancel` | Cancel order |
| POST | `/commerce/orders/:id/return` | Request return |
| POST | `/stripe/webhooks` | Stripe webhook handler |
| POST | `/commerce/webhooks/ucp/orders` | Merchant webhook handler |

### 4.4 Order State Machine

```mermaid
stateDiagram-v2
    [*] --> PROCESSING: order.confirmed
    PROCESSING --> FULFILLED: merchant webhook
    PROCESSING --> CANCELLED: customer cancels
    FULFILLED --> RETURN_REQUESTED: customer returns
    CANCELLED --> [*]
    RETURN_REQUESTED --> [*]
```

---

## 5. Frontend

### 5.1 Component Architecture

```mermaid
graph TB
    subgraph "Pages"
        LP["Landing Page<br/>(app/page.tsx)"]
        CP["Chat Page<br/>(app/chat/page.tsx)"]
    end

    subgraph "Chat Layout"
        SS["SessionSidebar"]
        CW["ChatWindow"]
        UD["UserDialog"]
    end

    subgraph "Chat Components"
        CI["ChatInput<br/>(text + image upload)"]
        MB["MessageBubble"]
        PS["ProductSlider"]
        SC["SuggestionChips"]
        TI["TypingIndicator"]
        CM["CheckoutModal"]
        OC["OrderConfirmationCard"]
    end

    subgraph "Hooks"
        UC["useChat"]
        UCU["useCustomer"]
        US["useSessions"]
    end

    CP --> SS & CW & UD
    CW --> CI & MB & TI & CM
    MB --> PS & SC & OC
    CP --> UC & UCU & US
```

### 5.2 Key Features

| Feature | Description |
|---------|-------------|
| **Photo Upload** | Camera icon, resize to 800px, GPT-4o vision analysis for outfit matching |
| **Streaming Chat** | Real-time SSE token streaming with typing indicator |
| **Product Cards** | Horizontal carousel with images, prices, ratings, multi-select compare |
| **Suggestion Chips** | Contextual quick-replies (brands, budgets, colors) |
| **Session Management** | Sidebar with session history, titles, status tracking |
| **Welcome Screen** | Onboarding with quick-start chips |
| **Checkout Flow** | Address selection, Stripe payment, order confirmation |
| **Markdown Rendering** | Bot messages rendered with markdown (bold, lists, tables) |
| **Price Filtering** | Products with zero/missing prices hidden |
| **Color Filtering** | Post-filter RAG results by requested color |

---

## 6. End-to-End User Journey

```mermaid
sequenceDiagram
    participant U as User
    participant FE as Frontend
    participant CB as Chat Backend
    participant LLM as GPT-4o
    participant RAG as RAG Service

    U->>FE: "I want casual sneakers"
    FE->>CB: POST /chat/stream
    CB->>LLM: decide_tool(slots: type only)
    LLM-->>CB: clarify_question("Any preferences?")
    CB-->>FE: SSE: "Any preferences — brand, budget, or color?"
    FE-->>U: Shows chips: [Nike] [Under ₹2000] [Black]

    U->>FE: Clicks "Black"
    FE->>CB: POST /chat/stream
    CB->>LLM: decide_tool(slots: type + color = READY)
    LLM-->>CB: search_products(query="black casual sneakers")
    CB->>RAG: POST /retrieve
    RAG-->>CB: 5 products (post-filtered by "black")
    CB->>LLM: generate_stream(products context)
    LLM-->>CB: JSON {answer, suggestions}
    CB-->>FE: SSE tokens + product cards
    FE-->>U: Shows black sneakers with prices
```

---

## 7. Database Schemas

### 7.1 Chat Backend Database

```mermaid
erDiagram
    customers ||--o{ sessions : has
    sessions ||--o{ messages : contains
    sessions ||--o| session_feedback : has

    customers {
        uuid customer_id PK
        varchar email
        varchar name
        jsonb profile
        varchar status
    }

    sessions {
        uuid session_id PK
        uuid customer_id FK
        varchar channel
        varchar status
        jsonb context
        int message_count
        timestamp started_at
    }

    messages {
        uuid message_id PK
        uuid session_id FK
        varchar role
        text content
        varchar intent
        jsonb cited_products
        varchar llm_model
    }

    session_feedback {
        uuid feedback_id PK
        uuid session_id FK
        int rating
        text comment
    }
```

### 7.2 Checkout-Order Database

```mermaid
erDiagram
    checkout_sessions ||--o| orders : creates
    orders ||--o{ order_status_history : tracks
    orders ||--o{ audit_log : audits

    checkout_sessions {
        uuid session_id PK
        varchar customer_id
        enum ucp_status
        jsonb line_items_snapshot
        jsonb totals_snapshot
        varchar stripe_payment_intent_id
    }

    orders {
        uuid order_id PK
        varchar customer_id
        uuid checkout_id FK
        enum status
        jsonb line_items
        jsonb totals
        jsonb adjustments
    }

    order_status_history {
        uuid history_id PK
        uuid order_id FK
        enum from_status
        enum to_status
        varchar source
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

## 8. Security

| Layer | Mechanism |
|-------|-----------|
| API Authentication | X-API-Key header on all endpoints |
| Input Safety | Prompt injection detection, harmful content blocking |
| Output Safety | Citation hallucination check, off-brand language detection |
| Data Privacy | Customer-scoped order retrieval (Requirement 12.2, 12.4) |
| Payment Security | Stripe webhook signature verification |
| Merchant Comms | JWT-signed requests (ES256/RS256), webhook verification |
| XSS Prevention | DOMPurify HTML sanitization on frontend |
| Idempotency | Redis-backed request deduplication (24h TTL) |
| Circuit Breaking | Per-endpoint circuit breaker for merchant calls |

---

## 9. Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| **Agentic pattern** (LLM picks tools) | More flexible than hardcoded routing; handles ambiguous queries |
| **2-call LLM loop** (decide + generate) | Separates tool selection from response writing for better control |
| **Conversational slot gathering** | Better product discovery than immediate search with no context |
| **Base64 image transport** | Simplest — no CDN/upload infrastructure needed |
| **SSE streaming** | Real-time typing effect; better UX than waiting for full response |
| **pgvector + HNSW** | Fast ANN search with metadata filtering in single query |
| **Cross-encoder reranking** | Improves relevance over pure vector similarity |
| **BullMQ for order events** | Decouples checkout completion from order creation; retry on failure |
| **Append-only audit log** | Compliance-ready order history; transactional with order mutations |
| **Redis caching** | 5-min TTL for RAG results and customer profiles; reduces latency |
