# Bug Fix Tasks: UCP Checkout Integration

## Status Key
- `[x]` = Fixed
- `[ ]` = Pending
- `[-]` = In progress

---

## Tasks

- [x] Bug 1: Commerce intents blocked by LaunchDarkly in local dev
  - [x] Add `FEATURE_FLAG_FORCE_ENABLE` field to Pydantic `Settings` model in `backend/app/core/config.py`
  - [x] Add bypass check in `FeatureFlagService.is_intent_enabled()` using `get_settings().FEATURE_FLAG_FORCE_ENABLE`
  - [x] Set `FEATURE_FLAG_FORCE_ENABLE=true` in `backend/.env`

- [x] Bug 2: Doubled global prefix causing 404 on all commerce routes
  - [x] Remove `app.setGlobalPrefix('commerce')` from `checkout-order-service/src/main.ts`

- [x] Bug 3: snake_case vs camelCase mismatch on `customer_id` query param
  - [x] Update `OrderQueryDto` to accept both `customer_id` and `customerId` via `@Transform`
  - [x] Update `CommerceClient` (Python) to send `customerId` for `list_orders`, `get_order`, `cancel_order`, `request_return`

- [x] Bug 4: TypeORM column name mismatch (camelCase property vs snake_case DB column)
  - [x] Add explicit `name` options to all columns in `Order` entity
  - [x] Add explicit `name` options to all columns in `OrderStatusHistory` entity
  - [x] Add explicit `name` options to all columns in `CheckoutSession` entity
  - [x] Add explicit `name` options to all columns in `WebhookEvent` entity

- [x] Bug 5: Missing `merchant_id` and invalid `price: 0` in checkout session creation
  - [x] Make `merchant_id` optional in `CreateCheckoutSessionDto`
  - [x] Add `DEFAULT_MERCHANT_ID` fallback in `CheckoutController.createSession()`
  - [x] Change `price` placeholder from `0` to `1` in Python `_dispatch_commerce_intent`

- [x] Bug 6: `cancelSession` calls UCP in `SKIP_UCP_OUTBOUND=true` mode
  - [x] Add `SKIP_UCP_OUTBOUND` guard to `CheckoutSessionService.cancelSession()`

- [x] Bug 7: Checkout summary page uses relative URL for complete API call
  - [x] Change JavaScript in summary HTML to use `window.location.origin` for absolute URL
  - [x] Add `postMessage` to notify parent chat window on checkout completion

- [x] Bug 8: Dirty env files with unused dummy variables
  - [x] Clean `checkout-order-service/.env` — remove Vault, LaunchDarkly, UCP OAuth, HMAC, FSM, idempotency vars
  - [x] Clean `backend/.env` — remove unused vars, keep only what's read by `Settings` model
  - [x] Clean `rag-service/.env` — remove unused COMMERCE_SERVICE_URL, RAG_ORDER_SOURCE_ID
  - [x] Create `Frontend/.env.local` with `NEXT_PUBLIC_API_BASE_URL`, `NEXT_PUBLIC_COMMERCE_BASE_URL`, `NEXT_PUBLIC_CHECKOUT_URL`

- [ ] Bug 9: Commerce intent keyword matching too narrow — natural language checkout phrases not detected
  - [x] Expand `_COMMERCE_INTENT_MAP` in `backend/app/services/chat_service.py` to include "I want to buy", "place the order", "buy this", etc.
  - [ ] Add integration test to verify keyword matching for common checkout phrases

- [x] Bug 10: `updateSession` calls UCP even in `SKIP_UCP_OUTBOUND=true` mode
  - [x] Add `SKIP_UCP_OUTBOUND` guard to `CheckoutSessionService.updateSession()` — return local session with updated line items without calling UCP

- [x] Bug 11: `CheckoutModal` does not handle CORS when calling checkout service directly from browser
  - [x] Verify NestJS CORS config allows requests from `http://localhost:4001` (Frontend dev port)
  - [x] Add CORS configuration to `checkout-order-service/src/main.ts` if missing

- [x] Bug 12: `orderOrderId` column error when inserting `OrderStatusHistory`
  - [x] Remove duplicate `@Column orderId` from `OrderStatusHistory` entity
  - [x] Add `@JoinColumn({ name: 'order_id' })` to `@ManyToOne` relation
  - [x] Add `@RelationId` decorator for read access to `orderId`
  - [x] Update `OrderService.createFromConfirmedEvent()` to use `order: savedOrder` instead of `orderId`
  - [x] Update `OrderService.cancelOrder()` to use `order: { orderId }` instead of `orderId`
  - [x] Update `OrderService.returnOrder()` to use `order: { orderId }` instead of `orderId`
  - [x] Update `WebhookIngestionConsumer` to use `order: { orderId }` instead of `orderId`
