import { Test } from '@nestjs/testing';
import { ConfigService } from '@nestjs/config';
import { PlatformProfileController } from './platform-profile.controller';
import { RequestSigningService } from '../../ucp-client/signing/request-signing.service';

// ── Mocks ──────────────────────────────────────────────────────────────────

const mockConfigService = {
  get: jest.fn(),
};

const mockSigningService = {
  signRequest: jest.fn(),
};

// ── Tests ──────────────────────────────────────────────────────────────────

describe('PlatformProfileController', () => {
  let controller: PlatformProfileController;

  beforeEach(async () => {
    jest.clearAllMocks();
    mockConfigService.get.mockImplementation((key: string, defaultVal?: string) => {
      if (key === 'PLATFORM_BASE_URL') return 'https://platform.example.com';
      if (key === 'PLATFORM_SIGNING_KEY_JWK') return undefined;
      if (key === 'PLATFORM_SIGNING_KEY_PKCS8') return undefined;
      if (key === 'PLATFORM_SIGNING_KEY_ID') return 'platform-key-1';
      if (key === 'PLATFORM_SIGNING_ALG') return 'ES256';
      return defaultVal;
    });

    const module = await Test.createTestingModule({
      controllers: [PlatformProfileController],
      providers: [
        { provide: ConfigService, useValue: mockConfigService },
        { provide: RequestSigningService, useValue: mockSigningService },
      ],
    }).compile();
    controller = module.get(PlatformProfileController);
  });

  describe('GET /.well-known/ucp', () => {
    it('returns a profile document with dev.ucp.shopping.order capability', async () => {
      const profile = await controller.getProfile();

      expect(profile).toHaveProperty('capabilities');
      const capabilities = profile['capabilities'] as Array<{ namespace: string }>;
      const orderCap = capabilities.find((c) => c.namespace === 'dev.ucp.shopping.order');
      expect(orderCap).toBeDefined();
    });

    it('includes webhook_url in the order capability config', async () => {
      const profile = await controller.getProfile();

      const capabilities = profile['capabilities'] as Array<{ namespace: string; config: { webhook_url: string } }>;
      const orderCap = capabilities.find((c) => c.namespace === 'dev.ucp.shopping.order');
      expect(orderCap?.config?.webhook_url).toContain('/commerce/webhooks/ucp/orders');
    });

    it('constructs webhook_url from PLATFORM_BASE_URL config', async () => {
      const profile = await controller.getProfile();

      const capabilities = profile['capabilities'] as Array<{ namespace: string; config: { webhook_url: string } }>;
      const orderCap = capabilities.find((c) => c.namespace === 'dev.ucp.shopping.order');
      expect(orderCap?.config?.webhook_url).toBe(
        'https://platform.example.com/commerce/webhooks/ucp/orders',
      );
    });

    it('strips trailing slash from PLATFORM_BASE_URL', async () => {
      mockConfigService.get.mockImplementation((key: string, defaultVal?: string) => {
        if (key === 'PLATFORM_BASE_URL') return 'https://platform.example.com/';
        return defaultVal;
      });

      const profile = await controller.getProfile();

      const capabilities = profile['capabilities'] as Array<{ namespace: string; config: { webhook_url: string } }>;
      const orderCap = capabilities.find((c) => c.namespace === 'dev.ucp.shopping.order');
      // Should not have double slash
      expect(orderCap?.config?.webhook_url).not.toContain('//commerce');
    });

    it('includes signing_keys in the profile', async () => {
      const profile = await controller.getProfile();

      expect(profile).toHaveProperty('signing_keys');
      const signingKeys = profile['signing_keys'] as { keys: unknown[] };
      expect(signingKeys).toHaveProperty('keys');
      expect(Array.isArray(signingKeys.keys)).toBe(true);
    });

    it('returns empty signing_keys.keys when no signing key is configured', async () => {
      const profile = await controller.getProfile();

      const signingKeys = profile['signing_keys'] as { keys: unknown[] };
      expect(signingKeys.keys).toHaveLength(0);
    });
  });
});
