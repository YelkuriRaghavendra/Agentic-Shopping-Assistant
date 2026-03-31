# Bug Requirements: UCP Checkout Integration

## Overview

These bugs were identified during local integration testing of the Universal Commerce Protocol (UCP) checkout flow across all four services: Frontend (Next.js), Backend (Python/FastAPI), checkout-order-service (NestJS), and rag-service.

---

## Bug 1: Commerce intents blocked by LaunchDarkly feature flag in local dev

**Symptom:** All checkout and order messages return "This feature is currently unavailable."

**Root Cause:** `FeatureFlagService.is_intent_enabled()` defaults to `False` when LaunchDarkly SDK key is not configured. The `LAUNCHDARKLY_SDK_KEY` was set to `change-me-in-prod` in local dev.

**Fix:** Added `FEATURE_FLAG_FORCE_ENABLE=true` env var to `backend/.env` and a bypass check in `FeatureFlagService.is_intent_enabled()`. Also added `FEATURE_FLAG_FORCE_ENABLE` as a proper field in the Pydantic `Settings` model to avoid `extra_forbidden` validation error.

---

## Bug 2: `GET /commerce/orders` returns 404 due to doubled global prefix

**Symptom:** `GET http://localhost:3001/commerce/orders` → 404 Not Found

**Root Cause:** `main.ts` called `app.setGlobalPrefix('commerce')` while all controllers already had `commerce/` in their `@Controller()` decorator. This doubled the prefix to `/commerce/commerce/orders`.

**Fix:** Removed `app.setGlobalPrefix()` from `main.ts`.

---

## Bug 3: `GET /commerce/orders` returns 400 — snake_case vs camelCase mismatch

**Symptom:** `{"message":["property customer_id should not exist","customerId should not be empty"]}`

**Root Cause:** Python backend sends `customer_id` (snake_case) but NestJS `OrderQueryDto` expects `customerId` (camelCase). The global `ValidationPipe` with `forbidNonWhitelisted: true` rejects unknown properties.

**Fix:** Updated `OrderQueryDto` to accept both `customer_id` and `customerId` via `@Transform`. Also updated `CommerceClient` in Python to send `customerId` (camelCase) for all order endpoints.

---

## Bug 4: TypeORM column name mismatch — `orderId` vs `order_id`

**Symptom:** `QueryFailedError: column order.orderId does not exist`

**Root Cause:** TypeORM entity properties used camelCase (`orderId`, `customerId`, etc.) without explicit `name` options. The DB columns created by migrations use snake_case (`order_id`, `customer_id`). TypeORM defaults to using the property name as the column name.

**Fix:** Added explicit `name` options to all `@Column()`, `@PrimaryGeneratedColumn()`, `@CreateDateColumn()`, and `@UpdateDateColumn()` decorators in all four entities: `Order`, `OrderStatusHistory`, `CheckoutSession`, `WebhookEvent`.

---

## Bug 5: `POST /commerce/checkout/sessions` returns 400 — missing `merchant_id` and empty `line_items`

**Symptom:** `{"message":["merchant_id should not be empty","line_items must contain at least 1 elements"]}`

**Root Cause (merchant_id):** Python backend never sends `merchant_id` — it's not part of the commerce slot extraction. The NestJS DTO required it.

**Root Cause (line_items):** When `checkout_initiate` is triggered from a product message, `line_items` was built with `price: 0` which fails the `@IsPositive()` validator.

**Fix:** Made `merchant_id` optional in `CreateCheckoutSessionDto` with a fallback to `DEFAULT_MERCHANT_ID` env var. Changed `price` placeholder to `1` (minimum positive value).

---

## Bug 6: `cancelSession` calls UCP even in `SKIP_UCP_OUTBOUND=true` mode

**Symptom:** Cancel session fails in local dev because it tries to call a non-existent UCP merchant endpoint.

**Root Cause:** `cancelSession()` in `CheckoutSessionService` always called `ucpCheckoutClient.cancelCheckoutSession()` regardless of `SKIP_UCP_OUTBOUND`.

**Fix:** Added `SKIP_UCP_OUTBOUND` check to `cancelSession()` — skips the UCP call in local dev mode.

---

## Bug 7: Checkout summary page uses relative URL for complete API call

**Symptom:** When the checkout summary page is opened as a `continue_url` in a new tab/window, the `fetch('/commerce/checkout-sessions/:id/complete')` call fails because the relative URL resolves to the frontend origin (port 4001) instead of the checkout service (port 3001).

**Root Cause:** The HTML page served by `GET /commerce/checkout-sessions/:id/summary` used a hardcoded relative path `/commerce/checkout-sessions/${id}/complete` in its JavaScript.

**Fix:** Changed to use `window.location.origin` to build the absolute URL dynamically. Added `postMessage` to notify the parent chat window when checkout completes.

---

## Bug 8: Dummy environment variables causing startup failures and silent errors

**Symptom:** Multiple services fail to start or silently fail due to placeholder values like `change-me-in-prod` in env vars that are read at startup.

**Root Cause:** The `.env` files contained many unused or placeholder variables (Vault, LaunchDarkly, UCP OAuth, HMAC secrets) that were copied from a template but never configured.

**Fix:** Cleaned all four `.env` files to contain only variables that are actually used. Removed: `VAULT_*`, `UCP_OAUTH_*`, `UCP_API_KEY`, `UCP_BASE_URL`, `UCP_WELL_KNOWN_URL`, `WEBHOOK_HMAC_SECRET`, `LAUNCHDARKLY_SDK_KEY`, `FEATURE_FLAG_DEFAULT_DISABLED`, `IDEMPOTENCY_TTL_SECONDS`, `TOKEN_REFRESH_BUFFER_SECONDS`, `CHECKOUT_PAYMENT_TIMEOUT_MINUTES`, `CART_TTL_MINUTES`, `RAG_ORDER_SOURCE_ID`, `COMMERCE_SERVICE_URL` (from rag-service — unused).
