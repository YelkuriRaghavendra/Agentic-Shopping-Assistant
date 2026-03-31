# Requirements Document

## Introduction

This document defines the business and functional requirements for the checkout and order capabilities added to the existing AI-powered conversational commerce platform.

The platform already has a Python/FastAPI chat backend, a Next.js frontend, a RAG retrieval service, and a shared PostgreSQL database. The new services extend the platform to support the full purchase lifecycle: cart management, checkout flow, payment, order history, status tracking, cancellations, returns, and async event ingestion from the Unified Commerce Platform (UCP).

All UCP interactions are proxied exclusively through the UCP_Gateway_Service — the single chokepoint for all UCP API families (`/cart`, `/checkout`, `/orders`, `/returns`). The LLM orchestrator never calls UCP APIs directly. New LLM intents are classified and routed through the existing `ChatService` orchestrator, which emits structured JSON via function-calling to invoke the appropriate downstream service.

The architecture introduces several new bounded services: a Payment_Service for PCI-DSS-scoped tokenisation, a Notification_Service for order confirmations and shipping alerts, a Webhook_Handler for async UCP events, an Event_Bus for decoupled async processing, an Audit_Log for compliance-grade mutation records, a Secret_Store for credential management, and a Feature_Flag service to gate commerce intents with instant kill-switch capability.

---

## Glossary

- **Checkout_Service**: The NestJS microservice responsible for cart management, checkout session lifecycle, payment method selection, promo/tax application, and order confirmation.
- **Order_Service**: The NestJS microservice responsible for order history queries, order status tracking, cancellation/return requests, and ingestion of async UCP webhook events.
- **UCP**: Unified Commerce Platform — the external third-party platform exposing cart, checkout, orders, inventory, payment, and fulfilment APIs.
- **UCP_Gateway_Service**: The single internal chokepoint for all UCP API families (`/cart`, `/checkout`, `/orders`, `/returns`). Owns idempotency key management, retry logic with exponential backoff, UCP credential rotation, session tokenisation, cart lifecycle, and payment method tokenisation. The LLM orchestrator never calls UCP directly — all UCP traffic flows through this service.
- **Checkout_FSM**: The Finite State Machine governing checkout session state transitions: `IDLE → CART_BUILDING → AWAITING_ADDRESS → AWAITING_PAYMENT → AWAITING_CONFIRM → PLACING → COMPLETE`. `IDLE` = no active checkout; `CART_BUILDING` = cart being assembled before checkout initiation; `AWAITING_ADDRESS` = collecting shipping address; `AWAITING_PAYMENT` = collecting payment method; `AWAITING_CONFIRM` = waiting for customer confirmation; `PLACING` = order being placed with UCP; `COMPLETE` = order confirmed. FSM state is persisted in Redis.
- **Cart**: A transient collection of product line items associated with a customer session, stored in Redis.
- **Checkout_Session**: A persistent record in the `checkout` PostgreSQL schema representing one checkout attempt, including FSM state, selected payment method, applied promos, and tax totals.
- **Order**: A confirmed purchase record stored in the `orders` PostgreSQL schema, created after UCP confirms payment.
- **Order_DB**: The PostgreSQL database storing order history and order state.
- **Token_Exchange**: The internal service that maps a platform session token to UCP credentials, ensuring the LLM never handles raw UCP auth tokens.
- **Intent_Classifier**: The existing component in `ChatService` that classifies user messages into named intents and routes them to the appropriate tool or service.
- **Redis**: The shared in-memory store used for cart state, FSM state, and session data.
- **RAG_Pipeline**: The existing retrieval-augmented generation pipeline used for product search, extended to also index user-scoped order history.
- **Webhook_Handler**: The HTTP endpoint that ingests async UCP lifecycle events (order.confirmed, shipped, failed, etc.) and publishes them to the Event_Bus after HMAC signature verification.
- **API_Gateway**: The entry-point reverse proxy routing external traffic to the correct internal service.
- **Payment_Service**: A separate bounded service responsible exclusively for payment tokenisation and charge execution using UCP hosted tokenisation. Operates within PCI-DSS scope isolation — raw card data never leaves this service.
- **Notification_Service**: The service responsible for sending order confirmation and shipping notification messages to customers via email and/or SMS.
- **Event_Bus**: The async messaging infrastructure (Kafka or SQS) used to decouple event producers (Webhook_Handler, Checkout_Service) from consumers (Order_Service, Notification_Service).
- **Audit_Log**: An immutable, append-only compliance-grade log recording all order mutations with actor, action, timestamp, before/after state, and source.
- **Secret_Store**: The secrets management service (e.g. HashiCorp Vault) used to store and rotate UCP API credentials and HMAC secrets.
- **Feature_Flag**: The feature flag service (e.g. LaunchDarkly) used to gate commerce intents, supporting percentage-based rollout and instant kill-switch without redeployment.
- **Idempotency_Guard**: The sub-component of UCP_Gateway_Service that deduplicates mutating UCP requests using client-generated idempotency keys within a 24-hour window.

---

## Requirements

### Requirement 1: Cart Management

**User Story:** As a customer, I want to add, remove, and view items in my cart through the chat interface, so that I can build my order conversationally before checking out.

#### Acceptance Criteria

1. WHEN the Intent_Classifier detects an `add_to_cart` intent, THE Checkout_Service SHALL add the specified product and quantity to the customer's Cart in Redis, keyed by `customer_id`.
2. WHEN the Intent_Classifier detects a `remove_from_cart` intent, THE Checkout_Service SHALL remove the specified line item from the customer's Cart in Redis.
3. WHEN the Intent_Classifier detects a `view_cart` intent, THE Checkout_Service SHALL return the current Cart contents including product IDs, names, quantities, unit prices, and a calculated subtotal.
4. WHILE a Cart exists in Redis, THE Checkout_Service SHALL preserve Cart state for a minimum of 60 minutes of inactivity before expiry.
5. IF a product is added to the Cart and the UCP Inventory Engine reports zero available stock, THEN THE Checkout_Service SHALL reject the add operation and return an `out_of_stock` error to the caller.
6. THE Checkout_Service SHALL enforce a maximum of 50 distinct line items per Cart.
7. WHEN a Cart item quantity is updated to zero, THE Checkout_Service SHALL remove that line item from the Cart automatically.

---

### Requirement 2: Checkout Session Lifecycle (FSM)

**User Story:** As a customer, I want to initiate and progress through a checkout flow conversationally, so that I can complete a purchase without leaving the chat interface.

#### Acceptance Criteria

1. WHEN the Intent_Classifier detects a `checkout_initiate` intent, THE Checkout_Service SHALL create a Checkout_Session record in the `checkout` schema and transition the Checkout_FSM from `CART_BUILDING` to `AWAITING_ADDRESS`.
2. THE Checkout_FSM SHALL enforce the following state transition sequence: `IDLE → CART_BUILDING → AWAITING_ADDRESS → AWAITING_PAYMENT → AWAITING_CONFIRM → PLACING → COMPLETE`.
3. IF a Checkout_FSM transition is requested for a state that is not the immediate next valid state, THEN THE Checkout_Service SHALL reject the transition and return an `invalid_transition` error.
4. WHILE the Checkout_FSM is in the `CART_BUILDING` state, THE Checkout_Service SHALL allow Cart modifications (add, remove, update quantity).
5. WHILE the Checkout_FSM is in `AWAITING_ADDRESS` or a later state, THE Checkout_Service SHALL reject Cart modification requests and return a `checkout_locked` error.
6. WHEN the Checkout_FSM reaches the `COMPLETE` state, THE Checkout_Service SHALL publish an `order.confirmed` event to the internal message queue for consumption by Order_Service.
7. THE Checkout_Service SHALL persist the current FSM state in both Redis (for low-latency reads) and the `checkout.checkout_sessions` PostgreSQL table (for durability).
8. IF a Checkout_Session remains in `AWAITING_PAYMENT` state for more than 15 minutes without a payment confirmation, THEN THE Checkout_Service SHALL transition the FSM to `IDLE` and release the Cart.

---

### Requirement 3: Payment Method Selection and Payment Bridge

**User Story:** As a customer, I want to select a payment method during checkout, so that I can complete my purchase using my preferred payment option.

#### Acceptance Criteria

1. WHEN a customer selects a payment method during checkout, THE Checkout_Service SHALL record the selected payment method on the Checkout_Session and transition the Checkout_FSM to `AWAITING_PAYMENT`.
2. THE Checkout_Service SHALL proxy all payment method listing and payment initiation requests through UCP_Gateway_Service to the UCP Payment Gateway — the LLM SHALL NOT call the UCP Payment Gateway directly.
3. WHEN the UCP Payment Gateway returns a payment confirmation, THE Checkout_Service SHALL transition the Checkout_FSM to `AWAITING_CONFIRM`, then to `PLACING`, and then to `COMPLETE`.
4. IF the UCP Payment Gateway returns a payment failure, THEN THE Checkout_Service SHALL transition the Checkout_FSM back to `AWAITING_PAYMENT` and return a `payment_failed` error with a human-readable reason to the caller.
5. THE Token_Exchange SHALL resolve a platform session token to the corresponding UCP credentials before any UCP Payment Gateway call is made.

---

### Requirement 4: Promo Code and Tax Application

**User Story:** As a customer, I want to apply promo codes and see accurate tax totals before confirming my order, so that I know the final price I will be charged.

#### Acceptance Criteria

1. WHEN a customer provides a promo code during checkout, THE Checkout_Service SHALL validate the code against the UCP Promo API via UCP_Gateway_Service and apply the resulting discount to the Checkout_Session.
2. IF a promo code is invalid or expired, THEN THE Checkout_Service SHALL return a `promo_invalid` error with a descriptive message and leave the Checkout_Session totals unchanged.
3. WHEN a Checkout_Session transitions to `AWAITING_ADDRESS`, THE Checkout_Service SHALL calculate applicable taxes by calling the UCP Tax API via UCP_Gateway_Service and store the tax total on the Checkout_Session.
4. THE Checkout_Service SHALL recalculate taxes whenever a Cart line item is added or removed while the Checkout_FSM is in `CART_BUILDING` state.
5. THE Checkout_Service SHALL expose a `GET /checkout/sessions/:id/summary` endpoint that returns the Cart subtotal, applied discount, tax total, and grand total.

---

### Requirement 5: Order Confirmation and Order Creation

**User Story:** As a customer, I want to receive an order confirmation after completing checkout, so that I have a record of my purchase.

#### Acceptance Criteria

1. WHEN the Checkout_FSM reaches the `COMPLETE` state, THE Order_Service SHALL consume the `order.confirmed` event from the message queue and create an Order record in the `orders.orders` PostgreSQL table.
2. THE Order_Service SHALL assign a unique `order_id` (UUID) to each Order at creation time.
3. WHEN an Order is created, THE Order_Service SHALL store the customer ID, order line items, payment method, subtotal, discount, tax, grand total, and initial status of `pending`.
4. WHEN an Order is created, THE Order_Service SHALL return an order confirmation payload including `order_id`, `status`, `grand_total`, and estimated delivery date to the caller.

---

### Requirement 6: Order History

**User Story:** As a customer, I want to query my past orders through the chat interface, so that I can review what I have purchased.

#### Acceptance Criteria

1. WHEN the Intent_Classifier detects an `order_history` intent, THE Order_Service SHALL return a paginated list of Orders for the authenticated customer, ordered by creation date descending.
2. THE Order_Service SHALL support cursor-based pagination with a configurable page size defaulting to 20 orders per page.
3. WHEN returning Order history, THE Order_Service SHALL include for each Order: `order_id`, `status`, `grand_total`, `created_at`, and a summary of line items.
4. THE Order_Service SHALL scope all Order history queries to the authenticated `customer_id` — cross-customer data access SHALL NOT be permitted.

---

### Requirement 7: Order Status Tracking

**User Story:** As a customer, I want to check the current status of a specific order through the chat interface, so that I know where my order is.

#### Acceptance Criteria

1. WHEN the Intent_Classifier detects an `order_status` intent with a valid `order_id`, THE Order_Service SHALL return the current status and status history of the specified Order.
2. THE Order_Service SHALL support the following Order status values: `pending`, `confirmed`, `processing`, `shipped`, `delivered`, `cancelled`, `return_requested`, `returned`.
3. WHEN an Order status is `shipped`, THE Order_Service SHALL include the UCP-provided tracking number and carrier name in the status response.
4. IF the requested `order_id` does not belong to the authenticated customer, THEN THE Order_Service SHALL return a `not_found` error — the actual existence of the order SHALL NOT be disclosed.

---

### Requirement 8: Order Cancellation and Returns

**User Story:** As a customer, I want to cancel an order or request a return through the chat interface, so that I can manage my purchases without contacting support.

#### Acceptance Criteria

1. WHEN the Intent_Classifier detects a `cancel_order` intent with a valid `order_id`, THE Order_Service SHALL submit a cancellation request to the UCP Orders API via UCP_Gateway_Service and transition the Order status to `cancelled` upon UCP confirmation.
2. IF an Order has a status of `shipped` or `delivered`, THEN THE Order_Service SHALL reject a cancellation request and return a `cancellation_not_allowed` error with a reason.
3. WHEN a return is requested for a delivered Order, THE Order_Service SHALL submit a return request to the UCP Orders API via UCP_Gateway_Service and transition the Order status to `return_requested`.
4. IF a return is requested for an Order that is not in `delivered` status, THEN THE Order_Service SHALL return a `return_not_eligible` error.
5. THE Order_Service SHALL record the cancellation or return reason provided by the customer on the Order record.

---

### Requirement 9: Webhook Ingestion for Async UCP Events

**User Story:** As a platform operator, I want the system to receive and process async lifecycle events from UCP, so that order statuses are kept accurate without polling.

#### Acceptance Criteria

1. THE Webhook_Handler SHALL expose a `POST /webhooks/ucp` endpoint that accepts UCP lifecycle event payloads.
2. WHEN a UCP webhook event is received, THE Webhook_Handler SHALL validate the event signature using a shared HMAC secret before processing.
3. IF a webhook event signature is invalid, THEN THE Webhook_Handler SHALL return HTTP 401 and discard the event without processing.
4. WHEN a `payment_failed` UCP event is received, THE Order_Service SHALL update the corresponding Order status to `payment_failed` and publish a notification event to the internal event bus.
5. WHEN a `shipped` UCP event is received, THE Order_Service SHALL update the corresponding Order status to `shipped` and store the tracking number and carrier name on the Order record.
6. WHEN a `delivered` UCP event is received, THE Order_Service SHALL update the corresponding Order status to `delivered` and record the delivery timestamp.
7. THE Webhook_Handler SHALL respond to all valid UCP webhook events with HTTP 200 within 2 seconds of receipt, deferring all processing to an async queue.
8. THE Webhook_Handler SHALL implement idempotency using the UCP-provided `event_id` — duplicate events with the same `event_id` SHALL be acknowledged but not reprocessed.

---

### Requirement 10: Token Exchange Layer

**User Story:** As a platform operator, I want all UCP API calls to use properly scoped credentials, so that the LLM and chat layer never have access to raw UCP authentication tokens.

#### Acceptance Criteria

1. THE Token_Exchange SHALL accept a platform session token and return a short-lived UCP access token scoped to the authenticated customer.
2. WHEN a UCP access token is requested, THE Token_Exchange SHALL cache the token in Redis with a TTL matching the token's expiry minus a 30-second buffer.
3. IF a cached UCP access token is within 30 seconds of expiry, THEN THE Token_Exchange SHALL proactively refresh the token before returning it.
4. THE Token_Exchange SHALL never expose UCP credentials in API responses, logs, or error messages returned to the chat layer.
5. IF the UCP token endpoint is unavailable, THEN THE Token_Exchange SHALL return a `ucp_auth_unavailable` error and the calling service SHALL surface a user-friendly message without disclosing UCP details.

---

### Requirement 11: New LLM Intent Routing

**User Story:** As a developer, I want the existing Intent_Classifier to recognise checkout and order intents, so that conversational commands are routed to the correct new service.

#### Acceptance Criteria

1. THE Intent_Classifier SHALL recognise and classify the following new intents: `checkout_initiate`, `add_to_cart`, `remove_from_cart`, `view_cart`, `order_status`, `order_history`, `cancel_order`.
2. WHEN a checkout or order intent is classified, THE ChatService SHALL route the request to the appropriate Checkout_Service or Order_Service endpoint via an internal HTTP call — the LLM SHALL NOT call these services directly.
3. THE ChatService SHALL include the resolved UCP token (via Token_Exchange) in all internal calls to Checkout_Service and Order_Service.
4. WHEN Checkout_Service or Order_Service returns a structured response, THE ChatService SHALL format the response into a natural language reply using the LLM before returning it to the customer.

---

### Requirement 12: RAG Pipeline Extension for Order History

**User Story:** As a customer, I want the AI assistant to reference my order history when answering questions, so that I get personalised, contextually relevant responses.

#### Acceptance Criteria

1. THE RAG_Pipeline SHALL index Order records as user-scoped embeddings, keyed by `customer_id`, so that order history is only retrievable in the context of the owning customer.
2. WHEN a customer asks a question that references past orders, THE RAG_Pipeline SHALL retrieve relevant Order embeddings alongside product embeddings and include them in the LLM context.
3. THE RAG_Pipeline SHALL re-index a customer's Order embeddings within 5 minutes of an Order status change.
4. THE RAG_Pipeline SHALL never return Order embeddings belonging to one customer in a query scoped to a different customer.

---

### Requirement 13: Database Schema Isolation

**User Story:** As a platform engineer, I want the new services to use isolated PostgreSQL schemas, so that the existing chat data is not affected by checkout and order migrations.

#### Acceptance Criteria

1. THE Checkout_Service SHALL use the `checkout` PostgreSQL schema for all its tables — no tables SHALL be created in the default `public` schema.
2. THE Order_Service SHALL use the `orders` PostgreSQL schema for all its tables — no tables SHALL be created in the default `public` schema.
3. THE Checkout_Service and Order_Service SHALL each maintain their own TypeORM migration files under `services/checkout-service/src/migrations/` and `services/order-service/src/migrations/` respectively.
4. WHEN a migration is run, THE migration runner SHALL apply only the migrations for the target service's schema without affecting other schemas.
5. THE Checkout_Service and Order_Service SHALL reference the `customers` table in the `public` schema via a foreign key — they SHALL NOT duplicate customer data.

---

### Requirement 14: Observability and Health

**User Story:** As a platform operator, I want both new services to expose health and metrics endpoints, so that I can monitor them in the existing observability stack.

#### Acceptance Criteria

1. THE Checkout_Service SHALL expose a `GET /health` endpoint returning HTTP 200 with service name, version, and dependency status (PostgreSQL, Redis, UCP reachability).
2. THE Order_Service SHALL expose a `GET /health` endpoint returning HTTP 200 with service name, version, and dependency status (PostgreSQL, Redis, message queue reachability).
3. THE Checkout_Service SHALL emit structured JSON logs for every FSM state transition, including `session_id`, `from_state`, `to_state`, and `timestamp`.
4. THE Order_Service SHALL emit structured JSON logs for every Order status change, including `order_id`, `from_status`, `to_status`, `source` (webhook or API), and `timestamp`.
5. WHERE distributed tracing is enabled, THE Checkout_Service and Order_Service SHALL propagate the incoming `X-Request-ID` header through all downstream UCP calls and internal service calls.

---

### Requirement 15: UCP Gateway Service — Idempotency and Retry

**User Story:** As a platform operator, I want all mutating UCP calls to be idempotent and resilient, so that network failures and retries never result in duplicate orders or charges.

#### Acceptance Criteria

1. THE UCP_Gateway_Service SHALL attach a client-generated idempotency key to every mutating UCP call (cart add, checkout initiate, order place).
2. THE Idempotency_Guard SHALL deduplicate requests carrying the same idempotency key within a 24-hour window — duplicate requests SHALL return the cached response without re-executing the UCP call.
3. WHEN a UCP call fails with a transient error, THE UCP_Gateway_Service SHALL retry the call using exponential backoff with jitter, up to a maximum of 3 retry attempts.
4. WHEN the UCP API is unavailable and the retry limit is exhausted, THE UCP_Gateway_Service SHALL open a circuit breaker and return a `ucp_unavailable` error to the caller without further retry attempts.
5. THE UCP_Gateway_Service SHALL be the sole service permitted to call UCP APIs — no other internal service SHALL call UCP directly.

---

### Requirement 16: PCI-DSS Scope Isolation

**User Story:** As a compliance officer, I want all payment card data to be handled exclusively within an isolated bounded service, so that the LLM, chat layer, and order services are outside PCI-DSS scope.

#### Acceptance Criteria

1. THE Payment_Service SHALL be the only service that handles raw payment method data — no other service, including the LLM orchestrator and ChatService, SHALL receive, store, or log raw card data.
2. THE Payment_Service SHALL tokenise payment methods using UCP hosted tokenisation before any token is passed to other services.
3. THE Payment_Service SHALL be deployed as a separate bounded service with its own network boundary, isolated from the LLM and chat layers.
4. IF raw card data is detected in any log, API response, or message queue payload outside the Payment_Service boundary, THE system SHALL treat this as a critical security violation and alert the operations team.
5. THE Audit_Log SHALL record payment events using payment tokens only — card numbers, CVVs, and expiry dates SHALL NOT appear in any audit record.

---

### Requirement 17: Feature Flags for Commerce Intents

**User Story:** As a product operator, I want all commerce intents to be gated behind feature flags, so that I can roll out, roll back, or kill commerce features instantly without a redeployment.

#### Acceptance Criteria

1. THE Intent_Classifier SHALL evaluate the Feature_Flag service before routing any commerce intent (`checkout_initiate`, `add_to_cart`, `remove_from_cart`, `view_cart`, `order_status`, `order_history`, `cancel_order`).
2. THE Feature_Flag service SHALL support percentage-based rollout, allowing commerce intents to be enabled for a configurable percentage of customers.
3. THE Feature_Flag service SHALL support an instant kill-switch that disables all commerce intents without requiring a service redeployment.
4. WHEN a commerce intent is disabled by a feature flag, THE ChatService SHALL inform the customer that the feature is currently unavailable and return a graceful, non-error response.
5. IF the Feature_Flag service is unreachable, THEN THE Intent_Classifier SHALL default to disabling commerce intents and log the flag evaluation failure.

---

### Requirement 18: Notification Service

**User Story:** As a customer, I want to receive timely notifications about my order status, so that I am kept informed without having to query the chat interface.

#### Acceptance Criteria

1. WHEN an `order.confirmed` event is received from the Event_Bus, THE Notification_Service SHALL send an order confirmation message to the customer via email and/or SMS within 60 seconds of the event.
2. WHEN an `order.shipped` event is received from the Event_Bus, THE Notification_Service SHALL send a shipping notification to the customer that includes the tracking number and carrier name.
3. WHEN a `payment.failed` event is received from the Event_Bus, THE Notification_Service SHALL send a payment failure notification to the customer with a prompt to retry or update their payment method.
4. THE Notification_Service SHALL not include raw payment data, card numbers, or UCP credentials in any outbound notification.
5. IF a notification delivery fails, THE Notification_Service SHALL retry delivery up to 3 times with exponential backoff before logging the failure and discarding the notification.

---

### Requirement 19: Audit Log

**User Story:** As a compliance officer, I want an immutable record of all order mutations, so that I can satisfy regulatory audit requirements and investigate disputes.

#### Acceptance Criteria

1. THE Audit_Log SHALL record an entry for every order mutation event: order creation, status change, cancellation, and return initiation.
2. WHEN an audit entry is written, THE Audit_Log SHALL capture: actor (customer ID or system component), action type, ISO 8601 timestamp, before-state, after-state, and source (API call or webhook event).
3. THE Audit_Log SHALL be append-only — existing entries SHALL NOT be modified or deleted by any service or operator action.
4. THE Audit_Log SHALL retain all entries for a minimum of 7 years from the date of the recorded event.
5. IF a write to the Audit_Log fails, THE originating service SHALL treat the mutation as failed and roll back the operation — order mutations SHALL NOT be committed without a corresponding audit entry.

---

### Requirement 20: Slot Filling for Commerce Intents

**User Story:** As a customer, I want the assistant to conversationally collect the information it needs to complete my purchase, so that I don't have to provide all details in a single message.

#### Acceptance Criteria

1. WHEN the Intent_Classifier classifies a commerce intent, THE ChatService SHALL extract the following slots from the conversation context: `product_id` (resolved via RAG_Pipeline), `quantity`, `shipping_address`, and `payment_method`.
2. IF one or more required slots are missing after initial classification, THEN THE ChatService SHALL re-prompt the customer with a targeted conversational question to collect each missing slot before proceeding.
3. THE LLM SHALL emit structured JSON via function-calling for all commerce intents — prose responses SHALL NOT be used to convey commerce intent payloads to downstream services.
4. WHEN a customer uses an ambiguous reference such as "the blue one" or "that item", THE Intent_Classifier SHALL resolve the reference to a `product_id` using the RAG_Pipeline context before emitting the structured intent payload.
5. THE ChatService SHALL validate that all required slots are populated and well-formed before forwarding a commerce intent to the UCP_Gateway_Service.
