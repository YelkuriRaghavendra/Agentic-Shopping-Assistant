import { Test } from '@nestjs/testing';
import { ConfigService } from '@nestjs/config';
import { IdempotencyService } from './idempotency.service';
import { REDIS_CLIENT } from '../../../redis.provider';
import { CommerceException } from '../../../shared/errors/commerce.exception';

const mockRedis = {
  get: jest.fn(),
  set: jest.fn(),
};

const mockConfig = {
  get: jest.fn((key: string, def?: unknown) => def),
};

describe('IdempotencyService', () => {
  let service: IdempotencyService;

  beforeEach(async () => {
    jest.clearAllMocks();
    const module = await Test.createTestingModule({
      providers: [
        IdempotencyService,
        { provide: REDIS_CLIENT, useValue: mockRedis },
        { provide: ConfigService, useValue: mockConfig },
      ],
    }).compile();
    service = module.get(IdempotencyService);
  });

  describe('wrap', () => {
    it('executes operation and caches result on cache miss', async () => {
      mockRedis.get.mockResolvedValue(null);
      mockRedis.set.mockResolvedValue('OK');
      const operation = jest.fn().mockResolvedValue({ orderId: '123' });

      const result = await service.wrap('key-1', { foo: 'bar' }, operation);

      expect(result).toEqual({ orderId: '123' });
      expect(operation).toHaveBeenCalledTimes(1);
      expect(mockRedis.set).toHaveBeenCalledWith(
        'idempotency:key-1',
        expect.any(String),
        'EX',
        86400,
      );
    });

    it('returns cached response on cache hit with same payload', async () => {
      const payload = { foo: 'bar' };
      const cachedResponse = { orderId: '123' };
      // Simulate what the service stores
      const crypto = require('crypto');
      const payloadHash = crypto.createHash('sha256').update(JSON.stringify(payload)).digest('hex');
      mockRedis.get.mockResolvedValue(
        JSON.stringify({ payloadHash, response: cachedResponse, createdAt: new Date().toISOString() }),
      );
      const operation = jest.fn();

      const result = await service.wrap('key-1', payload, operation);

      expect(result).toEqual(cachedResponse);
      expect(operation).not.toHaveBeenCalled();
    });

    it('throws 409 on cache hit with different payload', async () => {
      const originalPayload = { foo: 'bar' };
      const crypto = require('crypto');
      const originalHash = crypto.createHash('sha256').update(JSON.stringify(originalPayload)).digest('hex');
      mockRedis.get.mockResolvedValue(
        JSON.stringify({ payloadHash: originalHash, response: {}, createdAt: new Date().toISOString() }),
      );

      await expect(
        service.wrap('key-1', { foo: 'different' }, jest.fn()),
      ).rejects.toBeInstanceOf(CommerceException);
    });

    it('does not cache result if operation throws', async () => {
      mockRedis.get.mockResolvedValue(null);
      const operation = jest.fn().mockRejectedValue(new Error('upstream error'));

      await expect(service.wrap('key-1', {}, operation)).rejects.toThrow('upstream error');
      expect(mockRedis.set).not.toHaveBeenCalled();
    });
  });
});
