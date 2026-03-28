import { Test } from '@nestjs/testing';
import { ConfigService } from '@nestjs/config';
import { UcpCheckoutClient } from './ucp-checkout.client';
import { MerchantProfileService } from '../merchant-profile/merchant-profile.service';
import { RequestSigningService } from '../signing/request-signing.service';
import { IdempotencyService } from '../idempotency/idempotency.service';
import { RetryService } from '../retry/retry.service';
import { CircuitBreakerService } from '../circuit-breaker/circuit-breaker.service';

const mockMerchantProfile = {
  getCheckoutBaseUrl: jest.fn().mockResolvedValue('https://merchant.example.com'),
};
const mockSigning = {
  signRequest: jest.fn().mockResolvedValue('header..signature'),
};
const mockIdempotency = {
  wrap: jest.fn().mockImplementation((_key, _payload, op) => op()),
};
const mockRetry = {
  execute: jest.fn().mockImplementation((op) => op()),
};
const mockCircuitBreaker = {
  execute: jest.fn().mockImplementation((_endpoint, op) => op()),
};
const mockConfig = {
  get: jest.fn((key: string, def?: unknown) => def),
};

const mockCheckoutResponse = {
  id: 'chk_123',
  status: 'incomplete',
  totals: { subtotal_cents: 1000, tax_cents: 100, grand_total_cents: 1100 },
};

describe('UcpCheckoutClient', () => {
  let client: UcpCheckoutClient;

  beforeEach(async () => {
    jest.clearAllMocks();
    mockIdempotency.wrap.mockImplementation((_key: string, _payload: unknown, op: () => unknown) => op());
    mockRetry.execute.mockImplementation((op: () => unknown) => op());
    mockCircuitBreaker.execute.mockImplementation((_endpoint: string, op: () => unknown) => op());

    const module = await Test.createTestingModule({
      providers: [
        UcpCheckoutClient,
        { provide: MerchantProfileService, useValue: mockMerchantProfile },
        { provide: RequestSigningService, useValue: mockSigning },
        { provide: IdempotencyService, useValue: mockIdempotency },
        { provide: RetryService, useValue: mockRetry },
        { provide: CircuitBreakerService, useValue: mockCircuitBreaker },
        { provide: ConfigService, useValue: mockConfig },
      ],
    }).compile();
    client = module.get(UcpCheckoutClient);
  });

  function mockFetch(response: unknown, ok = true) {
    global.fetch = jest.fn().mockResolvedValue({
      ok,
      status: ok ? 200 : 500,
      json: async () => response,
      text: async () => JSON.stringify(response),
    }) as jest.Mock;
  }

  describe('createCheckoutSession', () => {
    it('calls POST /checkout-sessions with correct headers', async () => {
      mockFetch(mockCheckoutResponse);
      const payload = { line_items: [{ item: { id: 'p1', title: 'Shoe', price: 1000 }, quantity: 1 }] };

      const result = await client.createCheckoutSession('merchant-1', payload, 'idem-key-1');

      expect(result).toEqual(mockCheckoutResponse);
      const fetchCall = (global.fetch as jest.Mock).mock.calls[0];
      expect(fetchCall[0]).toBe('https://merchant.example.com/checkout-sessions');
      expect(fetchCall[1].method).toBe('POST');
      expect(fetchCall[1].headers['Request-Signature']).toBe('header..signature');
      expect(fetchCall[1].headers['UCP-Agent']).toContain('profile=');
      expect(fetchCall[1].headers['Request-Id']).toBeDefined();
    });

    it('uses idempotency service', async () => {
      mockFetch(mockCheckoutResponse);
      await client.createCheckoutSession('merchant-1', { line_items: [] }, 'idem-key-1');
      expect(mockIdempotency.wrap).toHaveBeenCalledWith('idem-key-1', expect.any(Object), expect.any(Function));
    });
  });

  describe('getCheckoutSession', () => {
    it('calls GET /checkout-sessions/:id', async () => {
      mockFetch(mockCheckoutResponse);
      const result = await client.getCheckoutSession('merchant-1', 'chk_123');

      expect(result).toEqual(mockCheckoutResponse);
      const fetchCall = (global.fetch as jest.Mock).mock.calls[0];
      expect(fetchCall[0]).toBe('https://merchant.example.com/checkout-sessions/chk_123');
      expect(fetchCall[1].method).toBe('GET');
    });

    it('does not use idempotency service (read-only)', async () => {
      mockFetch(mockCheckoutResponse);
      await client.getCheckoutSession('merchant-1', 'chk_123');
      expect(mockIdempotency.wrap).not.toHaveBeenCalled();
    });
  });

  describe('updateCheckoutSession', () => {
    it('calls PUT /checkout-sessions/:id', async () => {
      mockFetch(mockCheckoutResponse);
      const payload = { line_items: [] };
      await client.updateCheckoutSession('merchant-1', 'chk_123', payload, 'idem-key-2');

      const fetchCall = (global.fetch as jest.Mock).mock.calls[0];
      expect(fetchCall[0]).toBe('https://merchant.example.com/checkout-sessions/chk_123');
      expect(fetchCall[1].method).toBe('PUT');
    });
  });

  describe('completeCheckoutSession', () => {
    it('calls POST /checkout-sessions/:id/complete', async () => {
      const completedResponse = { ...mockCheckoutResponse, status: 'completed', order: { id: 'ord_1' } };
      mockFetch(completedResponse);
      const payload = { payment_instrument: { type: 'card', token: 'tok_123' } };

      const result = await client.completeCheckoutSession('merchant-1', 'chk_123', payload, 'idem-key-3');

      expect(result.status).toBe('completed');
      const fetchCall = (global.fetch as jest.Mock).mock.calls[0];
      expect(fetchCall[0]).toBe('https://merchant.example.com/checkout-sessions/chk_123/complete');
      expect(fetchCall[1].method).toBe('POST');
    });
  });

  describe('cancelCheckoutSession', () => {
    it('calls POST /checkout-sessions/:id/cancel', async () => {
      const canceledResponse = { ...mockCheckoutResponse, status: 'canceled' };
      mockFetch(canceledResponse);

      const result = await client.cancelCheckoutSession('merchant-1', 'chk_123', 'idem-key-4');

      expect(result.status).toBe('canceled');
      const fetchCall = (global.fetch as jest.Mock).mock.calls[0];
      expect(fetchCall[0]).toBe('https://merchant.example.com/checkout-sessions/chk_123/cancel');
      expect(fetchCall[1].method).toBe('POST');
    });
  });

  describe('error handling', () => {
    it('throws when UCP returns non-ok response', async () => {
      mockFetch({ error: 'server error' }, false);
      await expect(
        client.createCheckoutSession('merchant-1', { line_items: [] }, 'idem-key-5'),
      ).rejects.toThrow();
    });
  });
});
