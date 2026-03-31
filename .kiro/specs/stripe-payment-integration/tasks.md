# Implementation Plan: Stripe Payment Integration

## Overview

Integrate Stripe sandbox payments end-to-end: install dependencies, extend the backend entity and service, add a webhook controller, wire everything into NestJS, and refactor the frontend CheckoutModal to use Stripe Elements.

## Tasks

- [x] 1. Install dependencies and add environment variable placeholders
  - [x] 1.1 Install Stripe SDK in checkout-order-service
    - Run `npm install stripe` in `checkout-order-service/`
    - Verify `stripe` appears in `dependencies` in `checkout-order-service/package.json`
    - _Requirements: 1.1, 1.3_
  - [x] 1.2 Install Stripe.js packages in Frontend
    - Run `npm install @stripe/stripe-js @stripe/react-stripe-js` in `Frontend/`
    - Verify both packages appear in `dependencies` in `Frontend/package.json`
    - _Requirements: 4.1_
  - [x] 1.3 Add Stripe env var placeholders to checkout-order-service/.env
    - Append `STRIPE_SECRET_KEY=sk_test_` and `STRIPE_WEBHOOK_SECRET=whsec_` with comments to `checkout-order-service/.env`
    - _Requirements: 8.1, 8.4_
  - [x] 1.4 Add Stripe env var placeholder to Frontend/.env.local
    - Append `NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY=pk_test_` with a comment to `Frontend/.env.local`
    - _Requirements: 8.2, 8.5_

- [x] 2. Extend shared types and the CheckoutSession entity
  - [x] 2.1 Add PAYMENT_FAILED to UcpCheckoutStatus enum
    - Open `checkout-order-service/src/shared/types/ucp-checkout-status.enum.ts`
    - Add `PAYMENT_FAILED = 'payment_failed'` to the enum
    - _Requirements: 6.1_
  - [x] 2.2 Add Stripe columns to CheckoutSession entity
    - Open `checkout-order-service/src/modules/checkout/session/checkout-session.entity.ts`
    - Add `stripePaymentIntentId: string | null` column (`stripe_payment_intent_id`, varchar, nullable)
    - Add `stripeClientSecret: string | null` column (`stripe_client_secret`, text, nullable)
    - _Requirements: 3.1, 3.2_

- [x] 3. Create TypeORM migration for Stripe columns
  - [x] 3.1 Create migration file `checkout-order-service/src/migrations/checkout/003_add_stripe_columns.ts`
    - Implement `up`: ALTER TABLE to add `stripe_payment_intent_id VARCHAR(255)` and `stripe_client_secret TEXT`; CREATE UNIQUE INDEX on `stripe_payment_intent_id WHERE NOT NULL`
    - Implement `down`: DROP INDEX, DROP COLUMN for both columns
    - Class name: `AddStripeColumnsToCheckoutSessions1700000000003`
    - _Requirements: 3.1, 3.2_

- [x] 4. Create StripeModule (provider + module)
  - [x] 4.1 Create `checkout-order-service/src/modules/stripe/stripe.provider.ts`
    - Export `STRIPE_CLIENT` injection token constant
    - Export `stripeProvider` as a `FactoryProvider` that reads `STRIPE_SECRET_KEY` from `ConfigService`, throws if absent/empty, and returns `new Stripe(key, { apiVersion: '2024-06-20' })`
    - _Requirements: 1.1, 1.2, 1.3, 1.4_
  - [ ]* 4.2 Write unit test for StripeModule factory
    - Test that factory throws when `STRIPE_SECRET_KEY` is absent or empty
    - Test that factory passes `apiVersion: '2024-06-20'` to the Stripe constructor
    - _Requirements: 1.2, 1.3_
  - [x] 4.3 Create `checkout-order-service/src/modules/stripe/stripe.module.ts`
    - Decorate with `@Global()` and `@Module()`
    - Import `ConfigModule`, provide `stripeProvider`, export `stripeProvider`
    - Register `StripeWebhookController` in `controllers`
    - _Requirements: 1.4_

- [x] 5. Add Stripe payment methods to CheckoutSessionService
  - [x] 5.1 Implement `createOrGetPaymentIntent` in CheckoutSessionService
    - Inject `STRIPE_CLIENT` via constructor
    - Load session (404 if not found), assert not CANCELED (422)
    - If `stripePaymentIntentId` already set, return cached `{ client_secret, payment_intent_id }` without calling Stripe
    - Otherwise call `stripe.paymentIntents.create({ amount: grand_total_cents, currency: 'inr', metadata: { checkout_session_id } })`
    - Persist `stripePaymentIntentId` and `stripeClientSecret` on the session
    - Return `{ client_secret, payment_intent_id }`
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 3.3_
  - [ ]* 5.2 Write property test for createOrGetPaymentIntent — P1: Amount and currency
    - // Feature: stripe-payment-integration, Property 1: PaymentIntent creation uses session amount and INR currency
    - Use `fc.integer({ min: 1 })` for `grand_total_cents`; assert `stripe.paymentIntents.create` called with `{ amount: cents, currency: 'inr' }`
    - **Property 1: PaymentIntent creation uses session amount and INR currency**
    - **Validates: Requirements 2.1**
  - [ ]* 5.3 Write property test for createOrGetPaymentIntent — P2: Idempotence
    - // Feature: stripe-payment-integration, Property 2: PaymentIntent creation is idempotent
    - Pre-seed session with existing `stripePaymentIntentId`; assert second call returns same values and `stripe.paymentIntents.create` called at most once
    - **Property 2: PaymentIntent creation is idempotent**
    - **Validates: Requirements 2.6**
  - [ ]* 5.4 Write property test for createOrGetPaymentIntent — P3: Persistence round-trip
    - // Feature: stripe-payment-integration, Property 3: PaymentIntent fields are persisted (round-trip)
    - After call, assert `repo.findOne` returns session with `stripePaymentIntentId` and `stripeClientSecret` matching returned values
    - **Property 3: PaymentIntent fields are persisted (round-trip)**
    - **Validates: Requirements 2.5, 3.3**
  - [x] 5.5 Implement `handlePaymentSucceeded` in CheckoutSessionService
    - Find session by `stripePaymentIntentId`; if not found, log warning and return (idempotent)
    - Set `ucpStatus = COMPLETED`, set `ucpOrderId = randomUUID()` if not already set
    - Save session, call `handleCompleted(session)` to enqueue `order.confirmed`
    - _Requirements: 5.4_
  - [ ]* 5.6 Write property test for handlePaymentSucceeded — P8: succeeded → COMPLETED + enqueue
    - // Feature: stripe-payment-integration, Property 8: payment_intent.succeeded marks session COMPLETED and enqueues order.confirmed
    - Use `fc.string()` for `paymentIntentId`; assert session status = COMPLETED and `queue.add` called once with `order.confirmed`
    - **Property 8: payment_intent.succeeded marks session COMPLETED and enqueues order.confirmed**
    - **Validates: Requirements 5.4**
  - [x] 5.7 Implement `handlePaymentFailed` in CheckoutSessionService
    - Find session by `stripePaymentIntentId`; if not found, log warning and return
    - Set `ucpStatus = PAYMENT_FAILED`, save session, log failure reason
    - _Requirements: 5.5, 6.2_
  - [ ]* 5.8 Write property test for handlePaymentFailed — P9: failed → PAYMENT_FAILED
    - // Feature: stripe-payment-integration, Property 9: payment_intent.payment_failed marks session PAYMENT_FAILED
    - Use `fc.string()` for `paymentIntentId`; assert session status = PAYMENT_FAILED
    - **Property 9: payment_intent.payment_failed marks session PAYMENT_FAILED**
    - **Validates: Requirements 5.5, 6.2**
  - [ ]* 5.9 Write property test for createOrGetPaymentIntent — P11: PAYMENT_FAILED sessions allow retry
    - // Feature: stripe-payment-integration, Property 11: PAYMENT_FAILED sessions allow a new PaymentIntent to be created
    - Pre-set session to PAYMENT_FAILED; assert `createOrGetPaymentIntent` resolves without throwing
    - **Property 11: PAYMENT_FAILED sessions allow a new PaymentIntent to be created**
    - **Validates: Requirements 6.3**

- [x] 6. Add POST :id/payment-intent endpoint to CheckoutController
  - [x] 6.1 Add `createPaymentIntent` handler to `checkout-order-service/src/modules/checkout/session/checkout.controller.ts`
    - Add `@Post(':id/payment-intent')` decorated method that delegates to `checkoutSessionService.createOrGetPaymentIntent(id)` and returns the result
    - Existing `CommerceException` error handling propagates 404 and 422 automatically
    - _Requirements: 2.1, 2.2, 2.3, 2.4_

- [x] 7. Create StripeWebhookController
  - [x] 7.1 Create `checkout-order-service/src/modules/stripe/stripe-webhook.controller.ts`
    - Decorate with `@Controller('stripe')` (outside `commerce/` prefix)
    - Inject `STRIPE_CLIENT` and `CheckoutSessionService`
    - Implement `POST /stripe/webhooks`: read `req.rawBody` via `RawBodyRequest<Request>`, read `stripe-signature` header
    - Call `stripe.webhooks.constructEvent(rawBody, sig, STRIPE_WEBHOOK_SECRET)` — return 400 on failure
    - On `payment_intent.succeeded`: call `handlePaymentSucceeded(paymentIntentId)`
    - On `payment_intent.payment_failed`: call `handlePaymentFailed(paymentIntentId, lastPaymentError)`
    - All other event types: return 200 immediately
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 5.6, 5.7_
  - [ ]* 7.2 Write property test for StripeWebhookController — P7: All requests undergo signature verification
    - // Feature: stripe-payment-integration, Property 7: All webhook requests undergo signature verification
    - Assert `stripe.webhooks.constructEvent` is called before any business logic for every request
    - **Property 7: All webhook requests undergo signature verification**
    - **Validates: Requirements 5.2**
  - [ ]* 7.3 Write property test for StripeWebhookController — P10: Unknown event types return 200 with no side effects
    - // Feature: stripe-payment-integration, Property 10: Unrecognised webhook event types return 200 with no side effects
    - Use `fc.string().filter(s => !['payment_intent.succeeded','payment_intent.payment_failed'].includes(s))` for event type
    - Assert response 200, no `repo.save` called, no `queue.add` called
    - **Property 10: Unrecognised webhook event types return 200 with no side effects**
    - **Validates: Requirements 5.6**

- [x] 8. Register StripeModule in AppModule and enable rawBody in main.ts
  - [x] 8.1 Import `StripeModule` in `checkout-order-service/src/app.module.ts`
    - Add `StripeModule` to the `imports` array so `STRIPE_CLIENT` is globally available
    - _Requirements: 1.4_
  - [x] 8.2 Enable `rawBody: true` in `checkout-order-service/src/main.ts`
    - Pass `{ rawBody: true }` to `NestFactory.create(...)` so `req.rawBody` is populated for webhook signature verification
    - _Requirements: 5.1, 5.2_

- [x] 9. Checkpoint — backend wired and tests passing
  - Ensure all backend tests pass, ask the user if questions arise.

- [x] 10. Refactor CheckoutModal to use Stripe Elements
  - [x] 10.1 Initialise `stripePromise` at module level in `Frontend/components/CheckoutModal.tsx`
    - Import `loadStripe` from `@stripe/stripe-js`
    - Initialise `const stripePromise = process.env.NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY ? loadStripe(...) : null` outside the component
    - _Requirements: 4.1, 8.3_
  - [x] 10.2 Add `clientSecret` and `paymentIntentId` state; fetch PaymentIntent on address submit
    - Add `clientSecret` and `paymentIntentId` state variables
    - In `handleAddressSubmit`, after validation, call `POST /commerce/checkout-sessions/:id/payment-intent`; on success store values and advance to payment step; on failure display error and stay on address step
    - _Requirements: 4.2, 4.4_
  - [x] 10.3 Replace plain card inputs with Stripe Elements in the payment step
    - Import `Elements`, `PaymentElement`, `useStripe`, `useElements` from `@stripe/react-stripe-js`
    - Wrap payment step in `<Elements stripe={stripePromise} options={{ clientSecret }}>`
    - Replace card number / expiry / CVV inputs with `<PaymentElement />`
    - If `stripePromise` is null, render an error state indicating payment is unavailable
    - _Requirements: 4.3, 8.3_
  - [x] 10.4 Implement `handlePaymentSubmit` using `stripe.confirmPayment`
    - Call `stripe.confirmPayment({ elements, confirmParams: { return_url: window.location.href } })`
    - On success, advance to confirm step
    - On error, display `error.message` inline and stay on payment step
    - _Requirements: 4.5, 4.6, 4.7, 4.8_
  - [x] 10.5 Update `handleConfirm` to send Stripe payload to `/complete`
    - Change the `payment_instrument` body to `{ type: "stripe", payment_intent_id: paymentIntentId }`
    - _Requirements: 7.1, 7.2, 7.3, 7.4_
  - [ ]* 10.6 Write property test for CheckoutModal — P4: Address submit triggers payment-intent API call
    - // Feature: stripe-payment-integration, Property 4: Address submission triggers payment-intent API call
    - Use `fc.record({ fullName, addressLine, city, pincode })` for address fields; assert `fetch` called with URL containing `/payment-intent`
    - **Property 4: Address submission triggers payment-intent API call**
    - **Validates: Requirements 4.2**
  - [ ]* 10.7 Write property test for CheckoutModal — P5: confirmPayment receives stored clientSecret
    - // Feature: stripe-payment-integration, Property 5: Payment submission calls stripe.confirmPayment with stored client_secret
    - Use `fc.string()` for `clientSecret`; assert `stripe.confirmPayment` called with that exact `clientSecret`
    - **Property 5: Payment submission calls stripe.confirmPayment with stored client_secret**
    - **Validates: Requirements 4.5**
  - [ ]* 10.8 Write property test for CheckoutModal — P6: No raw card data sent to backend
    - // Feature: stripe-payment-integration, Property 6: No raw card data is sent to any backend endpoint
    - Assert all `fetch` calls to the backend contain no `cardNumber`, `expiry`, or `cvv` fields in request bodies
    - **Property 6: No raw card data is sent to any backend endpoint**
    - **Validates: Requirements 4.8**
  - [ ]* 10.9 Write property test for CheckoutModal — P12: /complete payload shape
    - // Feature: stripe-payment-integration, Property 12: Successful confirmPayment calls /complete with correct payload shape
    - Use `fc.string()` for `paymentIntentId`; assert `fetch` body contains `{ payment_instrument: { type: "stripe", payment_intent_id } }`
    - **Property 12: Successful confirmPayment calls /complete with correct payload shape**
    - **Validates: Requirements 7.1**
  - [ ]* 10.10 Write property test for CheckoutModal — P13: Submit button disabled during in-progress
    - // Feature: stripe-payment-integration, Property 13: Submit button is disabled while payment confirmation is in progress
    - While `handleConfirm` is pending, assert confirm button `disabled` attribute is true
    - **Property 13: Submit button is disabled while payment confirmation is in progress**
    - **Validates: Requirements 7.4**

- [x] 11. Write property test for /complete backward compatibility — P14
  - [x]* 11.1 Write property test for /complete endpoint — P14: Accepts both stripe and legacy card payloads
    - // Feature: stripe-payment-integration, Property 14: /complete endpoint accepts both stripe and legacy card payloads
    - Use `fc.oneof(fc.record({ type: fc.constant('stripe'), payment_intent_id: fc.string() }), fc.record({ type: fc.constant('card'), last4: fc.string() }))` for `payment_instrument`
    - Assert endpoint returns HTTP 200 for both payload shapes
    - **Property 14: /complete endpoint accepts both stripe and legacy card payloads**
    - **Validates: Requirements 9.3**

- [x] 12. Run database migration
  - [x] 12.1 Run `npm run migration:run` in `checkout-order-service/`
    - Execute `npm run migration:run` to apply `003_add_stripe_columns` against the configured database
    - Verify `stripe_payment_intent_id` and `stripe_client_secret` columns exist in `checkout.checkout_sessions`
    - _Requirements: 3.1, 3.2_

- [x] 13. Final checkpoint — Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for a faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate universal correctness properties from the design document
- Unit tests validate specific examples and edge cases
