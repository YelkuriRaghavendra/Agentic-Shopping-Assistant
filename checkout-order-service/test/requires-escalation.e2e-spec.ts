/**
 * E2E Integration Test — requires_escalation Flow (Task 14.2)
 *
 * Simulates merchant returning requires_escalation; asserts:
 *  - continue_url is returned to caller
 *  - No Complete Checkout call is made
 *
 * Requirements: 2.3
 */

import * as request from 'supertest';
import { INestApplication } from '@nestjs/common';
import {
  buildTestApp,
  makeCheckoutSession,
  TEST_MERCHANT_ID,
  TEST_CUSTOMER_ID,
  TEST_SESSION_ID,
  TEST_UCP_CHECKOUT_ID,
  TEST_LINE_ITEMS,
  TEST_BUYER,
  TEST_TOTALS,
  TestAppContext,
} from './e2e-helpers';
import { UcpCheckoutStatus } from '../src/shared/types/ucp-checkout-status.enum';

const CONTINUE_URL = 'https://merchant.example.com/checkout/escalate/abc123';

describe('E2E: requires_escalation Flow (Task 14.2)', () => {
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

  // ── Scenario 1: Create session returns requires_escalation ─────────────────

  describe('Scenario 1: Create session — merchant returns requires_escalation', () => {
    it('POST /commerce/checkout/sessions returns session with continue_url when merchant requires escalation', async () => {
      // Arrange: merchant returns requires_escalation on create
      const ucpResponse = {
        id: TEST_UCP_CHECKOUT_ID,
        status: 'requires_escalation',
        continue_url: CONTINUE_URL,
        payment_handlers: [],
        totals: TEST_TOTALS,
        expires_at: null,
        messages: [{ type: 'info', text: 'Please complete checkout on merchant site' }],
      };
      ctx.mocks.ucpCheckoutClient.createCheckoutSession!.mockResolvedValue(ucpResponse);

      const escalatedSession = makeCheckoutSession({
        ucpStatus: UcpCheckoutStatus.REQUIRES_ESCALATION,
        continueUrl: CONTINUE_URL,
      });
      ctx.mocks.checkoutSessionRepo.create.mockReturnValue(escalatedSession);
      ctx.mocks.checkoutSessionRepo.save.mockResolvedValue(escalatedSession);

      // Act
      const res = await request(app.getHttpServer())
        .post('/commerce/checkout/sessions')
        .send({
          merchant_id: TEST_MERCHANT_ID,
          customer_id: TEST_CUSTOMER_ID,
          line_items: TEST_LINE_ITEMS,
          buyer: TEST_BUYER,
        })
        .expect(201);

      // Assert: continue_url is returned
      expect(res.body).toMatchObject({
        ucpStatus: 'requires_escalation',
        continueUrl: CONTINUE_URL,
      });

      // Assert: Complete Checkout was NOT called
      expect(ctx.mocks.ucpCheckoutClient.completeCheckoutSession).not.toHaveBeenCalled();
    });
  });

  // ── Scenario 2: Update session returns requires_escalation ────────────────

  describe('Scenario 2: Update session — merchant returns requires_escalation', () => {
    it('PUT /commerce/checkout/sessions/:id returns continue_url and does not call Complete Checkout', async () => {
      // Arrange: existing incomplete session
      const existingSession = makeCheckoutSession();
      ctx.mocks.checkoutSessionRepo.findOne.mockResolvedValue(existingSession);

      // Merchant returns requires_escalation on update
      const ucpUpdateResponse = {
        id: TEST_UCP_CHECKOUT_ID,
        status: 'requires_escalation',
        continue_url: CONTINUE_URL,
        totals: TEST_TOTALS,
        messages: [{ type: 'action_required', text: 'Verify your identity at merchant site' }],
      };
      ctx.mocks.ucpCheckoutClient.updateCheckoutSession!.mockResolvedValue(ucpUpdateResponse);

      const escalatedSession = makeCheckoutSession({
        ucpStatus: UcpCheckoutStatus.REQUIRES_ESCALATION,
        continueUrl: CONTINUE_URL,
      });
      ctx.mocks.checkoutSessionRepo.save.mockResolvedValue(escalatedSession);

      // Act
      const res = await request(app.getHttpServer())
        .put(`/commerce/checkout/sessions/${TEST_SESSION_ID}`)
        .send({ line_items: TEST_LINE_ITEMS })
        .expect(200);

      // Assert: continue_url is returned to caller
      expect(res.body).toMatchObject({
        ucpStatus: 'requires_escalation',
        continueUrl: CONTINUE_URL,
      });

      // Assert: Complete Checkout was NOT called (Requirement 2.3)
      expect(ctx.mocks.ucpCheckoutClient.completeCheckoutSession).not.toHaveBeenCalled();
    });

    it('continue_url is stored on the session record', async () => {
      const existingSession = makeCheckoutSession();
      ctx.mocks.checkoutSessionRepo.findOne.mockResolvedValue(existingSession);

      const ucpUpdateResponse = {
        id: TEST_UCP_CHECKOUT_ID,
        status: 'requires_escalation',
        continue_url: CONTINUE_URL,
        totals: TEST_TOTALS,
      };
      ctx.mocks.ucpCheckoutClient.updateCheckoutSession!.mockResolvedValue(ucpUpdateResponse);

      const escalatedSession = makeCheckoutSession({
        ucpStatus: UcpCheckoutStatus.REQUIRES_ESCALATION,
        continueUrl: CONTINUE_URL,
      });
      ctx.mocks.checkoutSessionRepo.save.mockResolvedValue(escalatedSession);

      await request(app.getHttpServer())
        .put(`/commerce/checkout/sessions/${TEST_SESSION_ID}`)
        .send({ line_items: TEST_LINE_ITEMS })
        .expect(200);

      // The session was saved with the continue_url
      expect(ctx.mocks.checkoutSessionRepo.save).toHaveBeenCalledWith(
        expect.objectContaining({ continueUrl: CONTINUE_URL }),
      );
    });
  });

  // ── Scenario 3: Complete session returns requires_escalation ──────────────

  describe('Scenario 3: Complete session — merchant returns requires_escalation', () => {
    it('POST /commerce/checkout/sessions/:id/complete returns requires_escalation status when merchant requires escalation', async () => {
      const existingSession = makeCheckoutSession();
      ctx.mocks.checkoutSessionRepo.findOne.mockResolvedValue(existingSession);

      const ucpCompleteResponse = {
        id: TEST_UCP_CHECKOUT_ID,
        status: 'requires_escalation',
        continue_url: CONTINUE_URL,
        totals: TEST_TOTALS,
      };
      ctx.mocks.ucpCheckoutClient.completeCheckoutSession!.mockResolvedValue(ucpCompleteResponse);

      const escalatedSession = makeCheckoutSession({
        ucpStatus: UcpCheckoutStatus.REQUIRES_ESCALATION,
      });
      ctx.mocks.checkoutSessionRepo.save.mockResolvedValue(escalatedSession);

      const res = await request(app.getHttpServer())
        .post(`/commerce/checkout/sessions/${TEST_SESSION_ID}/complete`)
        .send({ payment_instrument: { type: 'card', token: 'tok_test' } })
        .expect(200);

      // Status should be requires_escalation
      expect(res.body).toMatchObject({
        ucpStatus: 'requires_escalation',
      });

      // No order.confirmed event should be published
      expect(ctx.mocks.orderEventsQueue.add).not.toHaveBeenCalled();
    });
  });

  // ── Scenario 4: GET session after escalation shows continue_url ───────────

  describe('Scenario 4: GET session after escalation', () => {
    it('GET /commerce/checkout/sessions/:id returns continue_url for escalated session', async () => {
      const escalatedSession = makeCheckoutSession({
        ucpStatus: UcpCheckoutStatus.REQUIRES_ESCALATION,
        continueUrl: CONTINUE_URL,
      });
      ctx.mocks.checkoutSessionRepo.findOne.mockResolvedValue(escalatedSession);

      const res = await request(app.getHttpServer())
        .get(`/commerce/checkout/sessions/${TEST_SESSION_ID}`)
        .expect(200);

      expect(res.body).toMatchObject({
        ucpStatus: 'requires_escalation',
        continueUrl: CONTINUE_URL,
      });
    });
  });
});
