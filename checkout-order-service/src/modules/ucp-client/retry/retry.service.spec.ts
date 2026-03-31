import { RetryService } from './retry.service';

describe('RetryService', () => {
  let service: RetryService;

  beforeEach(() => {
    service = new RetryService();
    // Speed up tests by mocking sleep
    jest.spyOn(service as any, 'sleep').mockResolvedValue(undefined);
  });

  afterEach(() => jest.restoreAllMocks());

  describe('execute', () => {
    it('returns result on first success', async () => {
      const op = jest.fn().mockResolvedValue('ok');
      const result = await service.execute(op);
      expect(result).toBe('ok');
      expect(op).toHaveBeenCalledTimes(1);
    });

    it('retries on transient error and succeeds', async () => {
      const transientErr = Object.assign(new Error('server error'), { status: 503 });
      const op = jest.fn()
        .mockRejectedValueOnce(transientErr)
        .mockResolvedValue('ok');

      const result = await service.execute(op);
      expect(result).toBe('ok');
      expect(op).toHaveBeenCalledTimes(2);
    });

    it('throws after max retries exhausted', async () => {
      const transientErr = Object.assign(new Error('server error'), { status: 500 });
      const op = jest.fn().mockRejectedValue(transientErr);

      await expect(service.execute(op)).rejects.toThrow('server error');
      expect(op).toHaveBeenCalledTimes(4); // 1 initial + 3 retries
    });

    it('does not retry on non-transient error', async () => {
      const nonTransient = Object.assign(new Error('bad request'), { status: 400 });
      const op = jest.fn().mockRejectedValue(nonTransient);

      await expect(service.execute(op)).rejects.toThrow('bad request');
      expect(op).toHaveBeenCalledTimes(1);
    });

    it('retries on 429 rate limit', async () => {
      const rateLimitErr = Object.assign(new Error('rate limited'), { status: 429 });
      const op = jest.fn()
        .mockRejectedValueOnce(rateLimitErr)
        .mockResolvedValue('ok');

      const result = await service.execute(op);
      expect(result).toBe('ok');
      expect(op).toHaveBeenCalledTimes(2);
    });
  });

  describe('isTransient', () => {
    it('returns true for 5xx status codes', () => {
      expect(service.isTransient(Object.assign(new Error(), { status: 500 }))).toBe(true);
      expect(service.isTransient(Object.assign(new Error(), { status: 503 }))).toBe(true);
    });

    it('returns true for 429', () => {
      expect(service.isTransient(Object.assign(new Error(), { status: 429 }))).toBe(true);
    });

    it('returns false for 4xx (except 429)', () => {
      expect(service.isTransient(Object.assign(new Error(), { status: 400 }))).toBe(false);
      expect(service.isTransient(Object.assign(new Error(), { status: 404 }))).toBe(false);
    });

    it('returns true for network/fetch errors', () => {
      const fetchErr = new TypeError('fetch failed');
      expect(service.isTransient(fetchErr)).toBe(true);
    });
  });

  describe('backoffMs', () => {
    it('returns a non-negative number', () => {
      for (let i = 0; i < 3; i++) {
        expect(service.backoffMs(i)).toBeGreaterThanOrEqual(0);
      }
    });

    it('increases cap with each attempt', () => {
      // The cap doubles each attempt; actual value is random but bounded
      const cap0 = 200 * Math.pow(2, 0); // 200
      const cap1 = 200 * Math.pow(2, 1); // 400
      // Just verify the function doesn't throw and returns a number
      expect(typeof service.backoffMs(0)).toBe('number');
      expect(typeof service.backoffMs(1)).toBe('number');
      expect(service.backoffMs(0)).toBeLessThanOrEqual(cap0);
      expect(service.backoffMs(1)).toBeLessThanOrEqual(cap1);
    });
  });
});
