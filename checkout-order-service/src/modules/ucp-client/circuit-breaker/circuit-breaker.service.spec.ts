import { Test } from '@nestjs/testing';
import { CircuitBreakerService } from './circuit-breaker.service';
import { REDIS_CLIENT } from '../../../redis.provider';
import { CommerceException } from '../../../shared/errors/commerce.exception';

const mockRedis = {
  get: jest.fn(),
  set: jest.fn(),
};

describe('CircuitBreakerService', () => {
  let service: CircuitBreakerService;

  beforeEach(async () => {
    jest.clearAllMocks();
    const module = await Test.createTestingModule({
      providers: [
        CircuitBreakerService,
        { provide: REDIS_CLIENT, useValue: mockRedis },
      ],
    }).compile();
    service = module.get(CircuitBreakerService);
  });

  describe('execute — CLOSED circuit', () => {
    it('executes operation and returns result', async () => {
      mockRedis.get.mockResolvedValue(null); // no record = CLOSED
      mockRedis.set.mockResolvedValue('OK');
      const op = jest.fn().mockResolvedValue('success');

      const result = await service.execute('merchant:endpoint', op);
      expect(result).toBe('success');
    });

    it('increments failure count on error (below threshold)', async () => {
      mockRedis.get.mockResolvedValue(JSON.stringify({ state: 'CLOSED', failures: 1 }));
      mockRedis.set.mockResolvedValue('OK');
      const op = jest.fn().mockRejectedValue(new Error('fail'));

      await expect(service.execute('merchant:endpoint', op)).rejects.toThrow('fail');
      // Should have saved state with failures: 2, still CLOSED
      const savedState = JSON.parse(mockRedis.set.mock.calls[0][1]);
      expect(savedState.state).toBe('CLOSED');
      expect(savedState.failures).toBe(2);
    });

    it('opens circuit after 3 consecutive failures', async () => {
      mockRedis.get.mockResolvedValue(JSON.stringify({ state: 'CLOSED', failures: 2 }));
      mockRedis.set.mockResolvedValue('OK');
      const op = jest.fn().mockRejectedValue(new Error('fail'));

      await expect(service.execute('merchant:endpoint', op)).rejects.toThrow('fail');
      const savedState = JSON.parse(mockRedis.set.mock.calls[0][1]);
      expect(savedState.state).toBe('OPEN');
      expect(savedState.failures).toBe(3);
    });
  });

  describe('execute — OPEN circuit', () => {
    it('throws ucp_unavailable without calling operation', async () => {
      mockRedis.get.mockResolvedValue(
        JSON.stringify({ state: 'OPEN', failures: 3, openedAt: Date.now() }),
      );
      const op = jest.fn();

      await expect(service.execute('merchant:endpoint', op)).rejects.toBeInstanceOf(
        CommerceException,
      );
      expect(op).not.toHaveBeenCalled();
    });

    it('allows probe after half-open timeout', async () => {
      const openedAt = Date.now() - 61_000; // 61 seconds ago
      mockRedis.get.mockResolvedValue(
        JSON.stringify({ state: 'OPEN', failures: 3, openedAt }),
      );
      mockRedis.set.mockResolvedValue('OK');
      const op = jest.fn().mockResolvedValue('probe-ok');

      const result = await service.execute('merchant:endpoint', op);
      expect(result).toBe('probe-ok');
    });
  });

  describe('execute — success resets circuit', () => {
    it('resets to CLOSED with 0 failures on success', async () => {
      mockRedis.get.mockResolvedValue(JSON.stringify({ state: 'CLOSED', failures: 2 }));
      mockRedis.set.mockResolvedValue('OK');
      const op = jest.fn().mockResolvedValue('ok');

      await service.execute('merchant:endpoint', op);
      const savedState = JSON.parse(mockRedis.set.mock.calls[0][1]);
      expect(savedState.state).toBe('CLOSED');
      expect(savedState.failures).toBe(0);
    });
  });
});
