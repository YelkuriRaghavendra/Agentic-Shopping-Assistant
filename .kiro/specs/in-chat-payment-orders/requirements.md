# Requirements Document

## Introduction

This feature extends the Vikrai conversational shopping assistant with two capabilities:

1. **Embedded Stripe payment** — instead of redirecting the user to a new browser tab for payment, the Stripe PaymentElement is rendered directly inside the chat's CheckoutModal. The user completes payment without ever leaving the chat interface.

2. **In-chat cart management and order history** — users can add products to a persistent cart from the chat, and view their cart or order history via dedicated panels accessible from the chat header. A cart icon and an orders icon appear in the top-right corner of the chat header; clicking either opens a slide-in side panel. When the backend returns `cart_data` or `order_history_data` in the SSE response, the relevant panel auto-opens and the icon shows a badge count. Every completed order is stored in the `orders.orders` database table and is queryable by the customer.

The existing codebase already has: a `CheckoutModal` that opens a Stripe Payment Link in a new tab, a `checkout-order-service` (NestJS) with `createOrGetPaymentIntent` and `handlePaymentSucceeded` methods, an `orders.orders` PostgreSQL table, and a `CommerceClient` in the Python backend that routes commerce intents. This feature builds on all of that without breaking existing behaviour.

Branding must follow the existing Vikrai design tokens: background `#080809` / `#0C0C0F`, primary teal `#1D9E75`, font families `Josefin Sans`, `Inter`, and `JetBrains Mono`.

---

## Glossary

- **CheckoutModal**: The existing Next.js React component (`Frontend/components/CheckoutModal.tsx`) that presents the multi-step checkout UI inside the chat.
- **CartPanel**: A new React component rendered in a slide-in side panel (accessible via a cart icon in the chat header) that shows the current cart contents, item quantities, subtotal, and a checkout button.
- **OrderHistoryPanel**: A new React component rendered in a slide-in side panel (accessible via an orders icon in the chat header) that shows a paginated list of the customer's past orders.
- **CartDrawer**: The slide-in panel container that hosts `CartPanel`, toggled by the cart icon in the chat header.
- **OrdersDrawer**: The slide-in panel container that hosts `OrderHistoryPanel`, toggled by the orders icon in the chat header.
- **Stripe_Elements**: The `@stripe/react-stripe-js` library that renders a PCI-compliant `PaymentElement` inside the CheckoutModal.
- **PaymentIntent**: A Stripe object (`pi_*`) representing a payment attempt, created by `checkout-order-service` via `createOrGetPaymentIntent`.
- **CheckoutSession**: The TypeORM entity in `checkout.checkout_sessions` representing one checkout attempt, already storing `stripePaymentIntentId` and `stripeClientSecret`.
- **Order**: The TypeORM entity in `orders.orders` created after a successful Stripe payment via the `order.confirmed` BullMQ event.
- **Order_Events_Queue**: The BullMQ queue (`order-events`) to which `order.confirmed` events are published after payment succeeds.
- **CommerceClient**: The Python HTTP client (`backend/app/clients/commerce_client.py`) that calls `checkout-order-service` on behalf of the chat backend.
- **Intent_Classifier**: The keyword-based classifier in `backend/app/services/chat_service.py` that maps user messages to commerce intents (`add_to_cart`, `view_cart`, `checkout_initiate`, `order_history`, etc.).
- **ChatService**: The Python orchestrator (`backend/app/services/chat_service.py`) that routes commerce intents to `CommerceClient`.
- **Stripe_Webhook_Secret**: The `whsec_*` signing secret used to verify that incoming webhook payloads originate from Stripe.
- **Payment_Link**: The existing Stripe Payment Link flow (opens a new tab) — this is replaced by Stripe Elements in this feature.

---

## Requirements

### Requirement 1: Embedded Stripe Payment Inside Chat

**User Story:** As a shopper, I want to complete my Stripe payment directly inside the chat without being redirected to a new browser tab, so that my shopping experience stays seamless and uninterrupted.

#### Acceptance Criteria

1. WHEN the user clicks "Continue to Payment" in the CheckoutModal, THE CheckoutModal SHALL call `POST /commerce/checkout-sessions/:id/payment-intent` to obtain a `client_secret` and render a Stripe `PaymentElement` inside the modal — no new browser tab SHALL be opened.
2. WHEN the `client_secret` is received, THE CheckoutModal SHALL render the Stripe `PaymentElement` using the `@stripe/react-stripe-js` library, styled to match the Vikrai dark theme (background `#0C0C0F`, text `rgba(255,255,255,0.82)`, accent `#1D9E75`).
3. WHEN the user submits the payment form, THE CheckoutModal SHALL call `stripe.confirmPayment` with the stored `client_secret` and a `return_url` pointing to the current page.
4. WHEN `stripe.confirmPayment` resolves without error, THE CheckoutModal SHALL advance to the `success` step inline — no page navigation SHALL occur.
5. IF `stripe.confirmPayment` returns an error, THEN THE CheckoutModal SHALL display the Stripe error message inline on the payment step and allow the user to retry without closing the modal.
6. WHILE the payment confirmation is in progress, THE CheckoutModal SHALL display a loading spinner and disable the submit button to prevent duplicate submissions.
7. THE CheckoutModal SHALL NOT transmit raw card numbers, expiry dates, or CVV values to any backend endpoint.
8. IF `NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY` is absent, THEN THE CheckoutModal SHALL render an error state on the payment step indicating that payment is currently unavailable.

---

### Requirement 2: Stripe PaymentIntent Endpoint (checkout-order-service)

**User Story:** As the frontend, I want to request a Stripe PaymentIntent for a checkout session, so that I can render Stripe Elements for secure card capture.

#### Acceptance Criteria

1. WHEN a `POST /commerce/checkout-sessions/:id/payment-intent` request is received, THE CheckoutSessionService SHALL return `{ client_secret, payment_intent_id }` — creating a new Stripe PaymentIntent if one does not already exist, or returning the cached one if it does.
2. THE CheckoutSessionService SHALL persist `stripePaymentIntentId` and `stripeClientSecret` on the `CheckoutSession` entity before returning the response, so that subsequent calls are idempotent.
3. IF the checkout session does not exist, THEN THE CheckoutController SHALL respond with HTTP 404.
4. IF the checkout session has status `CANCELED`, THEN THE CheckoutController SHALL respond with HTTP 422.
5. WHILE a session has status `PAYMENT_FAILED`, THE CheckoutSessionService SHALL allow a new PaymentIntent to be created for the same session, enabling the user to retry payment.

---

### Requirement 3: Stripe Webhook Drives Order Creation

**User Story:** As a platform operator, I want a successful Stripe payment to automatically create an order record in the database, so that every completed purchase is persisted without manual intervention.

#### Acceptance Criteria

1. WHEN a verified `payment_intent.succeeded` webhook event is received at `POST /stripe/webhooks`, THE CheckoutSessionService SHALL set the matching session's `ucpStatus` to `COMPLETED`, assign a `ucpOrderId`, and publish an `order.confirmed` event to the `Order_Events_Queue`.
2. WHEN the `order.confirmed` event is consumed from the `Order_Events_Queue`, THE OrderService SHALL create an `Order` record in `orders.orders` with `status = processing`, the customer ID, line items, and totals from the checkout session.
3. WHEN a verified `payment_intent.payment_failed` webhook event is received, THE CheckoutSessionService SHALL set the matching session's `ucpStatus` to `PAYMENT_FAILED` and log the failure reason.
4. THE Webhook_Controller SHALL verify the `Stripe-Signature` header using `stripe.webhooks.constructEvent` before executing any business logic — unverified requests SHALL be rejected with HTTP 400.
5. THE Webhook_Controller SHALL respond with HTTP 200 to all successfully verified events within 2 seconds, deferring processing to the async queue.

---

### Requirement 4: In-Chat Cart Management

**User Story:** As a shopper, I want to add products to a cart and manage it within the chat, so that I can build my order conversationally before checking out.

#### Acceptance Criteria

1. WHEN the Intent_Classifier detects an `add_to_cart` intent, THE ChatService SHALL call `CommerceClient.create_checkout_session` (if no active session exists) or `CommerceClient.update_checkout_session` (if one does) with the resolved product line item, and return a confirmation message to the user.
2. WHEN the Intent_Classifier detects a `view_cart` intent, THE ChatService SHALL return the current cart contents — product names, quantities, unit prices, and subtotal — as a structured `cart_data` payload in the SSE `done` event.
3. WHEN the Frontend receives a message with `cart_data` in the SSE `done` event, THE ChatWindow SHALL store the cart data in state, update the cart icon badge count in the header, and auto-open the `CartDrawer` side panel.
4. THE chat header SHALL display a cart icon in the top-right corner showing a badge with the number of line items currently in the cart. Clicking the icon SHALL toggle the `CartDrawer` open or closed.
5. THE `CartDrawer` SHALL render a `CartPanel` showing the cart items, quantities, unit prices, running subtotal, and a "Checkout" button. Clicking "Checkout" SHALL close the drawer and open the `CheckoutModal` pre-populated with the cart's line items and totals.
6. WHILE a cart has at least one item, THE CartPanel SHALL display a running subtotal in INR (₹), calculated as the sum of `item.price × quantity` for all line items.
7. IF a product is added to the cart and the checkout-order-service returns an `out_of_stock` error, THEN THE ChatService SHALL return a message informing the user that the item is out of stock and the cart SHALL remain unchanged.
8. THE CartPanel SHALL use the Vikrai design tokens: dark surface `#111116`, teal accent `#1D9E75`, Josefin Sans for headings, Inter for body text.

---

### Requirement 5: Order History in Chat

**User Story:** As a shopper, I want to view my past orders directly in the chat, so that I can track what I've purchased without leaving the conversation.

#### Acceptance Criteria

1. WHEN the Intent_Classifier detects an `order_history` intent, THE ChatService SHALL call `CommerceClient.list_orders` with the authenticated `customer_id` and return the results as a structured `order_history_data` payload in the SSE `done` event.
2. WHEN the Frontend receives a message with `order_history_data` in the SSE `done` event, THE ChatWindow SHALL store the order history data in state, update the orders icon badge count in the header, and auto-open the `OrdersDrawer` side panel.
3. THE chat header SHALL display an orders icon in the top-right corner. Clicking the icon SHALL toggle the `OrdersDrawer` open or closed.
4. THE `OrdersDrawer` SHALL render an `OrderHistoryPanel` showing each order's ID (truncated), status badge, grand total in INR, and creation date, in descending creation-date order, with a "Load more" option when `nextCursor` is present.
5. THE Order_Service SHALL scope all order history queries to the authenticated `customer_id` — THE Order_Service SHALL NOT return orders belonging to a different customer.
6. WHEN an `order_history` query returns zero orders, THE ChatService SHALL return a message informing the user that no orders have been placed yet, and the `OrdersDrawer` SHALL NOT auto-open.
7. THE OrderHistoryPanel SHALL use the Vikrai design tokens: dark surface `#111116`, teal accent `#1D9E75`, status badges using teal for `processing`/`fulfilled` and red (`#f87171`) for `cancelled`/`payment_failed`.

---

### Requirement 6: Order Confirmation in Chat

**User Story:** As a shopper, I want to see an order confirmation card in the chat immediately after my payment succeeds, so that I have immediate visual confirmation of my purchase.

#### Acceptance Criteria

1. WHEN the CheckoutModal advances to the `success` step, THE CheckoutModal SHALL call `onComplete` with an `OrderConfirmation` object containing `order_id`, `line_items`, `totals`, and `status: "processing"`.
2. WHEN `onComplete` is called with an `OrderConfirmation`, THE ChatWindow SHALL call `addOrderConfirmation` to append an `OrderConfirmationCard` message to the chat feed.
3. THE OrderConfirmationCard SHALL display: order ID, list of purchased items with quantities and prices, grand total in INR, and a status badge.
4. THE OrderConfirmationCard SHALL use the Vikrai design tokens consistent with the existing `Frontend/components/OrderConfirmationCard.tsx` component.

---

### Requirement 7: Cart State Persistence Across Chat Turns

**User Story:** As a shopper, I want my cart to persist across multiple chat messages within a session, so that I can continue browsing and adding items without losing my selections.

#### Acceptance Criteria

1. WHILE a `CheckoutSession` exists in `checkout.checkout_sessions` with `ucpStatus` not equal to `completed` or `canceled`, THE ChatService SHALL reuse the existing session when processing subsequent `add_to_cart` or `view_cart` intents for the same customer.
2. THE ChatService SHALL store the active `checkout_session_id` in the session context (`sessions.context` JSONB column) so that it survives across chat turns.
3. WHEN a customer starts a new chat session, THE ChatService SHALL check for an existing incomplete `CheckoutSession` for that customer and resume it rather than creating a duplicate.
4. IF a `CheckoutSession` has `ucpStatus = completed` or `canceled`, THEN THE ChatService SHALL create a new `CheckoutSession` for subsequent `add_to_cart` intents.

---

### Requirement 8: Branding and Visual Consistency

**User Story:** As a product designer, I want all new UI components to use the existing Vikrai design tokens, so that the payment and order history experience feels native to the chat interface.

#### Acceptance Criteria

1. THE CheckoutModal payment step SHALL apply Stripe Elements appearance options: `theme: "night"`, `variables.colorPrimary: "#1D9E75"`, `variables.colorBackground: "#0C0C0F"`, `variables.colorText: "rgba(255,255,255,0.82)"`, `variables.borderRadius: "12px"`.
2. THE CartPanel SHALL use the same card style as `ProductSlider` cards: background `#111116`, border `rgba(255,255,255,0.07)`, border-radius `8px`.
3. THE OrderHistoryPanel SHALL use the same surface style as the CheckoutModal: background `#0C0C0F`, border `0.5px solid rgba(255,255,255,0.08)`.
4. ALL new buttons SHALL follow the existing CTA pattern: background `#1D9E75`, color `#000`, font `Josefin Sans Bold`, uppercase, letter-spacing `2px`, border-radius `4px`.
5. THE Vikrai logo mark (green dot + "Vik" + "rai" wordmark) SHALL appear in the header of the CheckoutModal payment step, consistent with the existing address and success steps.
6. THE `CartDrawer` and `OrdersDrawer` SHALL slide in from the right side of the chat window, overlaying the message feed without pushing it. They SHALL have background `#0C0C0F`, a left border `0.5px solid rgba(255,255,255,0.08)`, and a close button in the top-right corner.
7. THE cart icon and orders icon in the chat header SHALL use the teal accent `#1D9E75` for the badge indicator. The icons SHALL be visible but unobtrusive — icon color `rgba(255,255,255,0.5)`, turning `#1D9E75` when the badge count is non-zero.

---

### Requirement 9: Environment Configuration

**User Story:** As a developer, I want all Stripe credentials to be supplied via environment variables, so that sandbox and production keys can be swapped without code changes.

#### Acceptance Criteria

1. THE checkout-order-service SHALL read `STRIPE_SECRET_KEY` and `STRIPE_WEBHOOK_SECRET` from environment variables — the service SHALL refuse to start if `STRIPE_SECRET_KEY` is absent.
2. THE Frontend SHALL read `NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY` from environment variables.
3. IF `NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY` is absent, THEN THE CheckoutModal SHALL render an error state on the payment step.
4. THE checkout-order-service `.env` file SHALL include placeholder entries for `STRIPE_SECRET_KEY` and `STRIPE_WEBHOOK_SECRET`.
5. THE Frontend `.env` file SHALL include a placeholder entry for `NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY`.

---

### Requirement 10: Backward Compatibility

**User Story:** As a developer, I want the new embedded payment flow to coexist with the existing SKIP_UCP_OUTBOUND dev mode, so that the service can still be run without Stripe credentials during non-payment development.

#### Acceptance Criteria

1. WHILE `SKIP_UCP_OUTBOUND=true` AND `STRIPE_SECRET_KEY` is set, THE CheckoutSessionService SHALL use Stripe for real payment processing via the embedded PaymentElement flow.
2. WHILE `SKIP_UCP_OUTBOUND=true` AND `STRIPE_SECRET_KEY` is absent, THE CheckoutSessionService SHALL fall back to the existing fake-complete behaviour and log a warning — the modal SHALL advance to the `success` step after the user submits the payment form.
3. THE existing `POST /commerce/checkout-sessions/:id/complete` endpoint SHALL remain functional and accept both `{ type: "stripe", payment_intent_id }` and the legacy `{ type: "card", last4 }` payloads.
4. THE existing `POST /commerce/checkout/sessions/:id/payment-link` endpoint SHALL remain functional for any callers that still use the redirect flow.
