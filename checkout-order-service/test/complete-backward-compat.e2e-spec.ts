/**
 * Property-Based E2E Test — /complete backward compatibility (Task 11.1)
 *
 * // Feature: stripe-payment-integration, Property 14: /complete endpoint accepts both stripe and legacy card payloads
 *
 * Property 14: /complete endpoint accepts both stripe and legacy card payloads
 * Validates: Requirements 9.3
 */

import * as request from 'supertest';
import * as fc from 'fast-check';
import { INestApplication } from '@nestjs/common';
import {
  buildTestApp,
  makeCheckoutSession,
  TEST_SESSION_ID,
  TestAppContext,
} from './e2e-helpers';
import { UcpCheckoutStatus } from '../src/shared/types/ucp-checkout-status.enum';

describe('Property 14: /complete endpoint accepts both stripe and legacy card payloads', () => {
  let ctx: TestAppContext;
  let app: INestApplication;

  beforeAll(async () => {
    ctx = await buildTestApp();
    app = ctx.app;
  });

  afterAll(async () => {
    await app.close();
  });

  beforeEach(() => {
    jest.clearAllMocks();
  });

  /**
   * **Validates: Requirements 9.3**
   *
   * For any call to POST /commerce/checkout-sessions/:id/complete with either
   * { type: "stripe", payment_intent_id: string } or { type: "card", last4: string }
   * as the payment_instrument, the endpoint should return HTTP 200 without error.
   */
  it('P14: returns HTTP 200 for both stripe and legacy card payment_instrument shapes', async () => {
    const stripePayload = fc.record({
      type: fc.constant('stripe'),
      payment_intent_id: fc.string(),
    });

    const legacyCardPayload = fc.record({
      type: fc.constant('card'),
      last4: fc.string(),
    });

    const paymentInstrumentArb = fc.oneof(stripePayload, legacyCardPayload);

    await fc.assert(
      fc.asyncProperty(paymentInstrumentArb, async (payment_instrument) => {
        // Arrange: set up a valid incomplete session for each run
        const session = makeCheckoutSession({
          ucpStatus: UcpCheckoutStatus.INCOMPLETE,
        });
        ctx.mocks.checkoutSessionRepo.findOne.mockResolvedValue(session);

        const completedSession = makeCheckoutSession({
          ucpStatus: UcpCheckoutStatus.COMPLETED,
        });
        ctx.mocks.checkoutSessionRepo.save.mockResolvedValue(completedSession);

        // UCP client returns completed status
        ctx.mocks.ucpCheckoutClient.completeCheckoutSession!.mockResolvedValue({
          id: session.ucpCheckoutId,
          status: 'completed',
          totals: session.totalsSnapshot,
          order: {
            id: 'ucp_ord_test',
            permalink_url: 'https://merchant.example.com/orders/ucp_ord_test',
          },
        });

        // Act
        const res = await request(app.getHttpServer())
          .post(`/commerce/checkout/sessions/${TEST_SESSION_ID}/complete`)
          .send({ payment_instrument });

        // Assert: endpoint returns HTTP 200 for both payload shapes
        return res.status === 200;
      }),
    );
  });
});
