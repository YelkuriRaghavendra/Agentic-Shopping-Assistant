import { Inject, Injectable, Logger } from '@nestjs/common';
import { ConfigService } from '@nestjs/config';
import Redis from 'ioredis';
import { REDIS_CLIENT } from '../../../redis.provider';
import { VaultService } from '../vault/vault.service';
import { CommerceErrorCodes, CommerceException } from '../../../shared/errors/commerce.exception';
import { HttpStatus } from '@nestjs/common';

interface UcpTokenResponse {
  access_token: string;
  expires_in: number; // seconds
  token_type: string;
}

interface CachedToken {
  accessToken: string;
  expiresAt: number; // unix ms
}

/**
 * TokenExchangeService — exchanges a platform customerId for a short-lived
 * UCP access token. Tokens are cached in Redis with a TTL of (expires_in - buffer).
 * Proactively refreshes when the cached token is within BUFFER seconds of expiry.
 */
@Injectable()
export class TokenExchangeService {
  private readonly logger = new Logger(TokenExchangeService.name);
  private readonly tokenUrl: string;
  private readonly clientId: string;
  private readonly refreshBufferMs: number;

  constructor(
    @Inject(REDIS_CLIENT) private readonly redis: Redis,
    private readonly config: ConfigService,
    private readonly vault: VaultService,
  ) {
    this.tokenUrl = config.getOrThrow<string>('UCP_OAUTH_TOKEN_URL');
    this.clientId = config.getOrThrow<string>('UCP_OAUTH_CLIENT_ID');
    const bufferSec = config.get<number>('TOKEN_REFRESH_BUFFER_SECONDS', 30);
    this.refreshBufferMs = bufferSec * 1000;
  }

  /**
   * Returns a valid UCP access token for the given customerId.
   * Uses Redis cache; proactively refreshes when near expiry.
   */
  async getToken(customerId: string): Promise<string> {
    const key = `ucp:token:${customerId}`;

    const cached = await this.redis.get(key);
    if (cached) {
      const parsed: CachedToken = JSON.parse(cached);
      const msUntilExpiry = parsed.expiresAt - Date.now();

      if (msUntilExpiry > this.refreshBufferMs) {
        // Token is fresh — return it
        return parsed.accessToken;
      }
      // Within refresh buffer — fall through to refresh
      this.logger.debug(`Token for ${customerId} near expiry, proactively refreshing`);
    }

    return this.fetchAndCacheToken(customerId, key);
  }

  // ── Private ────────────────────────────────────────────────────────────────

  private async fetchAndCacheToken(customerId: string, redisKey: string): Promise<string> {
    let response: Response;
    try {
      const clientSecret = this.vault.getUcpOAuthClientSecret();
      response = await fetch(this.tokenUrl, {
        method: 'POST',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        body: new URLSearchParams({
          grant_type: 'client_credentials',
          client_id: this.clientId,
          client_secret: clientSecret,
          scope: `customer:${customerId}`,
        }),
      });
    } catch {
      // Network-level failure
      throw new CommerceException(
        CommerceErrorCodes.UCP_AUTH_UNAVAILABLE,
        'UCP token endpoint is unreachable',
        HttpStatus.SERVICE_UNAVAILABLE,
      );
    }

    if (!response.ok) {
      this.logger.error(`UCP token endpoint returned HTTP ${response.status}`);
      throw new CommerceException(
        CommerceErrorCodes.UCP_AUTH_UNAVAILABLE,
        'Failed to obtain UCP access token',
        HttpStatus.SERVICE_UNAVAILABLE,
      );
    }

    const body = (await response.json()) as UcpTokenResponse;
    const { access_token, expires_in } = body;

    // Cache with TTL = expires_in - buffer (in seconds)
    const bufferSec = Math.ceil(this.refreshBufferMs / 1000);
    const ttlSec = Math.max(expires_in - bufferSec, 1);
    const expiresAt = Date.now() + expires_in * 1000;

    const cached: CachedToken = { accessToken: access_token, expiresAt };
    await this.redis.set(redisKey, JSON.stringify(cached), 'EX', ttlSec);

    this.logger.debug(`Cached UCP token for customer ${customerId}, TTL=${ttlSec}s`);
    return access_token;
  }
}
