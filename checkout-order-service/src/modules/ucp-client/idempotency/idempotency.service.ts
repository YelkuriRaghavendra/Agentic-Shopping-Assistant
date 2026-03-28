import { HttpStatus, Inject, Injectable, Logger } from '@nestjs/common';
import { ConfigService } from '@nestjs/config';
import Redis from 'ioredis';
import * as crypto from 'crypto';
import { REDIS_CLIENT } from '../../../redis.provider';
import { CommerceErrorCodes, CommerceException } from '../../../shared/errors/commerce.exception';

interface IdempotencyRecord {
  payloadHash: string;
  response: unknown;
  createdAt: string;
}

const DEFAULT_TTL_SECONDS = 86400; // 24 hours

/**
 * IdempotencyService — deduplicates mutating UCP calls within a 24-hour window.
 *
 * - Same key + same payload → return cached response (no UCP call)
 * - Same key + different payload → throw 409 idempotency_conflict
 * - New key → execute the operation and cache the result
 */
@Injectable()
export class IdempotencyService {
  private readonly logger = new Logger(IdempotencyService.name);
  private readonly ttlSeconds: number;

  constructor(
    @Inject(REDIS_CLIENT) private readonly redis: Redis,
    config: ConfigService,
  ) {
    this.ttlSeconds = config.get<number>('IDEMPOTENCY_TTL_SECONDS', DEFAULT_TTL_SECONDS);
  }

  /**
   * Wraps an operation with idempotency protection.
   *
   * @param key       Client-supplied idempotency key
   * @param payload   The request payload (used for conflict detection)
   * @param operation The async operation to execute on a cache miss
   * @returns         Cached or freshly computed response
   */
  async wrap<T>(
    key: string,
    payload: unknown,
    operation: () => Promise<T>,
  ): Promise<T> {
    const redisKey = `idempotency:${key}`;
    const incomingHash = this.hash(payload);

    const existing = await this.redis.get(redisKey);
    if (existing) {
      const record: IdempotencyRecord = JSON.parse(existing);

      if (record.payloadHash !== incomingHash) {
        this.logger.warn(`Idempotency conflict for key=${key}`);
        throw new CommerceException(
          CommerceErrorCodes.IDEMPOTENCY_CONFLICT,
          'A different request was already submitted with this idempotency key',
          HttpStatus.CONFLICT,
        );
      }

      this.logger.debug(`Idempotency cache hit for key=${key}`);
      return record.response as T;
    }

    // Cache miss — execute the operation
    const result = await operation();

    const record: IdempotencyRecord = {
      payloadHash: incomingHash,
      response: result,
      createdAt: new Date().toISOString(),
    };
    await this.redis.set(redisKey, JSON.stringify(record), 'EX', this.ttlSeconds);

    return result;
  }

  // ── Private ────────────────────────────────────────────────────────────────

  private hash(payload: unknown): string {
    return crypto
      .createHash('sha256')
      .update(JSON.stringify(payload))
      .digest('hex');
  }
}
