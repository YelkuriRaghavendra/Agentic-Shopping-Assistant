/**
 * E2E Integration Test — Full Checkout Flow (Task 14.1)
 *
 * Simulates: checkout_initiate → session create → update → ready_for_complete
 *            → complete → order.confirmed event → order appears in GET /commerce/orders
 *
 * Merchant UCP endpoints are mocked via nock.
 * Uses @nestjs/testing with mocked repositories and queues (no real DB/Redis needed).
 *
 * Requirements: 1.1, 2.1, 3.1, 5.1, 6.1
 */

import * as request from 'supertest';
import { INestApplication } from '@nestjs/common';
import {
  buildTestApp,
  makeCheckoutSession,
  makeOrder,
  TEST_MERCHANT_ID,
  TEST_CUSTOMER_ID,
  TEST_SESSION_ID,
  TEST_ORDER_ID,
  TEST_UCP_CHECKOUT_ID,
  TEST_UCP_ORDER_ID,
  TEST_LINE_ITEMS,
  TEST_BUYER,
  TEST_PAYMENT_INSTRUMENT,
  TEST_TOTALS,
  TestAppContext,
} from './e2e-helpers';
import { UcpCheckoutStatus } from '../src/shared/types/ucp-checkout-status.enum';
import { UcpOrderStatus } from '../src/shared/types/ucp-order-status.enum';

describe('E2E: Full Checkout Flow (Task 14.1)', () => {
  let ctx: TestAppContext;
  let app: INestApplication;
  let originalSkipUcp: string | undefined;

  beforeAll(async () => {
    // Ensure UCP outbound is NOT skipped so the mocked UCP client is called
    originalSkipUcp = process.env.SKIP_UCP_OUTBOUND;
    process.env.SKIP_UCP_OUTBOUND = 'false';
    ctx = await buildTestApp();
    app = ctx.app;
  });

  afterAll(async () => {
    await app.close();
    // Restore original env var
    if (originalSkipUcp !== undefined) {
      process.env.SKIP_UCP_OUTBOUND = originalSkipUcp;
    } else {
      delete process.env.SKIP_UCP_OUTBOUND;
    }
  });

  beforeEach(() => {
    jest.clearAllMocks();
  });

  // ── Step 1: POST /commerce/checkout/sessions — create session ──────────────

  describe('Step 1: Create checkout session (checkout_initiate)', () => {
    it('POST /commerce/checkout/sessions returns 201 with session data', async () => {
      // Arrange: UCP merchant returns incomplete session
      const ucpCreateResponse = {
        id: TEST_UCP_CHECKOUT_ID,
        status: 'incomplete',
        payment_handlers: ['card'],
        totals: TEST_TOTALS,
        expires_at: null,
        continue_url: null,
      };
      ctx.mocks.ucpCheckoutClient.createCheckoutSession!.mockResolvedValue(ucpCreateResponse);

      const createdSession = makeCheckoutSession();
      ctx.mocks.checkoutSessionRepo.create.mockReturnValue(createdSession);
      ctx.mocks.checkoutSessionRepo.save.mockResolvedValue(createdSession);

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

      // Assert
      expect(res.body).toMatchObject({
        sessionId: TEST_SESSION_ID,
        customerId: TEST_CUSTOMER_ID,
        merchantId: TEST_MERCHANT_ID,
        ucpCheckoutId: TEST_UCP_CHECKOUT_ID,
        ucpStatus: 'incomplete',
      });
      expect(ctx.mocks.ucpCheckoutClient.createCheckoutSession).toHaveBeenCalledWith(
        TEST_MERCHANT_ID,
        expect.objectContaining({ line_items: TEST_LINE_ITEMS }),
        expect.any(String),
      );
    });

    it('validates required fields — returns 400 when line_items is missing', async () => {
      await request(app.getHttpServer())
        .post('/commerce/checkout/sessions')
        .send({
          merchant_id: TEST_MERCHANT_ID,
          customer_id: TEST_CUSTOMER_ID,
          // line_items missing
        })
        .expect(400);
    });

    it('accepts request without merchant_id — uses DEFAULT_MERCHANT_ID fallback', async () => {
      // merchant_id is optional since Bug 5 fix; service uses DEFAULT_MERCHANT_ID
      const ucpCreateResponse = {
        id: TEST_UCP_CHECKOUT_ID,
        status: 'incomplete',
        payment_handlers: ['card'],
        totals: TEST_TOTALS,
        expires_at: null,
        continue_url: null,
      };
      ctx.mocks.ucpCheckoutClient.createCheckoutSession!.mockResolvedValue(ucpCreateResponse);

      const createdSession = makeCheckoutSession();
      ctx.mocks.checkoutSessionRepo.create.mockReturnValue(createdSession);
      ctx.mocks.checkoutSessionRepo.save.mockResolvedValue(createdSession);

      await request(app.getHttpServer())
        .post('/commerce/checkout/sessions')
        .send({
          customer_id: TEST_CUSTOMER_ID,
          line_items: TEST_LINE_ITEMS,
        })
        .expect(201);
    });
  });

  // ── Step 2: GET /commerce/checkout/sessions/:id — retrieve session ─────────

  describe('Step 2: Get checkout session', () => {
    it('GET /commerce/checkout/sessions/:id returns 200 with session', async () => {
      const session = makeCheckoutSession();
      ctx.mocks.checkoutSessionRepo.findOne.mockResolvedValue(session);

      const res = await request(app.getHttpServer())
        .get(`/commerce/checkout/sessions/${TEST_SESSION_ID}`)
        .expect(200);

      expect(res.body).toMatchObject({
        sessionId: TEST_SESSION_ID,
        ucpStatus: 'incomplete',
      });
    });

    it('GET /commerce/checkout/sessions/:id returns 404 for unknown session', async () => {
      ctx.mocks.checkoutSessionRepo.findOne.mockResolvedValue(null);

      const res = await request(app.getHttpServer())
        .get('/commerce/checkout/sessions/nonexistent-id')
        .expect(404);

      expect(res.body).toMatchObject({ errorCode: 'not_found' });
    });
  });

  // ── Step 3: PUT /commerce/checkout/sessions/:id — update session ───────────

  describe('Step 3: Update checkout session', () => {
    it('PUT /commerce/checkout/sessions/:id returns 200 with updated session', async () => {
      const session = makeCheckoutSession();
      ctx.mocks.checkoutSessionRepo.findOne.mockResolvedValue(session);

      const updatedLineItems = [
        ...TEST_LINE_ITEMS,
        { item: { id: 'prod-2', title: 'Nike Socks', price: 1500 }, quantity: 2 },
      ];
      const ucpUpdateResponse = {
        id: TEST_UCP_CHECKOUT_ID,
        status: 'incomplete',
        totals: { subtotal_cents: 15000, tax_cents: 1350, grand_total_cents: 16350 },
        continue_url: null,
      };
      ctx.mocks.ucpCheckoutClient.updateCheckoutSession!.mockResolvedValue(ucpUpdateResponse);

      const updatedSession = makeCheckoutSession({
        lineItemsSnapshot: updatedLineItems,
        totalsSnapshot: ucpUpdateResponse.totals,
      });
      ctx.mocks.checkoutSessionRepo.save.mockResolvedValue(updatedSession);

      const res = await request(app.getHttpServer())
        .put(`/commerce/checkout/sessions/${TEST_SESSION_ID}`)
        .send({ line_items: updatedLineItems })
        .expect(200);

      expect(res.body).toMatchObject({
        sessionId: TEST_SESSION_ID,
        ucpStatus: 'incomplete',
      });
      expect(ctx.mocks.ucpCheckoutClient.updateCheckoutSession).toHaveBeenCalledWith(
        TEST_MERCHANT_ID,
        TEST_UCP_CHECKOUT_ID,
        expect.objectContaining({ line_items: updatedLineItems }),
        expect.any(String),
      );
    });

    it('PUT returns 422 when session is canceled', async () => {
      const canceledSession = makeCheckoutSession({ ucpStatus: UcpCheckoutStatus.CANCELED });
      ctx.mocks.checkoutSessionRepo.findOne.mockResolvedValue(canceledSession);

      const res = await request(app.getHttpServer())
        .put(`/commerce/checkout/sessions/${TEST_SESSION_ID}`)
        .send({ line_items: TEST_LINE_ITEMS })
        .expect(422);

      expect(res.body).toMatchObject({ errorCode: 'session_canceled' });
    });
  });

  // ── Step 4: ready_for_complete → auto-complete ─────────────────────────────

  describe('Step 4: ready_for_complete → complete → order.confirmed', () => {
    it('POST /commerce/checkout/sessions/:id/complete triggers order.confirmed event when UCP returns completed', async () => {
      const session = makeCheckoutSession();
      ctx.mocks.checkoutSessionRepo.findOne.mockResolvedValue(session);

      const ucpCompleteResponse = {
        id: TEST_UCP_CHECKOUT_ID,
        status: 'completed',
        totals: TEST_TOTALS,
        order: {
          id: TEST_UCP_ORDER_ID,
          permalink_url: 'https://merchant.example.com/orders/ucp_ord_001',
        },
      };
      ctx.mocks.ucpCheckoutClient.completeCheckoutSession!.mockResolvedValue(ucpCompleteResponse);

      const completedSession = makeCheckoutSession({
        ucpStatus: UcpCheckoutStatus.COMPLETED,
        ucpOrderId: TEST_UCP_ORDER_ID,
        ucpOrderPermalink: 'https://merchant.example.com/orders/ucp_ord_001',
      });
      ctx.mocks.checkoutSessionRepo.save.mockResolvedValue(completedSession);

      const res = await request(app.getHttpServer())
        .post(`/commerce/checkout/sessions/${TEST_SESSION_ID}/complete`)
        .send({ payment_instrument: TEST_PAYMENT_INSTRUMENT })
        .expect(200);

      // Session should be completed
      expect(res.body).toMatchObject({
        ucpStatus: 'completed',
      });

      // order.confirmed event should be published to BullMQ
      expect(ctx.mocks.orderEventsQueue.add).toHaveBeenCalledWith(
        'order.confirmed',
        expect.objectContaining({
          eventType: 'order.confirmed',
          source: 'checkout-service',
          payload: expect.objectContaining({
            customerId: TEST_CUSTOMER_ID,
            merchantId: TEST_MERCHANT_ID,
          }),
        }),
      );
    });

    it('POST /commerce/checkout/sessions/:id/complete returns 400 when payment_instrument is missing', async () => {
      await request(app.getHttpServer())
        .post(`/commerce/checkout/sessions/${TEST_SESSION_ID}/complete`)
        .send({})
        .expect(400);
    });
  });

  // ── Step 5: GET /commerce/checkout/sessions/:id/summary ───────────────────

  describe('Step 5: Session summary in display currency', () => {
    it('GET /commerce/checkout/sessions/:id/summary returns totals in display currency', async () => {
      const session = makeCheckoutSession({ totalsSnapshot: TEST_TOTALS });
      ctx.mocks.checkoutSessionRepo.findOne.mockResolvedValue(session);

      const res = await request(app.getHttpServer())
        .get(`/commerce/checkout/sessions/${TEST_SESSION_ID}/summary`)
        .expect(200);

      expect(res.body).toMatchObject({
        subtotal: '120.00',   // 12000 cents → $120.00
        tax: '10.80',         // 1080 cents → $10.80
        grand_total: '130.80', // 13080 cents → $130.80
        currency: 'USD',
      });
    });
  });

  // ── Step 6: GET /commerce/orders — order appears after order.confirmed ──────

  describe('Step 6: Order appears in GET /commerce/orders after order.confirmed', () => {
    it('GET /commerce/orders returns the created order for the customer', async () => {
      const order = makeOrder();
      // Mock the query builder to return the order
      ctx.mocks.orderRepo.createQueryBuilder.mockReturnValue({
        where: jest.fn().mockReturnThis(),
        andWhere: jest.fn().mockReturnThis(),
        orderBy: jest.fn().mockReturnThis(),
        addOrderBy: jest.fn().mockReturnThis(),
        take: jest.fn().mockReturnThis(),
        getMany: jest.fn().mockResolvedValue([order]),
      });

      const res = await request(app.getHttpServer())
        .get('/commerce/orders')
        .query({ customerId: TEST_CUSTOMER_ID })
        .expect(200);

      expect(res.body).toMatchObject({
        data: expect.arrayContaining([
          expect.objectContaining({
            orderId: TEST_ORDER_ID,
            customerId: TEST_CUSTOMER_ID,
            status: 'processing',
          }),
        ]),
        nextCursor: null,
      });
    });

    it('GET /commerce/orders returns 400 when customerId is missing', async () => {
      await request(app.getHttpServer())
        .get('/commerce/orders')
        .expect(400);
    });
  });

  // ── Step 7: GET /commerce/orders/:id — order detail ───────────────────────

  describe('Step 7: Order detail', () => {
    it('GET /commerce/orders/:id returns order detail for the owning customer', async () => {
      const order = makeOrder();
      ctx.mocks.orderRepo.findOne.mockResolvedValue(order);

      const res = await request(app.getHttpServer())
        .get(`/commerce/orders/${TEST_ORDER_ID}`)
        .query({ customerId: TEST_CUSTOMER_ID })
        .expect(200);

      expect(res.body).toMatchObject({
        orderId: TEST_ORDER_ID,
        customerId: TEST_CUSTOMER_ID,
        ucpOrderId: TEST_UCP_ORDER_ID,
        status: 'processing',
      });
    });

    it('GET /commerce/orders/:id returns 404 for cross-customer access', async () => {
      const order = makeOrder({ customerId: 'other-customer-id' });
      ctx.mocks.orderRepo.findOne.mockResolvedValue(order);

      const res = await request(app.getHttpServer())
        .get(`/commerce/orders/${TEST_ORDER_ID}`)
        .query({ customerId: TEST_CUSTOMER_ID })
        .expect(404);

      expect(res.body).toMatchObject({ errorCode: 'not_found' });
    });

    it('GET /commerce/orders/:id returns 404 for non-existent order', async () => {
      ctx.mocks.orderRepo.findOne.mockResolvedValue(null);

      await request(app.getHttpServer())
        .get('/commerce/orders/nonexistent-order-id')
        .query({ customerId: TEST_CUSTOMER_ID })
        .expect(404);
    });
  });

  // ── Step 8: POST /commerce/checkout/sessions/:id/cancel ───────────────────

  describe('Step 8: Cancel checkout session', () => {
    it('POST /commerce/checkout/sessions/:id/cancel returns 200 with canceled session', async () => {
      const session = makeCheckoutSession();
      ctx.mocks.checkoutSessionRepo.findOne.mockResolvedValue(session);
      ctx.mocks.ucpCheckoutClient.cancelCheckoutSession!.mockResolvedValue({ id: TEST_UCP_CHECKOUT_ID, status: 'canceled' });

      const canceledSession = makeCheckoutSession({ ucpStatus: UcpCheckoutStatus.CANCELED });
      ctx.mocks.checkoutSessionRepo.save.mockResolvedValue(canceledSession);

      const res = await request(app.getHttpServer())
        .post(`/commerce/checkout/sessions/${TEST_SESSION_ID}/cancel`)
        .expect(200);

      expect(res.body).toMatchObject({ ucpStatus: 'canceled' });
    });
  });
});
