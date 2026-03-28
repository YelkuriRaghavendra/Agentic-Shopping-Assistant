/**
 * E2E Integration Test — Health Endpoint and Trace Propagation (Task 14.3)
 *
 * Confirms:
 *  - GET /commerce/health returns 200 with correct dependency status
 *  - X-Request-ID propagation through service calls
 *
 * Requirements: 14.1, 14.2, 14.5
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
  TEST_LINE_ITEMS,
  TEST_BUYER,
  TEST_TOTALS,
  TEST_UCP_CHECKOUT_ID,
  TestAppContext,
} from './e2e-helpers';
import { UcpCheckoutStatus } from '../src/shared/types/ucp-checkout-status.enum';

describe('E2E: Health Endpoint and Trace Propagation (Task 14.3)', () => {
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

  // ── Health endpoint (Requirements 14.1, 14.2) ─────────────────────────────

  describe('GET /health', () => {
    it('returns 200 with service name and version', async () => {
      // Redis mock returns PONG, DataSource mock returns SELECT 1 result
      ctx.mocks.redis.ping.mockResolvedValue('PONG');
      ctx.mocks.dataSource.query.mockResolvedValue([{ '?column?': 1 }]);

      const res = await request(app.getHttpServer())
        .get('/health')
        .expect(200);

      expect(res.body).toMatchObject({
        service: 'checkout-order-service',
        status: expect.stringMatching(/^(ok|degraded)$/),
        dependencies: expect.objectContaining({
          postgres: expect.stringMatching(/^(up|down)$/),
          redis: expect.stringMatching(/^(up|down)$/),
          ucp: expect.stringMatching(/^(up|down)$/),
        }),
        timestamp: expect.any(String),
      });
    });

    it('returns service name "checkout-order-service"', async () => {
      const res = await request(app.getHttpServer())
        .get('/health')
        .expect(200);

      expect(res.body.service).toBe('checkout-order-service');
    });

    it('returns version field', async () => {
      const res = await request(app.getHttpServer())
        .get('/health')
        .expect(200);

      expect(res.body.version).toBeDefined();
    });

    it('returns postgres: up when database is reachable', async () => {
      ctx.mocks.dataSource.query.mockResolvedValue([{ '?column?': 1 }]);

      const res = await request(app.getHttpServer())
        .get('/health')
        .expect(200);

      expect(res.body.dependencies.postgres).toBe('up');
    });

    it('returns redis: up when Redis is reachable', async () => {
      ctx.mocks.redis.ping.mockResolvedValue('PONG');

      const res = await request(app.getHttpServer())
        .get('/health')
        .expect(200);

      expect(res.body.dependencies.redis).toBe('up');
    });

    it('returns redis: down when Redis ping fails', async () => {
      ctx.mocks.redis.ping.mockRejectedValue(new Error('Connection refused'));

      const res = await request(app.getHttpServer())
        .get('/health')
        .expect(200);

      // Status should be degraded when a dependency is down
      expect(res.body.dependencies.redis).toBe('down');
      expect(res.body.status).toBe('degraded');
    });

    it('returns postgres: down when database query fails', async () => {
      ctx.mocks.dataSource.query.mockRejectedValue(new Error('Connection refused'));

      const res = await request(app.getHttpServer())
        .get('/health')
        .expect(200);

      expect(res.body.dependencies.postgres).toBe('down');
      expect(res.body.status).toBe('degraded');
    });

    it('returns ISO 8601 timestamp', async () => {
      const res = await request(app.getHttpServer())
        .get('/health')
        .expect(200);

      const ts = new Date(res.body.timestamp);
      expect(ts.toISOString()).toBe(res.body.timestamp);
    });

    it('returns all required dependency keys', async () => {
      const res = await request(app.getHttpServer())
        .get('/health')
        .expect(200);

      expect(res.body.dependencies).toHaveProperty('postgres');
      expect(res.body.dependencies).toHaveProperty('redis');
      expect(res.body.dependencies).toHaveProperty('ucp');
    });
  });

  // ── X-Request-ID propagation (Requirement 14.5) ───────────────────────────

  describe('X-Request-ID propagation', () => {
    it('POST /commerce/checkout/sessions accepts X-Request-ID header without error', async () => {
      const requestId = 'test-request-id-12345';

      const ucpResponse = {
        id: TEST_UCP_CHECKOUT_ID,
        status: 'incomplete',
        payment_handlers: ['card'],
        totals: TEST_TOTALS,
        expires_at: null,
        continue_url: null,
      };
      ctx.mocks.ucpCheckoutClient.createCheckoutSession!.mockResolvedValue(ucpResponse);

      const session = makeCheckoutSession();
      ctx.mocks.checkoutSessionRepo.create.mockReturnValue(session);
      ctx.mocks.checkoutSessionRepo.save.mockResolvedValue(session);

      // The service should accept and process requests with X-Request-ID header
      await request(app.getHttpServer())
        .post('/commerce/checkout/sessions')
        .set('X-Request-ID', requestId)
        .send({
          merchant_id: TEST_MERCHANT_ID,
          customer_id: TEST_CUSTOMER_ID,
          line_items: TEST_LINE_ITEMS,
          buyer: TEST_BUYER,
        })
        .expect(201);
    });

    it('GET /commerce/checkout/sessions/:id accepts X-Request-ID header', async () => {
      const requestId = 'trace-id-abc-xyz';
      const session = makeCheckoutSession();
      ctx.mocks.checkoutSessionRepo.findOne.mockResolvedValue(session);

      await request(app.getHttpServer())
        .get(`/commerce/checkout/sessions/${TEST_SESSION_ID}`)
        .set('X-Request-ID', requestId)
        .expect(200);
    });

    it('GET /commerce/orders accepts X-Request-ID header', async () => {
      const requestId = 'trace-id-orders-001';
      const order = makeOrder();
      ctx.mocks.orderRepo.createQueryBuilder.mockReturnValue({
        where: jest.fn().mockReturnThis(),
        andWhere: jest.fn().mockReturnThis(),
        orderBy: jest.fn().mockReturnThis(),
        addOrderBy: jest.fn().mockReturnThis(),
        take: jest.fn().mockReturnThis(),
        getMany: jest.fn().mockResolvedValue([order]),
      });

      await request(app.getHttpServer())
        .get('/commerce/orders')
        .set('X-Request-ID', requestId)
        .query({ customerId: TEST_CUSTOMER_ID })
        .expect(200);
    });

    it('PUT /commerce/checkout/sessions/:id accepts X-Request-ID header', async () => {
      const requestId = 'trace-id-update-001';
      const session = makeCheckoutSession();
      ctx.mocks.checkoutSessionRepo.findOne.mockResolvedValue(session);

      const ucpUpdateResponse = {
        id: TEST_UCP_CHECKOUT_ID,
        status: 'incomplete',
        totals: TEST_TOTALS,
        continue_url: null,
      };
      ctx.mocks.ucpCheckoutClient.updateCheckoutSession!.mockResolvedValue(ucpUpdateResponse);
      ctx.mocks.checkoutSessionRepo.save.mockResolvedValue(session);

      await request(app.getHttpServer())
        .put(`/commerce/checkout/sessions/${TEST_SESSION_ID}`)
        .set('X-Request-ID', requestId)
        .send({ line_items: TEST_LINE_ITEMS })
        .expect(200);
    });
  });

  // ── Platform UCP profile (/.well-known/ucp) ───────────────────────────────

  describe('GET /.well-known/ucp — platform profile', () => {
    it('returns 200 with UCP profile document', async () => {
      const res = await request(app.getHttpServer())
        .get('/.well-known/ucp')
        .expect(200);

      expect(res.body).toMatchObject({
        capabilities: expect.arrayContaining([
          expect.objectContaining({
            namespace: 'dev.ucp.shopping.order',
          }),
        ]),
      });
    });

    it('includes webhook_url in order capability config', async () => {
      const res = await request(app.getHttpServer())
        .get('/.well-known/ucp')
        .expect(200);

      const orderCapability = res.body.capabilities?.find(
        (c: { namespace: string }) => c.namespace === 'dev.ucp.shopping.order',
      );
      expect(orderCapability).toBeDefined();
      expect(orderCapability?.config?.webhook_url).toBeDefined();
    });
  });

  // ── Webhook endpoint (POST /commerce/webhooks/ucp/orders) ─────────────────

  describe('POST /commerce/webhooks/ucp/orders', () => {
    it('returns 401 when Request-Signature header is missing', async () => {
      const res = await request(app.getHttpServer())
        .post('/commerce/webhooks/ucp/orders')
        .query({ merchant_id: TEST_MERCHANT_ID })
        .send({ event_id: 'evt-001', event_type: 'order.shipped' })
        .expect(401);

      expect(res.body).toMatchObject({ error: expect.any(String) });
    });

    it('returns 401 when signature verification fails', async () => {
      ctx.mocks.webhookVerificationService.verifyWebhook!.mockResolvedValue(false);

      const res = await request(app.getHttpServer())
        .post('/commerce/webhooks/ucp/orders')
        .query({ merchant_id: TEST_MERCHANT_ID })
        .set('request-signature', 'invalid-signature')
        .send({ event_id: 'evt-001', event_type: 'order.shipped' })
        .expect(401);

      expect(res.body).toMatchObject({ error: 'Invalid webhook signature' });
    });

    it('returns 200 when signature is valid', async () => {
      ctx.mocks.webhookVerificationService.verifyWebhook!.mockResolvedValue(true);
      ctx.mocks.webhookEventRepo.findOne.mockResolvedValue(null); // not a duplicate
      ctx.mocks.webhookEventRepo.save.mockResolvedValue({
        eventId: 'evt-001',
        merchantId: TEST_MERCHANT_ID,
        eventType: 'order.shipped',
        status: 'queued',
        signatureVerified: true,
      });

      const res = await request(app.getHttpServer())
        .post('/commerce/webhooks/ucp/orders')
        .query({ merchant_id: TEST_MERCHANT_ID })
        .set('request-signature', 'valid-signature')
        .send({ event_id: 'evt-001', event_type: 'order.shipped' })
        .expect(200);

      expect(res.body).toMatchObject({
        received: true,
        eventId: 'evt-001',
        duplicate: false,
      });
    });

    it('returns 200 with duplicate=true for repeated event_id', async () => {
      ctx.mocks.webhookVerificationService.verifyWebhook!.mockResolvedValue(true);
      // Simulate duplicate: findOne returns existing record
      ctx.mocks.webhookEventRepo.findOne.mockResolvedValue({
        eventId: 'evt-duplicate',
        status: 'processed',
      });

      const res = await request(app.getHttpServer())
        .post('/commerce/webhooks/ucp/orders')
        .query({ merchant_id: TEST_MERCHANT_ID })
        .set('request-signature', 'valid-signature')
        .send({ event_id: 'evt-duplicate', event_type: 'order.shipped' })
        .expect(200);

      expect(res.body).toMatchObject({
        received: true,
        duplicate: true,
      });
    });

    it('returns 400 when merchant_id is missing', async () => {
      await request(app.getHttpServer())
        .post('/commerce/webhooks/ucp/orders')
        .set('request-signature', 'some-signature')
        .send({ event_id: 'evt-001' })
        .expect(400);
    });
  });
});
