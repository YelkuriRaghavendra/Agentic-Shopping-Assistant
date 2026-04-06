# Implementation Plan: In-Chat Payment Orders

## Overview

Wire together existing plumbing (Stripe PaymentIntent endpoint, BullMQ order pipeline, CommerceClient, CheckoutModal) into a cohesive in-chat payment and order-history experience. The work is additive: new components, type extensions, and small surgical edits to existing files.

## Tasks

- [x] 1. Add TypeScript type additions to `chat.types.ts`
  - Add `CartData` interface (mirrors `CheckoutData` but used for `view_cart` responses)
  - Add `OrderSummary` interface with `order_id`, `ucp_order_id?`, `status`, `totals`, `created_at`
  - Add `OrderHistoryData` interface with `orders: OrderSummary[]` and `next_cursor: string | null`
  - Extend `ChatMessageUI` with optional `cartData?: CartData` and `orderHistoryData?: OrderHistoryData`
  - _Requirements: 4.2, 4.3, 5.1, 5.2_

- [x] 2. Extend Python `ChatResponse` DTO and `ChatService` for `cart_data` and `order_history_data`
  - [x] 2.1 Add `cart_data: dict | None = None` and `order_history_data: dict | None = None` fields to `ChatResponse` in `backend/app/api/dto/chat_dto.py`
    - These fields flow through the existing SSE serialisation automatically
    - _Requirements: 4.2, 5.1_

  - [x] 2.2 Fix `view_cart` in `_dispatch_commerce_intent` (`chat_service.py`)
    - Replace the stub `CommerceResponse` with a real call to `self._commerce.get_checkout_session` using `checkout_session_id` from `session.context.get("cart", {}).get("checkout_session_id")`
    - If no active session exists, return a `CommerceResponse` with `data={"message": "empty_cart"}`
    - _Requirements: 4.2, 7.1_

  - [x] 2.3 Attach `cart_data` to the response in `_handle_commerce_intent` for `view_cart` intent
    - After `_dispatch_commerce_intent` returns for `view_cart`, build `cart_data` dict from `service_response.data` (same shape as `checkout_data`: `line_items`, `totals`, `checkout_session_id`)
    - Set `response.cart_data = cart_data`
    - _Requirements: 4.2, 4.3_

  - [x] 2.4 Attach `order_history_data` to the response in `_handle_commerce_intent` for `order_history` intent
    - After `_dispatch_commerce_intent` returns for `order_history`, set `response.order_history_data = {"orders": service_response.data.get("orders", []), "next_cursor": service_response.data.get("nextCursor")}`
    - When `orders` is empty, the existing `_format_commerce_response` message already handles the "no orders" case
    - _Requirements: 5.1, 5.5_

  - [x] 2.5 Fix `add_to_cart` in `_dispatch_commerce_intent` to reuse existing session
    - Check `session.context.get("cart", {}).get("checkout_session_id")` before deciding between `create_checkout_session` and `update_checkout_session`
    - If an active `checkout_session_id` exists in context, call `update_checkout_session`; otherwise call `create_checkout_session` and store the returned `sessionId` in `session.context["cart"]`
    - _Requirements: 4.1, 7.1, 7.2_

  - [ ]* 2.6 Write property test for `view_cart` → `get_checkout_session` routing (Property 14)
    - **Property 14: add_to_cart routes to correct CommerceClient method**
    - **Validates: Requirements 4.1**
    - Use `pytest` + `unittest.mock` to assert `create_checkout_session` called when no cart in context, `update_checkout_session` called when `checkout_session_id` present

  - [ ]* 2.7 Write property test for session reuse across cart intents (Property 21)
    - **Property 21: Active session is reused across cart intents**
    - **Validates: Requirements 7.1, 7.2**
    - Use `hypothesis` with `st.uuids()` for `checkout_session_id`; assert `create_checkout_session` never called when session context has active ID

- [x] 3. Verify and document `POST /commerce/checkout-sessions/:id/payment-intent` endpoint
  - Confirm `checkout.controller.ts` already exposes `POST :id/payment-intent` → `createOrGetPaymentIntent` (it does — no code change needed)
  - Confirm `checkout-order-service/.env` already has `STRIPE_SECRET_KEY` and `STRIPE_WEBHOOK_SECRET` placeholders (it does)
  - Add `NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY=pk_test_REPLACE_ME` to `Frontend/.env` if not present
  - Add `NEXT_PUBLIC_CHECKOUT_URL=http://localhost:3001` to `Frontend/.env` if not present
  - _Requirements: 2.1, 9.2, 9.4, 9.5_

- [x] 4. Refactor `CheckoutModal` to use Stripe Elements inline payment
  - [x] 4.1 Install / verify `@stripe/stripe-js` and `@stripe/react-stripe-js` in `Frontend/package.json`
    - These may already be present from the `stripe-payment-integration` spec; add if missing
    - _Requirements: 1.2_

  - [x] 4.2 Add `payment` step to `CheckoutModal` — replace redirect/polling with PaymentElement
    - Add `"payment"` to the `Step` union type
    - Remove the `"redirecting"` and `"awaiting"` steps (and their polling `useEffect`)
    - Add `clientSecret` and `paymentIntentId` to component state
    - Replace `proceedToPayment` (which called `/payment-link` and `window.open`) with `fetchPaymentIntent` that calls `POST ${baseUrl}/commerce/checkout-sessions/${checkout_session_id}/payment-intent` and transitions to `"payment"` step on success
    - _Requirements: 1.1, 1.8_

  - [x] 4.3 Render `<Elements>` + `<PaymentElement>` on the `payment` step
    - Initialise `stripePromise` once at module level using `NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY`
    - Apply dark-theme `appearance` object: `theme: "night"`, `colorPrimary: "#1D9E75"`, `colorBackground: "#0C0C0F"`, `colorText: "rgba(255,255,255,0.82)"`, `borderRadius: "12px"`
    - If `stripePromise` is `null`, render error state: "Payment is currently unavailable"
    - _Requirements: 1.2, 1.8, 8.1_

  - [x] 4.4 Implement `handlePaymentSubmit` inside the `payment` step
    - Call `stripe.confirmPayment({ elements, confirmParams: { return_url: window.location.href } })`
    - On success (no `error`): advance to `"success"` step, call `onComplete(orderConfirmation)`
    - On error: display `error.message` inline, stay on `"payment"` step, re-enable button
    - Disable submit button and show spinner while confirming (`isSubmitting` state)
    - _Requirements: 1.3, 1.4, 1.5, 1.6, 1.7_

  - [ ]* 4.5 Write property test: address submit calls `/payment-intent`, not `window.open` (Property 1)
    - **Property 1: Payment intent fetch replaces redirect**
    - **Validates: Requirements 1.1**
    - Use `fast-check` with `fc.record({ fullName: fc.string(), addressLine: fc.string(), city: fc.string(), pincode: fc.string() })` — assert `window.open` never called; `fetch` called with URL containing `/payment-intent`

  - [ ]* 4.6 Write property test: `confirmPayment` uses stored `clientSecret` (Property 2)
    - **Property 2: confirmPayment uses stored client_secret**
    - **Validates: Requirements 1.3**
    - Use `fc.string()` for `clientSecret`; mock `stripe.confirmPayment`; assert called with matching secret

  - [ ]* 4.7 Write property test: successful payment advances to success step (Property 3)
    - **Property 3: Successful payment advances to success step**
    - **Validates: Requirements 1.4**
    - Mock `confirmPayment` to resolve without error; assert step becomes `"success"` and no `window.location` navigation

  - [ ]* 4.8 Write property test: payment error stays on payment step (Property 4)
    - **Property 4: Payment error stays on payment step**
    - **Validates: Requirements 1.5**
    - Use `fc.string()` for error message; mock `confirmPayment` to return `{ error: { message } }`; assert step remains `"payment"` and error text rendered

  - [ ]* 4.9 Write property test: submit button disabled while confirming (Property 5)
    - **Property 5: Submit button disabled while confirming**
    - **Validates: Requirements 1.6**
    - Assert `disabled = true` on submit button while `handlePaymentSubmit` is in-flight

  - [ ]* 4.10 Write property test: no raw card data sent to backend (Property 6)
    - **Property 6: No raw card data sent to backend**
    - **Validates: Requirements 1.7**
    - Intercept all `fetch` calls; assert none contain `cardNumber`, `expiry`, or `cvv` fields

- [x] 5. Checkpoint — Ensure all CheckoutModal tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 6. Create `CartPanel` component (`Frontend/components/CartPanel.tsx`)
  - [x] 6.1 Implement `CartPanel` component
    - Props: `cartData: CartData`, `onCheckout: () => void`
    - Render list of line items: product title, quantity, unit price in INR (`₹X.XX`)
    - Render running subtotal: `sum(item.price × quantity) / 100` formatted as `₹X.XX`
    - Render "Checkout" button that calls `onCheckout()`
    - Apply design tokens: background `#111116`, border `rgba(255,255,255,0.07)`, border-radius `8px`, teal `#1D9E75`, Josefin Sans headings, Inter body
    - _Requirements: 4.3, 4.6, 4.8, 8.2, 8.4_

  - [ ]* 6.2 Write property test: CartPanel subtotal equals sum of line item prices (Property 15)
    - **Property 15: CartPanel subtotal equals sum of line item prices**
    - **Validates: Requirements 4.6**
    - Use `fc.array(fc.record({ price: fc.integer({ min: 1, max: 1_000_000 }), quantity: fc.integer({ min: 1, max: 99 }) }), { minLength: 1 })` — assert displayed subtotal equals `sum(price × quantity) / 100`

- [x] 7. Create `OrderHistoryPanel` component (`Frontend/components/OrderHistoryPanel.tsx`)
  - [x] 7.1 Implement `OrderHistoryPanel` component
    - Props: `data: OrderHistoryData`, `onLoadMore?: (cursor: string) => void`
    - Render each order as a row: truncated `order_id`, status badge, grand total in INR, `created_at` date
    - Status badge colors: teal `#1D9E75` for `processing`/`fulfilled`; red `#f87171` for `cancelled`/`payment_failed`
    - Show "Load more" button when `data.next_cursor` is present; call `onLoadMore(next_cursor)` on click
    - Apply design tokens: background `#0C0C0F`, border `0.5px solid rgba(255,255,255,0.08)`
    - _Requirements: 5.4, 5.7, 8.3, 8.4_

  - [ ]* 7.2 Write property test: OrderHistoryPanel renders orders in descending date order (Property 18)
    - **Property 18: OrderHistoryPanel orders are in descending date order**
    - **Validates: Requirements 5.4**
    - Use `fc.array(fc.record({ order_id: fc.uuid(), created_at: fc.date(), status: fc.constant("processing"), totals: fc.record({ grand_total_cents: fc.integer({ min: 1 }) }) }), { minLength: 2 })` — assert rendered rows match descending sort by `created_at`

  - [ ]* 7.3 Write property test: OrderConfirmationCard renders all required fields (Property 20)
    - **Property 20: OrderConfirmationCard renders all required fields**
    - **Validates: Requirements 6.3**
    - Use `fc.record(...)` for `OrderConfirmation`; assert rendered output contains `order_id`, all item titles, grand total, status badge

- [x] 8. Wire cart/orders drawers into `ChatWindow` and SSE data into `useChat.ts`
  - [x] 8.1 Add cart icon and orders icon to the `ChatWindow` header (top-right)
    - Add `cartData: CartData | null`, `orderHistoryData: OrderHistoryData | null`, `cartOpen: boolean`, `ordersOpen: boolean` to `ChatWindow` state
    - Render a cart icon button and an orders icon button in the header's right side
    - Cart icon shows a teal badge with item count when `cartData` has line items; icon color turns `#1D9E75` when count > 0
    - Orders icon shows a teal badge with order count when `orderHistoryData` has orders
    - Clicking either icon toggles the respective drawer open/closed
    - _Requirements: 4.4, 5.3, 8.7_

  - [x] 8.2 Implement `CartDrawer` and `OrdersDrawer` slide-in panels in `ChatWindow`
    - Render both drawers as absolutely-positioned overlays inside the chat container (right side, full height)
    - Width `320px`, background `#0C0C0F`, left border `0.5px solid rgba(255,255,255,0.08)`
    - Animate with `transform: translateX(0)` / `translateX(100%)` transition
    - Each drawer has a close button (`×`) in its top-right corner
    - `CartDrawer` renders `<CartPanel>` with an `onCheckout` handler that closes the drawer and opens `CheckoutModal`
    - `OrdersDrawer` renders `<OrderHistoryPanel>`
    - _Requirements: 4.5, 5.4, 8.6_

  - [x] 8.3 Wire `cart_data` and `order_history_data` from SSE `done` event into `useChat.ts`
    - In both `sendMessage` and `streamRequest` SSE `done` handlers, extract `event.cart_data` and `event.order_history_data` alongside the existing `event.checkout_data`
    - Map them onto the bot `ChatMessageUI` as `cartData` and `orderHistoryData`
    - _Requirements: 4.3, 5.2_

  - [x] 8.4 Auto-open drawers when SSE data arrives in `ChatWindow`
    - In `ChatWindow`, watch for new messages with `cartData` set — call `setCartData` and `setCartOpen(true)`
    - Watch for new messages with `orderHistoryData` set — call `setOrderHistoryData` and `setOrdersOpen(true)`
    - Only auto-open `OrdersDrawer` when `orderHistoryData.orders.length > 0` (Requirement 5.6)
    - _Requirements: 4.3, 5.2, 5.6_

  - [x] 8.5 Wire `CartDrawer` checkout button through `ChatWindow` to `CheckoutModal`
    - The `CartDrawer`'s `onCheckout` handler sets `checkoutData` from `cartData` (same shape) and opens `CheckoutModal`
    - `CartData` and `CheckoutData` share the same shape — cast or alias as needed
    - _Requirements: 4.5_

  - [ ]* 8.6 Write property test: `onComplete` called on success and `OrderConfirmationCard` appended (Property 19)
    - **Property 19: Successful payment triggers onComplete and OrderConfirmationCard**
    - **Validates: Requirements 6.1, 6.2**
    - Mock `confirmPayment` to resolve without error; assert `onComplete` called with valid `OrderConfirmation`; assert `addOrderConfirmation` appends a message with `orderConfirmation` set

- [x] 9. Checkpoint — Ensure all frontend component tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 10. Backend property tests for `checkout-order-service` (Jest + fast-check)
  - [ ]* 10.1 Write property test: PaymentIntent creation is idempotent (Property 7)
    - **Property 7: PaymentIntent creation is idempotent**
    - **Validates: Requirements 2.1**
    - Use `fc.uuid()` for `sessionId`; pre-seed session with existing `stripePaymentIntentId`; assert second call returns same `client_secret`; `stripe.paymentIntents.create` called at most once

  - [ ]* 10.2 Write property test: PaymentIntent fields are persisted round-trip (Property 8)
    - **Property 8: PaymentIntent fields are persisted (round-trip)**
    - **Validates: Requirements 2.2**
    - Use `fc.uuid()` for `sessionId`; after `createOrGetPaymentIntent`, assert `repo.findOne` returns session with `stripePaymentIntentId` and `stripeClientSecret` matching returned values

  - [ ]* 10.3 Write property test: PAYMENT_FAILED sessions allow retry (Property 9)
    - **Property 9: PAYMENT_FAILED sessions allow retry**
    - **Validates: Requirements 2.5**
    - Use `fc.uuid()` for `sessionId`; pre-set session `ucpStatus` to `PAYMENT_FAILED`; assert `createOrGetPaymentIntent` resolves without throwing

  - [ ]* 10.4 Write property test: `payment_intent.succeeded` marks session COMPLETED and enqueues order (Property 10)
    - **Property 10: payment_intent.succeeded marks session COMPLETED and enqueues order**
    - **Validates: Requirements 3.1**
    - Use `fc.string()` for `paymentIntentId`; assert session `ucpStatus` becomes `COMPLETED`; assert `queue.add` called exactly once with `order.confirmed`

  - [ ]* 10.5 Write property test: `order.confirmed` event creates Order record (Property 11)
    - **Property 11: order.confirmed event creates Order record**
    - **Validates: Requirements 3.2**
    - Use `fc.record({ customerId: fc.uuid(), lineItems: fc.array(...), totals: fc.record(...) })` for event payload; assert `orders.orders` INSERT with `status = "processing"` and correct fields

  - [ ]* 10.6 Write property test: `payment_intent.payment_failed` marks session PAYMENT_FAILED (Property 12)
    - **Property 12: payment_intent.payment_failed marks session PAYMENT_FAILED**
    - **Validates: Requirements 3.3**
    - Use `fc.string()` for `paymentIntentId`; assert session `ucpStatus` becomes `PAYMENT_FAILED`

  - [ ]* 10.7 Write property test: webhook signature verified before business logic (Property 13)
    - **Property 13: Webhook signature verified before business logic**
    - **Validates: Requirements 3.4**
    - Assert `stripe.webhooks.constructEvent` called before any `repo.save` or `queue.add`; requests with invalid signatures return HTTP 400

  - [ ]* 10.8 Write property test: order history scoped to authenticated customer (Property 17)
    - **Property 17: order_history scoped to authenticated customer**
    - **Validates: Requirements 5.4**
    - Use `fc.uuid()` for `customerId`; assert all returned orders have `customerId` equal to the queried value

  - [ ]* 10.9 Write property test: `/complete` endpoint accepts both payload types (Property 22)
    - **Property 22: /complete endpoint accepts both payload types (backward compat)**
    - **Validates: Requirements 10.3**
    - Use `fc.oneof(fc.record({ type: fc.constant("stripe"), payment_intent_id: fc.string() }), fc.record({ type: fc.constant("card"), last4: fc.string() }))` — assert HTTP 200 for both

- [ ] 11. Add e2e test for full webhook ingestion path
  - [ ]* 11.1 Create `checkout-order-service/test/in-chat-payment.e2e-spec.ts`
    - Mock Stripe SDK; POST a `payment_intent.succeeded` webhook with valid signature
    - Assert session `ucpStatus` transitions to `COMPLETED`
    - Assert `order.confirmed` job enqueued in `order-events` queue
    - _Requirements: 3.1, 3.4_

- [x] 12. Final checkpoint — Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for a faster MVP
- Properties 3, 5, 14, 16, 21 are covered by unit tests in tasks 4 and 2 respectively; dedicated property tests are marked optional
- The `checkout-order-service` payment-intent endpoint (`POST :id/payment-intent`) already exists — task 3 is verification only
- `CartData` and `CheckoutData` are intentionally the same shape; `cartData` is used for `view_cart` panel rendering while `checkoutData` is used for direct checkout-initiate modal opening
- All property tests must include the comment tag: `// Feature: in-chat-payment-orders, Property <N>: <property_text>`
