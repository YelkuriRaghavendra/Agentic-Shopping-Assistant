# Implementation Plan: Checkout & Order Service

## Overview

Implement a single NestJS application at `checkout-order-service/` (at the project root, alongside `backend/`, `Frontend/`, and `rag-service/`) containing three feature modules: `CheckoutModule`, `OrderModule`, and `UcpClientModule`. All modules run in one process, share the same database connection, Redis client, and BullMQ instance, and communicate via NestJS dependency injection — no inter-process HTTP between them.

Our service is a **UCP platform** that calls merchant-operated UCP endpoints (per the [Universal Commerce Protocol](https://ucp.dev)) and receives merchant order webhooks. The merchant owns checkout status; we store it locally and react to it.

Tasks are ordered by dependency: app scaffold → UcpClientModule → CheckoutModule → OrderModule → Python/RAG integration → frontend.

## Tasks

- [x] 1. Scaffold `checkout-order-service/` NestJS application
  - [x] 1.1 Create the NestJS app and install dependencies
    - Run `nest new checkout-order-service` at the project root
    - Install: `@nestjs/typeorm`, `typeorm`, `pg`, `ioredis`, `@nestjs/bull`, `bullmq`, `class-validator`, `class-transformer`, `@nestjs/config`, `@nestjs/terminus`, `jose` (for detached JWT signing/verification per RFC 7797)
    - Install dev: `jest`, `fast-check`, `@nestjs/testing`, `nock`, `ts-jest`
    - Configure `tsconfig.json`, ESLint, Prettier
    - _Requirements: 13.1, 13.2, 13.3_

  - [x] 1.2 Configure TypeORM with `checkout` and `orders` schemas
    - Set up `TypeOrmModule.forRootAsync()` in `AppModule` pointing to the shared PostgreSQL DB
    - Add `synchronize: false` — migrations only
    - _Requirements: 13.1, 13.2, 13.4_

  - [x] 1.3 Configure Redis and BullMQ
    - Set up `ioredis` client as a shared provider in `AppModule`
    - Register BullMQ queues: `order-events`, `webhook-ingestion`
    - _Requirements: 2.7, 9.7_

  - [x] 1.4 Create TypeORM migrations for `checkout` schema
    - `001_create_checkout_schema.ts` — `CREATE SCHEMA checkout`
    - `002_checkout_sessions.ts` — `checkout.checkout_sessions` table with all columns: `ucp_checkout_id`, `ucp_status`, `continue_url`, `expires_at`, `line_items_snapshot JSONB`, `buyer_snapshot JSONB`, `context_snapshot JSONB`, `payment_handlers JSONB`, `totals_snapshot JSONB`, `ucp_order_id`, `ucp_order_permalink`; indexes; FK to `public.customers`
    - Include `down` migrations
    - _Requirements: 13.1, 13.3, 13.4, 13.5_

  - [x] 1.5 Create TypeORM migrations for `orders` schema
    - `001_create_orders_schema.ts` — `CREATE SCHEMA orders`
    - `002_orders.ts` — `orders.orders` table with `ucp_order_id`, `checkout_id`, `permalink_url`, `line_items JSONB`, `fulfillment JSONB`, `adjustments JSONB`, `totals JSONB`
    - `003_order_status_history.ts`
    - `004_audit_log.ts`
    - `005_webhook_events.ts` — include `merchant_id` and `signature_verified` columns
    - Include `down` migrations
    - _Requirements: 13.2, 13.3, 13.4, 13.5_

  - [ ]* 1.6 Write migration smoke tests
    - Run `up` then `down` against a Dockerised PostgreSQL instance
    - Assert schema state after `up` and clean state after `down`
    - _Requirements: 13.3, 13.4_

  - [x] 1.7 Define shared types in `checkout-order-service/src/shared/`
    - `types/ucp-checkout-status.enum.ts` — `UcpCheckoutStatus`: `incomplete | requires_escalation | ready_for_complete | complete_in_progress | completed | canceled`
    - `types/ucp-order-status.enum.ts` — `UcpOrderStatus`: `processing | partial | fulfilled | cancelled | return_requested | returned | payment_failed`
    - `types/ucp-types.interface.ts` — `UcpLineItem`, `UcpBuyer`, `UcpContext`, `UcpTotals`, `UcpFulfillmentEvent`, `UcpAdjustment`
    - `types/event-envelope.interface.ts` — `EventEnvelope`
    - `errors/commerce.exception.ts` — base exception with error code + message
    - _Requirements: 2.1, 5.1, 9.1_

  - [x] 1.8 Add `GET /commerce/health` endpoint
    - Use `@nestjs/terminus` to check PostgreSQL, Redis, and merchant UCP reachability
    - Return service name, version, and dependency status
    - _Requirements: 14.1, 14.2_

- [-] 2. UcpClientModule
  - [x] 2.1 Implement `MerchantProfileService`
    - Fetch merchant's `/.well-known/ucp` document; extract `checkout_base_url`, `payment_handlers`, and `signing_keys` (JWK set)
    - Cache in Redis at `merchant:profile:{merchant_id}` with TTL 5 minutes
    - Expose `getProfile(merchantId)`, `getCheckoutBaseUrl(merchantId)`, `getPaymentHandlers(merchantId)`, `getSigningKeys(merchantId)`
    - Return `merchant_profile_unavailable` (503) when `/.well-known/ucp` is unreachable
    - _Requirements: 15.1, 15.5_

  - [x] 2.2 Implement `RequestSigningService`
    - Sign outbound request bodies with our platform's private key using a detached JWT (RFC 7797) via `jose`
    - Load platform key pair from environment / secret store at startup
    - Expose `signRequest(body: Buffer): string` — returns the `Request-Signature` header value
    - _Requirements: 15.1 (UCP REST Binding compliance)_

  - [ ]* 2.3 Write property test for request signing (Property 29)
    - **Property 29: Request signing on all outbound calls**
    - **Validates: Requirements 15.1**

  - [x] 2.4 Implement `WebhookVerificationService`
    - Verify inbound merchant webhook `Request-Signature` detached JWT using merchant's public key from `MerchantProfileService`
    - Algorithm: parse JWT `kid` → fetch merchant JWK set → find matching key → verify detached JWT against raw body
    - Expose `verifyWebhook(merchantId: string, signature: string, rawBody: Buffer): Promise<boolean>`
    - _Requirements: 9.2, 9.3_

  - [ ]* 2.5 Write property test for webhook JWT validation (Property 25)
    - **Property 25: Webhook JWT signature validation**
    - **Validates: Requirements 9.2, 9.3**

  - [x] 2.6 Implement `IdempotencyService`
    - Store idempotency key → cached response in Redis with 24-hour TTL
    - On duplicate key within window, return cached response without forwarding to merchant
    - Return `idempotency_conflict` (409) when same key is reused with a different payload
    - _Requirements: 15.1, 15.2_

  - [ ]* 2.7 Write property test for idempotency guard deduplication (Property 30)
    - **Property 30: Idempotency guard deduplication**
    - **Validates: Requirements 15.1, 15.2**

  - [x] 2.8 Implement `RetryService` and `CircuitBreakerService`
    - Exponential backoff with jitter, max 3 retries on transient merchant errors (429, 5xx, timeouts)
    - Circuit breaker opens after 3 consecutive failures; half-open probe after 60 seconds
    - Persist circuit state in Redis at `circuit:{merchant_id}:{endpoint}`
    - Return `ucp_unavailable` (503) when circuit is open
    - _Requirements: 15.3, 15.4_

  - [ ]* 2.9 Write property test for retry with exponential backoff (Property 31)
    - **Property 31: Retry with exponential backoff**
    - **Validates: Requirements 15.3, 15.4**

  - [ ] 2.10 Implement `UcpCheckoutClient`
    - Methods: `createCheckoutSession()`, `getCheckoutSession()`, `updateCheckoutSession()`, `completeCheckoutSession()`, `cancelCheckoutSession()`
    - Each method builds required UCP REST Binding headers: `UCP-Agent: profile="..."`, `Idempotency-Key` (mutating ops), `Request-Signature` (via `RequestSigningService`), `Request-Id`
    - Wires `MerchantProfileService`, `IdempotencyService`, `RetryService`, `CircuitBreakerService`
    - _Requirements: 15.5_

- [ ] 3. Checkpoint — UcpClientModule
  - Ensure all UcpClientModule tests pass. Ask the user if questions arise.

- [ ] 4. CheckoutModule — session management
  - [ ] 4.1 Define `CheckoutSession` TypeORM entity
    - `CheckoutSession` entity with `{ schema: 'checkout', name: 'checkout_sessions' }`
    - Fields: `ucpCheckoutId`, `ucpStatus: UcpCheckoutStatus`, `continueUrl`, `expiresAt`, `lineItemsSnapshot`, `buyerSnapshot`, `contextSnapshot`, `paymentHandlers`, `totalsSnapshot`, `ucpOrderId`, `ucpOrderPermalink`
    - _Requirements: 13.1_

  - [ ] 4.2 Implement `CheckoutSessionService`
    - `createSession(merchantId, customerId, lineItems, buyer?, context?)` — call `UcpCheckoutClient.createCheckoutSession()`, store local record, return session with `ucp_status`
    - `updateSession(sessionId, lineItems, buyer?, context?)` — call `UcpCheckoutClient.updateCheckoutSession()` (full replacement), update local snapshot
    - `completeSession(sessionId, paymentInstrument)` — call `UcpCheckoutClient.completeCheckoutSession()`, handle response status
    - `cancelSession(sessionId)` — call `UcpCheckoutClient.cancelCheckoutSession()`, update local status
    - After every UCP call, inspect returned `status` and react:
      - `requires_escalation` → store `continue_url`, return it to caller
      - `ready_for_complete` → if payment instrument available, auto-call `completeSession()`
      - `completed` → publish `order.confirmed` to BullMQ `order-events` queue
      - `canceled` → update local status, return error
    - Reject operations on sessions with `ucp_status = canceled`
    - Emit structured JSON log on every status change (`sessionId`, `fromStatus`, `toStatus`, `timestamp`)
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 14.3_

  - [ ]* 4.3 Write property test for checkout session create round-trip (Property 1)
    - **Property 1: Checkout session create round-trip**
    - **Validates: Requirements 1.1, 1.3**

  - [ ]* 4.4 Write property test for checkout session update replaces line items (Property 2)
    - **Property 2: Checkout session update replaces line items**
    - **Validates: Requirements 1.2**

  - [ ]* 4.5 Write property test for totals snapshot invariant (Property 3)
    - **Property 3: Totals snapshot invariant**
    - **Validates: Requirements 1.3, 4.5**

  - [ ]* 4.6 Write property test for UCP status stored accurately (Property 8)
    - **Property 8: UCP status stored accurately**
    - **Validates: Requirements 2.1, 2.2**

  - [ ]* 4.7 Write property test for `requires_escalation` surfaces `continue_url` (Property 9)
    - **Property 9: `requires_escalation` surfaces `continue_url`**
    - **Validates: Requirements 2.3**

  - [ ]* 4.8 Write property test for `ready_for_complete` triggers auto-complete (Property 10)
    - **Property 10: `ready_for_complete` triggers auto-complete**
    - **Validates: Requirements 2.4**

  - [ ]* 4.9 Write property test for `completed` triggers `order.confirmed` event (Property 11)
    - **Property 11: `completed` status triggers `order.confirmed` event**
    - **Validates: Requirements 2.5, 5.1**

  - [ ]* 4.10 Write property test for canceled session is terminal (Property 12)
    - **Property 12: Canceled session is terminal**
    - **Validates: Requirements 2.6**

- [ ] 5. CheckoutModule — controller and payment
  - [ ] 5.1 Implement `CheckoutController`
    - `POST /commerce/checkout/sessions` — create session; validate `line_items`, `buyer`, `context` DTOs
    - `GET /commerce/checkout/sessions/:id` — return local session state
    - `PUT /commerce/checkout/sessions/:id` — update session (full replacement)
    - `POST /commerce/checkout/sessions/:id/complete` — trigger Complete Checkout with `payment_instrument` body
    - `POST /commerce/checkout/sessions/:id/cancel` — cancel session
    - `GET /commerce/checkout/sessions/:id/summary` — return totals in display currency (convert from cents)
    - _Requirements: 2.1, 3.1, 4.5_

  - [ ]* 5.2 Write property test for payment instrument required for Complete (Property 13)
    - **Property 13: Payment instrument required for Complete**
    - **Validates: Requirements 3.1**

  - [ ]* 5.3 Write property test for Complete Checkout failure leaves status unchanged (Property 14)
    - **Property 14: Complete Checkout failure leaves status unchanged**
    - **Validates: Requirements 3.2**

  - [ ]* 5.4 Write property test for summary amounts in display currency (Property 15)
    - **Property 15: Summary amounts are in display currency**
    - **Validates: Requirements 4.5**

  - [ ]* 5.5 Write property test for summary grand total invariant (Property 16)
    - **Property 16: Summary grand total invariant**
    - **Validates: Requirements 4.5**

  - [ ]* 5.6 Write property test for line item limit enforced (Property 6)
    - **Property 6: Line item limit enforced**
    - **Validates: Requirements 1.6**

  - [ ]* 5.7 Write property test for zero-quantity item excluded (Property 7)
    - **Property 7: Zero-quantity item excluded from session**
    - **Validates: Requirements 1.7**

- [ ] 6. Checkpoint — CheckoutModule
  - Ensure all CheckoutModule tests pass. Ask the user if questions arise.

- [ ] 7. OrderModule — order creation and history
  - [ ] 7.1 Define `Order` and `OrderStatusHistory` TypeORM entities
    - `Order` entity with `{ schema: 'orders', name: 'orders' }` — JSONB fields: `lineItems`, `fulfillment`, `adjustments`, `totals`
    - `OrderStatusHistory` entity with `{ schema: 'orders', name: 'order_status_history' }`
    - _Requirements: 13.2_

  - [ ] 7.2 Implement `OrderService` — BullMQ consumer and order creation
    - Consume `order.confirmed` from BullMQ `order-events` queue
    - Create `orders.orders` record with `status = processing`, `ucp_order_id`, `checkout_id`, `permalink_url`, `line_items`, `fulfillment`, `totals`; write initial `order_status_history`; write `audit_log` — all in one PostgreSQL transaction
    - Return `orderId`, `ucpOrderId`, `status`, `permalinkUrl` in confirmation payload
    - Emit structured JSON log on every status change
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 14.4_

  - [ ]* 7.3 Write property test for order creation completeness (Property 17)
    - **Property 17: Order creation completeness**
    - **Validates: Requirements 5.1, 5.2, 5.3, 5.4**

  - [ ] 7.4 Implement order history and status query endpoints
    - `GET /commerce/orders` — cursor-based paginated history scoped to `customerId`, ordered by `createdAt DESC`, default page size 20
    - `GET /commerce/orders/:id` — order detail with status history, fulfillment events, and adjustments; return `not_found` if order does not belong to authenticated customer
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 7.1, 7.2, 7.3, 7.4_

  - [ ]* 7.5 Write property test for order history customer-scoped and ordered (Property 18)
    - **Property 18: Order history is customer-scoped and ordered**
    - **Validates: Requirements 6.1, 6.3, 6.4**

  - [ ]* 7.6 Write property test for order history pagination correctness (Property 19)
    - **Property 19: Order history pagination correctness**
    - **Validates: Requirements 6.2**

  - [ ]* 7.7 Write property test for cross-customer order isolation (Property 20)
    - **Property 20: Cross-customer order isolation**
    - **Validates: Requirements 6.4, 7.4**

  - [ ]* 7.8 Write property test for fulfilled order includes fulfillment events (Property 21)
    - **Property 21: Fulfilled order includes fulfillment events**
    - **Validates: Requirements 7.3**

- [ ] 8. OrderModule — cancellations, returns, adjustments, and audit log
  - [ ] 8.1 Implement cancellation and return endpoints
    - `POST /commerce/orders/:id/cancel` — validate status is `processing`; append `cancellation` adjustment to `adjustments` JSONB; transition to `cancelled`; write status history and audit log in one transaction
    - `POST /commerce/orders/:id/return` — validate status is `fulfilled`; append `return` adjustment; transition to `return_requested`; write status history and audit log
    - Reject with `cancellation_not_allowed` for `fulfilled` orders
    - Reject with `return_not_eligible` for non-`fulfilled` orders
    - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.5_

  - [ ]* 8.2 Write property test for cancellation eligibility invariant (Property 22)
    - **Property 22: Cancellation eligibility invariant**
    - **Validates: Requirements 8.1, 8.2**

  - [ ]* 8.3 Write property test for return eligibility invariant (Property 23)
    - **Property 23: Return eligibility invariant**
    - **Validates: Requirements 8.3, 8.4**

  - [ ]* 8.4 Write property test for adjustments are append-only (Property 24)
    - **Property 24: Adjustments are append-only**
    - **Validates: Requirements 8.5, 9.6**

  - [ ] 8.5 Implement `AuditService` — append-only audit log
    - `AuditService.write()` always runs inside the same PostgreSQL transaction as the order mutation
    - If the audit INSERT fails, the entire transaction rolls back and the caller receives 500
    - No UPDATE or DELETE operations permitted on `orders.audit_log`
    - _Requirements: 19.1, 19.2, 19.3, 19.5_

  - [ ]* 8.6 Write property test for audit log completeness and immutability (Property 32)
    - **Property 32: Audit log completeness and immutability**
    - **Validates: Requirements 19.1, 19.2, 19.3**

  - [ ]* 8.7 Write property test for audit log write failure rolls back mutation (Property 33)
    - **Property 33: Audit log write failure rolls back mutation**
    - **Validates: Requirements 19.5**

- [ ] 9. OrderModule — webhook handler and platform profile
  - [ ] 9.1 Implement `PlatformProfileController`
    - `GET /.well-known/ucp` — return our platform's UCP profile document
    - Include `dev.ucp.shopping.order` capability with `config.webhook_url: "${PLATFORM_BASE_URL}/commerce/webhooks/ucp/orders"`
    - Include our platform's public signing key (JWK) so merchants can verify our request signatures
    - _Requirements: 9.1_

  - [ ]* 9.2 Write property test for platform profile exposes webhook URL (Property 34)
    - **Property 34: Platform profile exposes webhook URL**
    - **Validates: Requirements 9.1**

  - [ ] 9.3 Implement `WebhookController` and `WebhookService`
    - `POST /commerce/webhooks/ucp/orders` — extract `merchant_id`; call `WebhookVerificationService.verifyWebhook()`; return 401 on failure
    - Check `orders.webhook_events` for duplicate `event_id`; if duplicate return 200 without reprocessing
    - Insert `webhook_events` record with `status = queued`, `signature_verified = true`; enqueue to BullMQ `webhook-ingestion` queue; return 200 within 2 seconds
    - _Requirements: 9.1, 9.2, 9.3, 9.7, 9.8_

  - [ ]* 9.4 Write property test for webhook idempotency (Property 28)
    - **Property 28: Webhook idempotency**
    - **Validates: Requirements 9.8**

  - [ ]* 9.5 Write property test for webhook response latency (Property 27)
    - **Property 27: Webhook response latency**
    - **Validates: Requirements 9.7**

  - [ ] 9.6 Implement BullMQ consumers for webhook-driven order updates
    - Consume `webhook-ingestion` queue; parse UCP order payload
    - Update `orders.orders`: append new fulfillment events to `fulfillment.events`, append new adjustments to `adjustments`, update `totals`, derive and update `status`
    - Write `order_status_history` and `audit_log` in the same transaction
    - Publish `order.shipped` or `payment.failed` events to `order-events` queue as appropriate
    - _Requirements: 9.4, 9.5, 9.6_

  - [ ]* 9.7 Write property test for webhook status update correctness (Property 26)
    - **Property 26: Webhook status update correctness**
    - **Validates: Requirements 9.4, 9.5, 9.6**

  - [ ]* 9.8 Write property test for merchant profile cache consistency (Property 35)
    - **Property 35: Merchant profile cache consistency**
    - **Validates: Requirements 15.1**

- [ ] 10. Checkpoint — OrderModule
  - Ensure all OrderModule tests pass. Ask the user if questions arise.

- [ ] 11. Python ChatService — intent routing and feature flags
  - [ ] 11.1 Extend `Intent_Classifier` with commerce intents
    - Add intent recognition for: `checkout_initiate`, `add_to_cart`, `remove_from_cart`, `view_cart`, `order_status`, `order_history`, `cancel_order` in `backend/app/services/chat_service.py`
    - Add slot extraction for `product_id`, `quantity`, `buyer` (name, email), `context` (address hints), `payment_instrument`
    - Re-prompt customer for missing required slots before forwarding
    - Resolve ambiguous product references via RAG_Pipeline before emitting structured intent payload
    - When commerce service returns `requires_escalation`, format the `continue_url` as a clickable link in the chat response
    - _Requirements: 11.1, 20.1, 20.2, 20.3, 20.4, 20.5_

  - [ ] 11.2 Integrate LaunchDarkly feature flag evaluation
    - Add LaunchDarkly SDK to `backend/` dependencies
    - Evaluate flag before routing any commerce intent; default to disabled when LaunchDarkly is unreachable
    - Return graceful "feature currently unavailable" response when flag is off
    - _Requirements: 17.1, 17.2, 17.3, 17.4, 17.5_

  - [ ] 11.3 Wire ChatService HTTP calls to `checkout-order-service/`
    - Add `CommerceClient` in `backend/app/clients/commerce_client.py` with methods for each commerce intent
    - Base URL: `http://checkout-order-service:3001` (configurable via `COMMERCE_SERVICE_URL` env var)
    - Propagate `X-Request-ID` through all downstream calls
    - Format structured service responses into natural language LLM replies
    - Handle `requires_escalation` response: extract `continue_url` and present it to the user
    - _Requirements: 11.2, 11.3, 11.4, 14.5_

  - [ ]* 11.4 Write unit tests for intent routing and slot filling
    - _Requirements: 11.1, 11.2, 20.1, 20.2_

- [ ] 12. RAG pipeline extension for order history
  - [ ] 12.1 Extend RAG indexing pipeline to include order embeddings
    - Add order embedding indexer in `rag-service/` that consumes `order.confirmed` and order status change events
    - Index order records as user-scoped embeddings keyed by `customer_id`
    - Trigger re-indexing within 5 minutes of any order status change
    - _Requirements: 12.1, 12.3_

  - [ ] 12.2 Enforce customer-scoped retrieval for order embeddings
    - Modify RAG retrieval query to always include `customer_id` scope filter
    - Ensure order embeddings from customer A are never returned in a query scoped to customer B
    - _Requirements: 12.2, 12.4_

  - [ ]* 12.3 Write unit tests for RAG order embedding isolation
    - _Requirements: 12.3, 12.4_

- [ ] 13. Frontend — order tracker and escalation handoff
  - [ ] 13.1 Create `OrderTracker` component in `Frontend/components/`
    - Display order status, fulfillment events timeline, and adjustments
    - Accepts `orderId` prop; fetches from `GET /commerce/orders/:id`
    - Render `permalink_url` as a link to the merchant's order page when available
    - _Requirements: 7.1, 7.2, 7.3_

  - [ ] 13.2 Handle `requires_escalation` in chat UI
    - When ChatService returns a `continue_url`, render it as a prominent call-to-action button in the chat message
    - _Requirements: 2.3_

  - [ ]* 13.3 Write unit tests for OrderTracker
    - _Requirements: 7.3_

- [ ] 14. Final checkpoint — end-to-end integration
  - [ ] 14.1 Write E2E integration test for full checkout flow
    - Simulate `checkout_initiate` → session create → update → `ready_for_complete` → complete → `order.confirmed` event → order appears in `GET /commerce/orders`
    - Use Dockerised PostgreSQL and Redis; mock merchant UCP endpoint via nock
    - _Requirements: 1.1, 2.1, 3.1, 5.1, 6.1_

  - [ ] 14.2 Write E2E test for `requires_escalation` flow
    - Simulate merchant returning `requires_escalation`; assert `continue_url` is returned to caller and no Complete Checkout call is made
    - _Requirements: 2.3_

  - [ ] 14.3 Validate health endpoint and trace propagation
    - Confirm `GET /commerce/health` returns 200 with correct dependency status
    - Confirm `X-Request-ID` propagation through ChatService → `checkout-order-service/`
    - _Requirements: 14.1, 14.2, 14.5_

  - Ensure all tests pass. Ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for a faster MVP
- All three feature modules (`CheckoutModule`, `OrderModule`, `UcpClientModule`) live in one NestJS app at `checkout-order-service/` — no separate processes
- Modules communicate via NestJS dependency injection, not HTTP
- All migrations live under `checkout-order-service/src/migrations/` split by schema
- Property tests use `fast-check` with a minimum of 100 iterations per property
- Unit tests use Jest with `@nestjs/testing`
- Merchant UCP endpoints are mocked via `nock` in all automated tests — no real UCP calls in CI
- UCP amounts are always integers in minor units (cents); convert to display currency only in API responses
- The existing `UcpGatewayModule` code (VaultService, TokenExchangeService, UcpProxyService) will be replaced by `UcpClientModule` in Task 2 — the old module can be removed once Task 2 is complete
