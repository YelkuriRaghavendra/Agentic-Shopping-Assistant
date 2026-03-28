import { HttpStatus, Inject, Injectable, Logger } from '@nestjs/common';
import Redis from 'ioredis';
import { REDIS_CLIENT } from '../../../redis.provider';
import { CommerceErrorCodes, CommerceException } from '../../../shared/errors/commerce.exception';

type CircuitState = 'CLOSED' | 'OPEN' | 'HALF_OPEN';

interface CircuitRecord {
  state: CircuitState;
  failures: number;
  openedAt?: number; // unix ms
}

const FAILURE_THRESHOLD = 3;
const HALF_OPEN_PROBE_MS = 60_000; // 60 seconds
const CIRCUIT_TTL_SECONDS = 300;   // Redis key TTL — auto-cleanup after 5 min of inactivity

/**
 * CircuitBreakerService — per-endpoint circuit breaker persisted in Redis.
 * Redis key pattern: circuit:{merchant_id}:{endpoint}
 *
 * States:
 *  CLOSED    — normal operation; failures are counted
 *  OPEN      — requests are rejected immediately with ucp_unavailable (503)
 *  HALF_OPEN — one probe request is allowed; success → CLOSED, failure → OPEN
 */
@Injectable()
export class CircuitBreakerService {
  private readonly logger = new Logger(CircuitBreakerService.name);

  constructor(@Inject(REDIS_CLIENT) private readonly redis: Redis) {}

  /**
   * Executes `operation` through the circuit breaker for the given endpoint.
   * Throws CommerceException(ucp_unavailable) when the circuit is OPEN.
   *
   * @param endpoint  Identifies the circuit (e.g. "{merchant_id}:{path}")
   * @param operation The async operation to execute
   */
  async execute<T>(endpoint: string, operation: () => Promise<T>): Promise<T> {
    const record = await this.getRecord(endpoint);

    if (record.state === 'OPEN') {
      const elapsed = Date.now() - (record.openedAt ?? 0);
      if (elapsed < HALF_OPEN_PROBE_MS) {
        throw new CommerceException(
          CommerceErrorCodes.UCP_UNAVAILABLE,
          `UCP is currently unavailable (circuit open for ${endpoint})`,
          HttpStatus.SERVICE_UNAVAILABLE,
        );
      }
      // Transition to HALF_OPEN for probe
      await this.setState(endpoint, { ...record, state: 'HALF_OPEN' });
    }

    try {
      const result = await operation();
      await this.onSuccess(endpoint);
      return result;
    } catch (err) {
      await this.onFailure(endpoint, record);
      throw err;
    }
  }

  // ── Private ────────────────────────────────────────────────────────────────

  async getRecord(endpoint: string): Promise<CircuitRecord> {
    const key = `circuit:${endpoint}`;
    const raw = await this.redis.get(key);
    if (!raw) return { state: 'CLOSED', failures: 0 };
    return JSON.parse(raw) as CircuitRecord;
  }

  async setState(endpoint: string, record: CircuitRecord): Promise<void> {
    const key = `circuit:${endpoint}`;
    await this.redis.set(key, JSON.stringify(record), 'EX', CIRCUIT_TTL_SECONDS);
  }

  private async onSuccess(endpoint: string): Promise<void> {
    const record = await this.getRecord(endpoint);
    if (record.state !== 'CLOSED' || record.failures > 0) {
      this.logger.log(`Circuit CLOSED for ${endpoint}`);
      await this.setState(endpoint, { state: 'CLOSED', failures: 0 });
    }
  }

  private async onFailure(endpoint: string, current: CircuitRecord): Promise<void> {
    const failures = current.failures + 1;

    if (failures >= FAILURE_THRESHOLD) {
      this.logger.warn(`Circuit OPEN for ${endpoint} after ${failures} failures`);
      await this.setState(endpoint, {
        state: 'OPEN',
        failures,
        openedAt: Date.now(),
      });
    } else {
      await this.setState(endpoint, { ...current, state: 'CLOSED', failures });
    }
  }
}
