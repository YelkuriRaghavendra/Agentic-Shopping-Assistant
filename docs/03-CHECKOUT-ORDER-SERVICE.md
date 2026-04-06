# Checkout-Order Service — Commerce Engine

**Service:** NestJS 10 (TypeScript) | **Port:** 3001 | **Role:** Payments, orders, merchant integration

---

## What It Does

Handles the full commerce lifecycle: checkout session management, Stripe payment processing, order creation, status tracking, cancellation/returns, merchant webhook handling via UCP (Universal Commerce Protocol), and order indexing into the RAG service.

## Architecture

```mermaid
graph TD
    FE["Frontend :4001"] -->|"Create Checkout"| API["NestJS Router"]
    CB["Chat Backend :8000"] -->|"Checkout/Orders API"| API
    STRIPE["Stripe"] -->|"Webhooks"| WH_S["StripeWebhookController"]
    MERCHANT["UCP Merchants"] -->|"Order Webhooks"| WH_M["WebhookController"]

    API --> CHECKOUT["CheckoutSessionService"]
    API --> ORDERS["OrderService"]
    WH_S --> CHECKOUT
    WH_M --> ORDERS

    CHECKOUT -->|"Payment"| STRIPE_SDK["Stripe SDK"]
    CHECKOUT -->|"order.confirmed"| QUEUE["BullMQ<br/>Redis Queues"]
    QUEUE --> CONSUMER["OrderEventsConsumer"]
    CONSUMER --> ORDERS

    ORDERS --> AUDIT["AuditService<br/>Append-Only Log"]
    ORDERS --> RAG_IDX["RagIndexingService"]
    RAG_IDX -->|"POST /orders/index"| RAG["RAG Service :8001"]

    CHECKOUT --> UCP["UcpCheckoutClient"]
    UCP --> SIGN["RequestSigningService<br/>JWT (ES256)"]
    UCP --> IDEM["IdempotencyService<br/>Redis 24h TTL"]
    UCP --> CB_SVC["CircuitBreakerService"]
    UCP --> RETRY["RetryService<br/>Exponential Backoff"]

    ORDERS --> DB["PostgreSQL<br/>checkout · orders schemas"]
    CHECKOUT --> DB
```

## Checkout Flow

```mermaid
sequenceDiagram
    participant FE as Frontend
    participant COS as Checkout Service
    participant S as Stripe
    participant Q as BullMQ
    participant OS as OrderService
    participant RAG as RAG Service

    FE->>COS: POST /checkout/sessions
    COS-->>FE: { session_id, totals }

    FE->>COS: POST /sessions/:id/payment-link
    COS->>S: Create Payment Link
    S-->>COS: { url }
    COS-->>FE: { payment_url }

    FE->>S: User pays on Stripe

    S->>COS: Webhook: payment_intent.succeeded
    COS->>COS: Mark session COMPLETED
    COS->>Q: Enqueue order.confirmed

    Q->>OS: Process order.confirmed
    OS->>OS: Create Order + Audit Log
    OS->>RAG: POST /orders/index (async)
```

## Order State Machine

```mermaid
stateDiagram-v2
    [*] --> PROCESSING: order.confirmed event
    PROCESSING --> FULFILLED: Merchant webhook (shipped/delivered)
    PROCESSING --> CANCELLED: Customer cancels via API
    FULFILLED --> RETURN_REQUESTED: Customer requests return
    CANCELLED --> [*]
    RETURN_REQUESTED --> [*]

    note right of PROCESSING: Only PROCESSING orders can be cancelled
    note right of FULFILLED: Only FULFILLED orders can be returned
```

## Service Reference

### CheckoutSessionService

| Method | Description |
|--------|-------------|
| `createSession()` | Create local session, optionally sync with UCP merchant |
| `updateSession()` | Update line items, buyer info, context |
| `completeSession()` | Mark COMPLETED, enqueue order.confirmed event |
| `cancelSession()` | Mark CANCELED |
| `createOrGetPaymentIntent()` | Create Stripe PaymentIntent (cached per session) |
| `createPaymentLink()` | Create one-time Stripe Payment Link |
| `handlePaymentSucceeded()` | Stripe webhook → complete session |
| `handlePaymentFailed()` | Stripe webhook → mark PAYMENT_FAILED |

### OrderService

| Method | Description |
|--------|-------------|
| `createFromConfirmedEvent()` | Create order from checkout + audit log (transactional) |
| `cancelOrder()` | PROCESSING → CANCELLED + adjustment + audit (transactional) |
| `returnOrder()` | FULFILLED → RETURN_REQUESTED + adjustment + audit (transactional) |

### AuditService
Append-only audit log. Failure rolls back the entire order transaction.

| Action Types | Trigger |
|-------------|---------|
| `order_created` | Order creation |
| `status_changed` | Any status transition |
| `cancelled` | Customer cancellation |
| `return_initiated` | Return request |
| `adjustment_applied` | Refund/credit adjustment |

### UCP Client (Merchant Integration)

| Service | Purpose |
|---------|---------|
| `UcpCheckoutClient` | 5 REST operations (create/get/update/complete/cancel) |
| `MerchantProfileService` | Discover merchant via `/.well-known/ucp` (Redis cached 1h) |
| `RequestSigningService` | JWT signing (ES256/RS256) for outbound requests |
| `WebhookVerificationService` | Verify inbound merchant webhook signatures |
| `IdempotencyService` | Redis-backed dedup (24h TTL) |
| `CircuitBreakerService` | Per-endpoint circuit breaker (Redis) |
| `RetryService` | Exponential backoff with jitter (3 attempts) |

## Database Schema

```mermaid
erDiagram
    checkout_sessions ||--o| orders : creates
    orders ||--o{ order_status_history : tracks
    orders ||--o{ audit_log : audits

    checkout_sessions {
        uuid session_id PK
        varchar customer_id
        varchar merchant_id
        enum ucp_status "INCOMPLETE|READY|COMPLETED|FAILED|CANCELED"
        jsonb line_items_snapshot
        jsonb totals_snapshot "subtotal_cents, tax_cents, grand_total_cents"
        varchar stripe_payment_intent_id
        varchar stripe_client_secret
        varchar ucp_order_id
    }
    orders {
        uuid order_id PK
        varchar customer_id
        uuid checkout_id FK
        enum status "PROCESSING|FULFILLED|CANCELLED|RETURN_REQUESTED"
        jsonb line_items
        jsonb totals
        jsonb adjustments "Append-only"
        jsonb fulfillment "Events array"
    }
    order_status_history {
        uuid history_id PK
        uuid order_id FK
        enum from_status
        enum to_status
        varchar source "api|webhook|system"
        varchar actor
    }
    audit_log {
        uuid audit_id PK
        uuid order_id FK
        varchar action_type
        jsonb before_state
        jsonb after_state
        varchar source
        varchar ip_address
    }
```

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/commerce/checkout/sessions` | Create checkout session |
| GET | `/commerce/checkout/sessions/:id` | Get session |
| PUT | `/commerce/checkout/sessions/:id` | Update session |
| POST | `/commerce/checkout/sessions/:id/complete` | Complete checkout |
| POST | `/commerce/checkout/sessions/:id/cancel` | Cancel session |
| POST | `/commerce/checkout/sessions/:id/payment-intent` | Create Stripe PaymentIntent |
| POST | `/commerce/checkout/sessions/:id/payment-link` | Create Stripe Payment Link |
| GET | `/commerce/checkout/sessions/:id/summary` | Get totals |
| GET | `/commerce/orders` | List orders (cursor-paginated) |
| GET | `/commerce/orders/:id` | Order detail + history |
| POST | `/commerce/orders/:id/cancel` | Cancel order |
| POST | `/commerce/orders/:id/return` | Request return |
| POST | `/stripe/webhooks` | Stripe webhook handler |
| POST | `/commerce/webhooks/ucp/orders` | Merchant webhook handler |
| GET | `/.well-known/ucp` | Platform profile discovery |

## Message Queues (BullMQ)

| Queue | Job | Producer | Consumer |
|-------|-----|----------|----------|
| `order-events` | `order.confirmed` | CheckoutSessionService | OrderEventsConsumer |
| `webhook-ingestion` | `ucp.order.event` | WebhookController | WebhookIngestionConsumer |

## Tech Stack

| Component | Technology |
|-----------|-----------|
| Framework | NestJS 10 (TypeScript) |
| ORM | TypeORM |
| Payments | Stripe SDK v21 |
| Queues | BullMQ (Redis) |
| Signing | jose (JWT ES256/RS256) |
| Database | PostgreSQL (checkout + orders schemas) |
| Cache | Redis 7 |

## Security

| Mechanism | Purpose |
|-----------|---------|
| Stripe webhook signature | Verify payment events are from Stripe |
| JWT request signing | Sign outbound merchant requests (ES256) |
| Webhook verification | Verify inbound merchant webhooks |
| Idempotency keys | Prevent duplicate order creation (Redis 24h) |
| Circuit breaker | Prevent cascading merchant failures |
| Audit trail | Append-only, transactional with order mutations |
