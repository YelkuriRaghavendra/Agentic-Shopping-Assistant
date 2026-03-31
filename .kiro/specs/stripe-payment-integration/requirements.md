# Requirements Document

## Introduction

This feature integrates Stripe sandbox payments end-to-end into the Vik Rai conversational shopping assistant. Currently, the checkout flow collects card details via a fake form and marks sessions as completed locally (SKIP_UCP_OUTBOUND=true mode). This integration replaces the fake card form with Stripe Elements in the frontend, adds a PaymentIntent creation endpoint to the checkout-order-service, and handles Stripe webhook events to drive the checkout session lifecycle to completion.

The flow is: Frontend CheckoutModal (address step) → backend creates Stripe PaymentIntent → frontend renders Stripe Elements for card capture → frontend confirms PaymentIntent → Stripe webhook fires payment_intent.succeeded → backend marks session COMPLETED and emits order.confirmed event.

## Glossary

- **Stripe_Client**: The Stripe Node.js SDK instance configured with the secret key in checkout-order-service
- **Stripe_Elements**: The Stripe.js frontend library that renders a PCI-compliant card input UI
- **PaymentIntent**: A Stripe object representing a payment attempt, identified by a `pi_*` ID and associated `client_secret`
- **Webhook_Controller**: The NestJS controller in checkout-order-service that receives and verifies Stripe webhook events
- **CheckoutModal**: The Next.js React component in the Frontend that presents the multi-step checkout UI to the user
- **CheckoutSessionService**: The NestJS service in checkout-order-service that manages the lifecycle of a CheckoutSession entity
- **CheckoutSession**: The TypeORM entity persisted in the `checkout.checkout_sessions` table representing a checkout attempt
- **Stripe_Webhook_Secret**: The `whsec_*` signing secret used to verify that incoming webhook payloads originate from Stripe
- **Payment_Step**: The second step of the CheckoutModal where the user enters card details
- **Order_Events_Queue**: The BullMQ queue to which `order.confirmed` events are published after a successful payment

## Requirements

### Requirement 1: Stripe SDK Initialisation in checkout-order-service

**User Story:** As a backend developer, I want the checkout-order-service to initialise the Stripe Node.js SDK at startup, so that all Stripe API calls share a single configured client.

#### Acceptance Criteria

1. THE Stripe_Client SHALL be initialised using the `STRIPE_SECRET_KEY` environment variable at application bootstrap.
2. IF `STRIPE_SECRET_KEY` is absent or empty at startup, THEN THE checkout-order-service SHALL throw a configuration error and refuse to start.
3. THE Stripe_Client SHALL set the Stripe API version to `2024-06-20` to ensure stable API behaviour.
4. THE Stripe_Client SHALL be provided as a NestJS injectable so that any module can consume it without re-initialising.

---

### Requirement 2: Create PaymentIntent Endpoint

**User Story:** As the frontend, I want to request a Stripe PaymentIntent for a checkout session, so that I can collect card details securely via Stripe Elements.

#### Acceptance Criteria

1. WHEN a POST request is received at `/commerce/checkout-sessions/:id/payment-intent`, THE CheckoutSessionService SHALL create a Stripe PaymentIntent with the `grand_total_cents` from the session's `totalsSnapshot` as the amount and `inr` as the currency.
2. WHEN the PaymentIntent is created successfully, THE CheckoutController SHALL respond with HTTP 200 and a JSON body containing `{ client_secret: string, payment_intent_id: string }`.
3. IF the checkout session does not exist, THEN THE CheckoutController SHALL respond with HTTP 404.
4. IF the checkout session has status `CANCELED`, THEN THE CheckoutController SHALL respond with HTTP 422.
5. THE CheckoutSessionService SHALL persist the Stripe `payment_intent_id` on the CheckoutSession entity so that it can be correlated with incoming webhook events.
6. WHEN a PaymentIntent already exists on the session, THE CheckoutSessionService SHALL return the existing PaymentIntent's client_secret rather than creating a duplicate.

---

### Requirement 3: Stripe PaymentIntent ID Persistence

**User Story:** As a backend developer, I want the CheckoutSession entity to store the Stripe PaymentIntent ID, so that webhook events can be matched to the correct session.

#### Acceptance Criteria

1. THE CheckoutSession entity SHALL include a nullable `stripePaymentIntentId` column of type `varchar`.
2. THE CheckoutSession entity SHALL include a nullable `stripeClientSecret` column of type `text` to cache the client secret and avoid redundant Stripe API calls.
3. WHEN a PaymentIntent is created, THE CheckoutSessionService SHALL persist both `stripePaymentIntentId` and `stripeClientSecret` on the CheckoutSession before returning the response.

---

### Requirement 4: Frontend Stripe Elements Integration

**User Story:** As a shopper, I want to enter my card details in a secure, PCI-compliant Stripe Elements form instead of a plain text input, so that my payment information is handled safely.

#### Acceptance Criteria

1. THE CheckoutModal SHALL load the Stripe.js library using the `NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY` environment variable.
2. WHEN the user advances from the address step to the payment step, THE CheckoutModal SHALL call `POST /commerce/checkout-sessions/:id/payment-intent` to obtain a `client_secret`.
3. WHEN the `client_secret` is received, THE CheckoutModal SHALL render a Stripe `PaymentElement` (or `CardElement`) mounted inside the payment step UI, replacing the previous plain card number / expiry / CVV inputs.
4. IF the PaymentIntent request fails, THEN THE CheckoutModal SHALL display an error message and remain on the address step.
5. WHEN the user submits the payment step, THE CheckoutModal SHALL call `stripe.confirmPayment` (or `stripe.confirmCardPayment`) with the `client_secret` and the collected billing address.
6. WHEN `stripe.confirmPayment` returns without error, THE CheckoutModal SHALL advance to the confirm/review step showing the masked card summary returned by Stripe.
7. IF `stripe.confirmPayment` returns an error, THEN THE CheckoutModal SHALL display the Stripe error message inline and allow the user to retry.
8. THE CheckoutModal SHALL NOT transmit raw card numbers to any backend endpoint.

---

### Requirement 5: Stripe Webhook Ingestion

**User Story:** As a backend developer, I want the checkout-order-service to receive and verify Stripe webhook events, so that payment outcomes drive the checkout session lifecycle.

#### Acceptance Criteria

1. THE Webhook_Controller SHALL expose a POST endpoint at `/stripe/webhooks` that accepts raw request bodies.
2. WHEN a webhook request is received, THE Webhook_Controller SHALL verify the `Stripe-Signature` header using the `STRIPE_WEBHOOK_SECRET` environment variable and the Stripe SDK's `constructEvent` method.
3. IF signature verification fails, THEN THE Webhook_Controller SHALL respond with HTTP 400 and log the failure.
4. WHEN a `payment_intent.succeeded` event is received and verified, THE Webhook_Controller SHALL invoke CheckoutSessionService to mark the matching session as COMPLETED and enqueue an `order.confirmed` event on the Order_Events_Queue.
5. WHEN a `payment_intent.payment_failed` event is received and verified, THE Webhook_Controller SHALL update the matching session's status to `PAYMENT_FAILED` and log the failure reason from the PaymentIntent's `last_payment_error`.
6. WHEN an unrecognised event type is received, THE Webhook_Controller SHALL respond with HTTP 200 and take no further action (acknowledge without processing).
7. THE Webhook_Controller SHALL respond with HTTP 200 to all successfully verified events, regardless of whether the event type is handled.

---

### Requirement 6: Checkout Session Status for Payment Failure

**User Story:** As a backend developer, I want a PAYMENT_FAILED status on CheckoutSession, so that failed payment attempts are distinguishable from cancellations.

#### Acceptance Criteria

1. THE UcpCheckoutStatus enum SHALL include a `PAYMENT_FAILED` value.
2. WHEN a `payment_intent.payment_failed` webhook is processed, THE CheckoutSessionService SHALL set the session's `ucpStatus` to `PAYMENT_FAILED`.
3. WHILE a session has status `PAYMENT_FAILED`, THE CheckoutSessionService SHALL allow a new PaymentIntent to be created for the same session, enabling the user to retry payment.

---

### Requirement 7: Frontend Post-Payment Confirmation

**User Story:** As a shopper, I want the checkout modal to confirm my order after Stripe processes the payment, so that I know my purchase was successful.

#### Acceptance Criteria

1. WHEN `stripe.confirmPayment` succeeds, THE CheckoutModal SHALL call `POST /commerce/checkout-sessions/:id/complete` with `{ payment_instrument: { type: "stripe", payment_intent_id: string } }` to notify the backend.
2. WHEN the complete endpoint responds with HTTP 200, THE CheckoutModal SHALL advance to the `success` step displaying the order confirmation.
3. IF the complete endpoint responds with a non-200 status, THEN THE CheckoutModal SHALL display the error message and remain on the confirm step.
4. WHILE the payment confirmation is in progress, THE CheckoutModal SHALL display a loading state and disable the submit button to prevent duplicate submissions.

---

### Requirement 8: Environment Configuration

**User Story:** As a developer, I want all Stripe credentials to be supplied via environment variables, so that sandbox and production keys can be swapped without code changes.

#### Acceptance Criteria

1. THE checkout-order-service SHALL read `STRIPE_SECRET_KEY` and `STRIPE_WEBHOOK_SECRET` from environment variables.
2. THE Frontend SHALL read `NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY` from environment variables.
3. IF `NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY` is absent, THEN THE CheckoutModal SHALL render an error state indicating that payment is unavailable.
4. THE checkout-order-service `.env` file SHALL include placeholder entries for `STRIPE_SECRET_KEY` and `STRIPE_WEBHOOK_SECRET` with comments indicating where to obtain the values.
5. THE Frontend `.env.local` file SHALL include a placeholder entry for `NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY`.

---

### Requirement 9: Backward Compatibility with SKIP_UCP_OUTBOUND Mode

**User Story:** As a developer, I want the Stripe integration to coexist with the existing SKIP_UCP_OUTBOUND local dev mode, so that the service can still be run without Stripe credentials during non-payment development.

#### Acceptance Criteria

1. WHILE `SKIP_UCP_OUTBOUND=true` AND `STRIPE_SECRET_KEY` is set, THE CheckoutSessionService SHALL use Stripe for real payment processing.
2. WHILE `SKIP_UCP_OUTBOUND=true` AND `STRIPE_SECRET_KEY` is absent, THE CheckoutSessionService SHALL fall back to the existing fake-complete behaviour and log a warning.
3. THE existing `POST /commerce/checkout-sessions/:id/complete` endpoint SHALL remain functional and accept the `{ payment_instrument: { type: "stripe", payment_intent_id } }` payload without breaking existing callers that pass the legacy `{ type: "card", last4 }` payload.
