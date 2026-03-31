import { HttpStatus, Inject, Injectable, Logger } from '@nestjs/common';
import { ConfigService } from '@nestjs/config';
import Redis from 'ioredis';
import { REDIS_CLIENT } from '../../../redis.provider';
import { CommerceErrorCodes, CommerceException } from '../../../shared/errors/commerce.exception';

export interface UcpWellKnownDocument {
  checkout_base_url: string;
  payment_handlers: string[];
  signing_keys: { keys: JwkKey[] };
  [key: string]: unknown;
}

export interface JwkKey {
  kid: string;
  kty: string;
  use?: string;
  alg?: string;
  n?: string;
  e?: string;
  x?: string;
  y?: string;
  crv?: string;
  [key: string]: unknown;
}

const CACHE_TTL_SECONDS = 300; // 5 minutes

/**
 * MerchantProfileService — fetches and caches the merchant's /.well-known/ucp document.
 * Cache key: merchant:profile:{merchant_id} in Redis, TTL 5 minutes.
 */
@Injectable()
export class MerchantProfileService {
  private readonly logger = new Logger(MerchantProfileService.name);
  private readonly ttl: number;

  constructor(
    @Inject(REDIS_CLIENT) private readonly redis: Redis,
    private readonly config: ConfigService,
  ) {
    this.ttl = config.get<number>('MERCHANT_PROFILE_TTL_SECONDS', CACHE_TTL_SECONDS);
  }

  async getProfile(merchantId: string): Promise<UcpWellKnownDocument> {
    const cacheKey = `merchant:profile:${merchantId}`;
    const cached = await this.redis.get(cacheKey);
    if (cached) {
      this.logger.debug(`Cache hit for merchant profile: ${merchantId}`);
      return JSON.parse(cached) as UcpWellKnownDocument;
    }

    const baseUrl = this.getMerchantBaseUrl(merchantId);
    const url = `${baseUrl}/.well-known/ucp`;

    let doc: UcpWellKnownDocument;
    try {
      const res = await fetch(url, {
        headers: { Accept: 'application/json' },
        signal: AbortSignal.timeout(5000),
      });
      if (!res.ok) {
        throw new Error(`HTTP ${res.status}`);
      }
      doc = (await res.json()) as UcpWellKnownDocument;
    } catch (err) {
      this.logger.error(`Failed to fetch /.well-known/ucp for merchant ${merchantId}: ${err}`);
      throw new CommerceException(
        CommerceErrorCodes.MERCHANT_PROFILE_UNAVAILABLE,
        `Merchant profile unavailable for ${merchantId}`,
        HttpStatus.SERVICE_UNAVAILABLE,
      );
    }

    await this.redis.set(cacheKey, JSON.stringify(doc), 'EX', this.ttl);
    return doc;
  }

  async getCheckoutBaseUrl(merchantId: string): Promise<string> {
    const profile = await this.getProfile(merchantId);
    return profile.checkout_base_url;
  }

  async getPaymentHandlers(merchantId: string): Promise<string[]> {
    const profile = await this.getProfile(merchantId);
    return profile.payment_handlers ?? [];
  }

  async getSigningKeys(merchantId: string): Promise<JwkKey[]> {
    const profile = await this.getProfile(merchantId);
    return profile.signing_keys?.keys ?? [];
  }

  /** Invalidate cached profile (e.g. after a signing key rotation). */
  async invalidateCache(merchantId: string): Promise<void> {
    await this.redis.del(`merchant:profile:${merchantId}`);
  }

  // ── Private ────────────────────────────────────────────────────────────────

  private getMerchantBaseUrl(merchantId: string): string {
    // In production, merchant base URLs are resolved from a registry or config.
    // For now, support a per-merchant env var: MERCHANT_{ID}_BASE_URL
    const envKey = `MERCHANT_${merchantId.toUpperCase().replace(/-/g, '_')}_BASE_URL`;
    const fromEnv = this.config.get<string>(envKey);
    if (fromEnv) return fromEnv.replace(/\/$/, '');
    // Fallback: treat merchantId as a base URL directly (useful in tests)
    return merchantId.startsWith('http') ? merchantId.replace(/\/$/, '') : `https://${merchantId}`;
  }
}
