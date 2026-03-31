/**
 * E2E test helpers — shared utilities for building the NestJS test app,
 * creating mock providers, and setting up nock interceptors.
 */
import { INestApplication, ValidationPipe } from '@nestjs/common';
import { Test, TestingModule } from '@nestjs/testing';
import { getRepositoryToken } from '@nestjs/typeorm';
import { getQueueToken } from '@nestjs/bull';
import { DataSource } from 'typeorm';
import * as express from 'express';

import { AppModule } from '../src/app.module';
import { CheckoutSession } from '../src/modules/checkout/session/checkout-session.entity';
import { Order } from '../src/modules/orders/orders/order.entity';
import { OrderStatusHistory } from '../src/modules/orders/orders/order-status-history.entity';
import { WebhookEvent } from '../src/modules/orders/webhook/webhook-event.entity';
import { UcpCheckoutClient } from '../src/modules/ucp-client/checkout-client/ucp-checkout.client';
import { MerchantProfileService } from '../src/modules/ucp-client/merchant-profile/merchant-profile.service';
import { WebhookVerificationService } from '../src/modules/ucp-client/verification/webhook-verification.service';
import { RequestSigningService } from '../src/modules/ucp-client/signing/request-signing.service';
import { IdempotencyService } from '../src/modules/ucp-client/idempotency/idempotency.service';
import { RetryService } from '../src/modules/ucp-client/retry/retry.service';
import { CircuitBreakerService } from '../src/modules/ucp-client/circuit-breaker/circuit-breaker.service';
import { AuditService } from '../src/modules/orders/audit/audit.service';
import { RagIndexingService } from '../src/modules/orders/orders/rag-indexing.service';
import { REDIS_CLIENT } from '../src/redis.provider';
import { UcpCheckoutStatus } from '../src/shared/types/ucp-checkout-status.enum';
import { UcpOrderStatus } from '../src/shared/types/ucp-order-status.enum';

// ── Shared test data ─────────────────────────────────────────────────────────

export const TEST_MERCHANT_ID = 'test-merchant';
export const TEST_CUSTOMER_ID = '00000000-0000-0000-0000-000000000001';
export const TEST_SESSION_ID = '11111111-1111-1111-1111-111111111111';
export const TEST_ORDER_ID = '22222222-2222-2222-2222-222222222222';
export const TEST_UCP_CHECKOUT_ID = 'chk_test_001';
export const TEST_UCP_ORDER_ID = 'ucp_ord_001';

export const TEST_LINE_ITEMS = [
  { item: { id: 'prod-1', title: 'Nike Air Max', price: 12000 }, quantity: 1 },
];

export const TEST_BUYER = {
  first_name: 'Jane',
  last_name: 'Doe',
  email: 'jane@example.com',
};

export const TEST_PAYMENT_INSTRUMENT = {
  type: 'card',
  token: 'tok_test_visa',
};

export const TEST_TOTALS = {
  subtotal_cents: 12000,
  tax_cents: 1080,
  grand_total_cents: 13080,
};

// ── Mock factories ────────────────────────────────────────────────────────────

export function makeCheckoutSession(overrides: Partial<CheckoutSession> = {}): CheckoutSession {
  return {
    sessionId: TEST_SESSION_ID,
    customerId: TEST_CUSTOMER_ID,
    merchantId: TEST_MERCHANT_ID,
    ucpCheckoutId: TEST_UCP_CHECKOUT_ID,
    ucpStatus: UcpCheckoutStatus.INCOMPLETE,
    continueUrl: null,
    expiresAt: null,
    lineItemsSnapshot: TEST_LINE_ITEMS,
    buyerSnapshot: TEST_BUYER,
    contextSnapshot: null,
    paymentHandlers: ['card'],
    totalsSnapshot: TEST_TOTALS,
    ucpOrderId: null,
    ucpOrderPermalink: null,
    createdAt: new Date('2024-01-01T00:00:00Z'),
    updatedAt: new Date('2024-01-01T00:00:00Z'),
    ...overrides,
  } as CheckoutSession;
}

export function makeOrder(overrides: Partial<Order> = {}): Order {
  return {
    orderId: TEST_ORDER_ID,
    customerId: TEST_CUSTOMER_ID,
    checkoutId: TEST_SESSION_ID,
    merchantId: TEST_MERCHANT_ID,
    ucpOrderId: TEST_UCP_ORDER_ID,
    permalinkUrl: 'https://merchant.example.com/orders/ucp_ord_001',
    status: UcpOrderStatus.PROCESSING,
    lineItems: TEST_LINE_ITEMS,
    fulfillment: { events: [] } as any,
    adjustments: [],
    totals: TEST_TOTALS,
    createdAt: new Date('2024-01-01T00:00:00Z'),
    updatedAt: new Date('2024-01-01T00:00:00Z'),
    statusHistory: [],
    ...overrides,
  } as Order;
}

// ── Mock repository factory ───────────────────────────────────────────────────

export function makeMockRepo<T>(defaultEntity?: T) {
  return {
    findOne: jest.fn().mockResolvedValue(defaultEntity ?? null),
    find: jest.fn().mockResolvedValue(defaultEntity ? [defaultEntity] : []),
    save: jest.fn().mockImplementation((entity: T) => Promise.resolve(entity)),
    create: jest.fn().mockImplementation((data: Partial<T>) => data as T),
    createQueryBuilder: jest.fn().mockReturnValue({
      where: jest.fn().mockReturnThis(),
      andWhere: jest.fn().mockReturnThis(),
      orderBy: jest.fn().mockReturnThis(),
      addOrderBy: jest.fn().mockReturnThis(),
      take: jest.fn().mockReturnThis(),
      getMany: jest.fn().mockResolvedValue(defaultEntity ? [defaultEntity] : []),
    }),
  };
}

// ── Mock queue factory ────────────────────────────────────────────────────────

export function makeMockQueue() {
  return {
    add: jest.fn().mockResolvedValue({ id: 'job-1' }),
    process: jest.fn(),
  };
}

// ── Mock Redis ────────────────────────────────────────────────────────────────

export function makeMockRedis() {
  const store = new Map<string, string>();
  return {
    get: jest.fn().mockImplementation((key: string) => Promise.resolve(store.get(key) ?? null)),
    set: jest.fn().mockImplementation((key: string, value: string) => {
      store.set(key, value);
      return Promise.resolve('OK');
    }),
    del: jest.fn().mockResolvedValue(1),
    ping: jest.fn().mockResolvedValue('PONG'),
    setex: jest.fn().mockResolvedValue('OK'),
    expire: jest.fn().mockResolvedValue(1),
    _store: store,
  };
}

// ── Mock DataSource ───────────────────────────────────────────────────────────

export function makeMockDataSource(em: Record<string, jest.Mock>) {
  return {
    transaction: jest.fn().mockImplementation((cb: (em: unknown) => Promise<unknown>) => cb(em)),
    query: jest.fn().mockResolvedValue([{ '?column?': 1 }]),
    isInitialized: true,
  };
}

// ── App builder ───────────────────────────────────────────────────────────────

export interface TestAppContext {
  app: INestApplication;
  mocks: {
    checkoutSessionRepo: ReturnType<typeof makeMockRepo>;
    orderRepo: ReturnType<typeof makeMockRepo>;
    orderHistoryRepo: ReturnType<typeof makeMockRepo>;
    webhookEventRepo: ReturnType<typeof makeMockRepo>;
    ucpCheckoutClient: jest.Mocked<Partial<UcpCheckoutClient>>;
    merchantProfileService: jest.Mocked<Partial<MerchantProfileService>>;
    webhookVerificationService: jest.Mocked<Partial<WebhookVerificationService>>;
    orderEventsQueue: ReturnType<typeof makeMockQueue>;
    webhookIngestionQueue: ReturnType<typeof makeMockQueue>;
    redis: ReturnType<typeof makeMockRedis>;
    dataSource: ReturnType<typeof makeMockDataSource>;
    auditService: jest.Mocked<Partial<AuditService>>;
  };
}

export async function buildTestApp(): Promise<TestAppContext> {
  const checkoutSessionRepo = makeMockRepo<CheckoutSession>();
  const orderRepo = makeMockRepo<Order>();
  const orderHistoryRepo = makeMockRepo<OrderStatusHistory>();
  const webhookEventRepo = makeMockRepo<WebhookEvent>();
  const orderEventsQueue = makeMockQueue();
  const webhookIngestionQueue = makeMockQueue();
  const redis = makeMockRedis();

  const em = {
    create: jest.fn().mockImplementation((_Entity: unknown, data: Record<string, unknown>) => ({ ...data })),
    save: jest.fn().mockImplementation((entity: unknown) => Promise.resolve(entity)),
    findOne: jest.fn().mockResolvedValue(null),
    query: jest.fn().mockResolvedValue(undefined),
  };
  const dataSource = makeMockDataSource(em);

  const auditService = {
    write: jest.fn().mockResolvedValue(undefined),
  };

  const ucpCheckoutClient = {
    createCheckoutSession: jest.fn(),
    getCheckoutSession: jest.fn(),
    updateCheckoutSession: jest.fn(),
    completeCheckoutSession: jest.fn(),
    cancelCheckoutSession: jest.fn(),
  };

  const merchantProfileService = {
    getProfile: jest.fn(),
    getCheckoutBaseUrl: jest.fn().mockResolvedValue('https://merchant.example.com'),
    getPaymentHandlers: jest.fn().mockResolvedValue(['card']),
    getSigningKeys: jest.fn().mockResolvedValue([]),
    invalidateCache: jest.fn(),
  };

  const webhookVerificationService = {
    verifyWebhook: jest.fn().mockResolvedValue(true),
  };

  const requestSigningService = {
    signRequest: jest.fn().mockResolvedValue('mock-signature'),
    onModuleInit: jest.fn(),
  };

  const idempotencyService = {
    wrap: jest.fn().mockImplementation(
      (_key: string, _payload: unknown, fn: () => Promise<unknown>) => fn(),
    ),
  };

  const retryService = {
    execute: jest.fn().mockImplementation(
      (fn: () => Promise<unknown>) => fn(),
    ),
  };

  const circuitBreakerService = {
    execute: jest.fn().mockImplementation(
      (_endpoint: string, fn: () => Promise<unknown>) => fn(),
    ),
  };

  const ragIndexingService = {
    indexOrder: jest.fn().mockResolvedValue(undefined),
  };

  const moduleRef: TestingModule = await Test.createTestingModule({
    imports: [AppModule],
  })
    .overrideProvider(getRepositoryToken(CheckoutSession))
    .useValue(checkoutSessionRepo)
    .overrideProvider(getRepositoryToken(Order))
    .useValue(orderRepo)
    .overrideProvider(getRepositoryToken(OrderStatusHistory))
    .useValue(orderHistoryRepo)
    .overrideProvider(getRepositoryToken(WebhookEvent))
    .useValue(webhookEventRepo)
    .overrideProvider(getQueueToken('order-events'))
    .useValue(orderEventsQueue)
    .overrideProvider(getQueueToken('webhook-ingestion'))
    .useValue(webhookIngestionQueue)
    .overrideProvider(REDIS_CLIENT)
    .useValue(redis)
    .overrideProvider(DataSource)
    .useValue(dataSource)
    .overrideProvider(AuditService)
    .useValue(auditService)
    .overrideProvider(UcpCheckoutClient)
    .useValue(ucpCheckoutClient)
    .overrideProvider(MerchantProfileService)
    .useValue(merchantProfileService)
    .overrideProvider(WebhookVerificationService)
    .useValue(webhookVerificationService)
    .overrideProvider(RequestSigningService)
    .useValue(requestSigningService)
    .overrideProvider(IdempotencyService)
    .useValue(idempotencyService)
    .overrideProvider(RetryService)
    .useValue(retryService)
    .overrideProvider(CircuitBreakerService)
    .useValue(circuitBreakerService)
    .overrideProvider(RagIndexingService)
    .useValue(ragIndexingService)
    .compile();

  const app = moduleRef.createNestApplication({ rawBody: true });

  app.useGlobalPipes(
    new ValidationPipe({
      whitelist: true,
      transform: true,
      forbidNonWhitelisted: true,
    }),
  );

  // Note: controllers already include 'commerce' in their path prefix
  // (e.g. @Controller('commerce/checkout/sessions')), so we do NOT set
  // a global prefix here to avoid doubling up the prefix.
  // The health controller uses @Controller('health') and is registered
  // at /health in tests (no global prefix applied here).
  // The /.well-known/ucp route is excluded from any prefix.

  await app.init();

  return {
    app,
    mocks: {
      checkoutSessionRepo,
      orderRepo,
      orderHistoryRepo,
      webhookEventRepo,
      ucpCheckoutClient: ucpCheckoutClient as jest.Mocked<Partial<UcpCheckoutClient>>,
      merchantProfileService: merchantProfileService as jest.Mocked<Partial<MerchantProfileService>>,
      webhookVerificationService: webhookVerificationService as jest.Mocked<Partial<WebhookVerificationService>>,
      orderEventsQueue,
      webhookIngestionQueue,
      redis,
      dataSource,
      auditService: auditService as jest.Mocked<Partial<AuditService>>,
    },
  };
}
