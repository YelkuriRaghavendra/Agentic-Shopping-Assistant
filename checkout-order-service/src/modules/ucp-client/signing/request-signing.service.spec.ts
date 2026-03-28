import { Test } from '@nestjs/testing';
import { ConfigService } from '@nestjs/config';
import { RequestSigningService } from './request-signing.service';

const mockConfig = {
  get: jest.fn((key: string, def?: unknown) => def),
};

describe('RequestSigningService', () => {
  let service: RequestSigningService;

  beforeEach(async () => {
    jest.clearAllMocks();
    const module = await Test.createTestingModule({
      providers: [
        RequestSigningService,
        { provide: ConfigService, useValue: mockConfig },
      ],
    }).compile();
    service = module.get(RequestSigningService);
    // Initialize the service (loads/generates key)
    await service.onModuleInit();
  });

  describe('signRequest', () => {
    it('returns a detached JWS string (header..signature format)', async () => {
      const body = Buffer.from(JSON.stringify({ foo: 'bar' }));
      const signature = await service.signRequest(body);

      // Detached JWS: header..signature (empty payload segment)
      const parts = signature.split('.');
      expect(parts).toHaveLength(3);
      expect(parts[1]).toBe(''); // empty payload = detached
    });

    it('produces different signatures for different bodies', async () => {
      const body1 = Buffer.from('{"a":1}');
      const body2 = Buffer.from('{"a":2}');

      const sig1 = await service.signRequest(body1);
      const sig2 = await service.signRequest(body2);

      expect(sig1).not.toBe(sig2);
    });

    it('produces consistent header for same key', async () => {
      const body = Buffer.from('test');
      const sig1 = await service.signRequest(body);
      const sig2 = await service.signRequest(body);

      // Headers should be the same (same key, same alg)
      const header1 = sig1.split('.')[0];
      const header2 = sig2.split('.')[0];
      expect(header1).toBe(header2);
    });

    it('handles empty body', async () => {
      const body = Buffer.alloc(0);
      const signature = await service.signRequest(body);
      const parts = signature.split('.');
      expect(parts).toHaveLength(3);
      expect(parts[1]).toBe('');
    });
  });
});
