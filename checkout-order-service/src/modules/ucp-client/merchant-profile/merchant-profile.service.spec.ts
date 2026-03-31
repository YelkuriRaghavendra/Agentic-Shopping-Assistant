import { Test } from '@nestjs/testing';
import { ConfigService } from '@nestjs/config';
import { MerchantProfileService } from './merchant-profile.service';
import { REDIS_CLIENT } from '../../../redis.provider';
import { CommerceException } from '../../../shared/errors/commerce.exception';

const mockRedis = {
  get: jest.fn(),
  set: jest.fn(),
  del: jest.fn(),
};

const mockConfig = {
  get: jest.fn((key: string, def?: unknown) => def),
};

const wellKnownDoc = {
  checkout_base_url: 'https://merchant.example.com',
  payment_handlers: ['stripe', 'paypal'],
  signing_keys: { keys: [{ kid: 'key-1', kty: 'EC' }] },
};

describe('MerchantProfileService', () => {
  let service: MerchantProfileService;

  beforeEach(async () => {
    jest.clearAllMocks();
    const module = await Test.createTestingModule({
      providers: [
        MerchantProfileService,
        { provide: REDIS_CLIENT, useValue: mockRedis },
        { provide: ConfigService, useValue: mockConfig },
      ],
    }).compile();
    service = module.get(MerchantProfileService);
  });

  describe('getProfile', () => {
    it('returns cached profile on cache hit', async () => {
      mockRedis.get.mockResolvedValue(JSON.stringify(wellKnownDoc));
      const result = await service.getProfile('merchant-1');
      expect(result).toEqual(wellKnownDoc);
      expect(mockRedis.set).not.toHaveBeenCalled();
    });

    it('fetches and caches profile on cache miss', async () => {
      mockRedis.get.mockResolvedValue(null);
      mockRedis.set.mockResolvedValue('OK');
      global.fetch = jest.fn().mockResolvedValue({
        ok: true,
        json: async () => wellKnownDoc,
      }) as jest.Mock;

      const result = await service.getProfile('https://merchant.example.com');
      expect(result).toEqual(wellKnownDoc);
      expect(mockRedis.set).toHaveBeenCalledWith(
        'merchant:profile:https://merchant.example.com',
        JSON.stringify(wellKnownDoc),
        'EX',
        300,
      );
    });

    it('throws CommerceException when fetch fails', async () => {
      mockRedis.get.mockResolvedValue(null);
      global.fetch = jest.fn().mockRejectedValue(new Error('network error')) as jest.Mock;

      await expect(service.getProfile('https://merchant.example.com')).rejects.toBeInstanceOf(
        CommerceException,
      );
    });

    it('throws CommerceException when HTTP response is not ok', async () => {
      mockRedis.get.mockResolvedValue(null);
      global.fetch = jest.fn().mockResolvedValue({ ok: false, status: 503 }) as jest.Mock;

      await expect(service.getProfile('https://merchant.example.com')).rejects.toBeInstanceOf(
        CommerceException,
      );
    });
  });

  describe('getCheckoutBaseUrl', () => {
    it('returns checkout_base_url from profile', async () => {
      mockRedis.get.mockResolvedValue(JSON.stringify(wellKnownDoc));
      const url = await service.getCheckoutBaseUrl('merchant-1');
      expect(url).toBe('https://merchant.example.com');
    });
  });

  describe('getPaymentHandlers', () => {
    it('returns payment_handlers from profile', async () => {
      mockRedis.get.mockResolvedValue(JSON.stringify(wellKnownDoc));
      const handlers = await service.getPaymentHandlers('merchant-1');
      expect(handlers).toEqual(['stripe', 'paypal']);
    });

    it('returns empty array when payment_handlers is missing', async () => {
      mockRedis.get.mockResolvedValue(JSON.stringify({ ...wellKnownDoc, payment_handlers: undefined }));
      const handlers = await service.getPaymentHandlers('merchant-1');
      expect(handlers).toEqual([]);
    });
  });

  describe('getSigningKeys', () => {
    it('returns signing keys from profile', async () => {
      mockRedis.get.mockResolvedValue(JSON.stringify(wellKnownDoc));
      const keys = await service.getSigningKeys('merchant-1');
      expect(keys).toEqual([{ kid: 'key-1', kty: 'EC' }]);
    });
  });

  describe('invalidateCache', () => {
    it('deletes the cache key', async () => {
      mockRedis.del.mockResolvedValue(1);
      await service.invalidateCache('merchant-1');
      expect(mockRedis.del).toHaveBeenCalledWith('merchant:profile:merchant-1');
    });
  });
});
