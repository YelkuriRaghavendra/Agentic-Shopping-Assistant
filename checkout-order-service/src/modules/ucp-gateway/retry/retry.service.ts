import { Injectable, Logger } from '@nestjs/common';

const MAX_RETRIES = 3;
const BASE_DELAY_MS = 200;

// HTTP status codes considered transient (safe to retry)
const TRANSIENT_STATUS_CODES = new Set([429, 500, 502, 503, 504]);

/**
 * RetryService — executes an async operation with exponential backoff + jitter.
 * Retries up to MAX_RETRIES times on transient errors (429, 5xx, network timeouts).
 */
@Injectable()
export class RetryService {
  private readonly logger = new Logger(RetryService.name);

  /**
   * Executes `operation` with retry logic.
   * Throws the last error if all retries are exhausted.
   *
   * @param operation  Async function to execute; should throw on failure
   * @param context    Label used in log messages (e.g. "POST /checkout-sessions")
   */
  async execute<T>(operation: () => Promise<T>, context = 'ucp-call'): Promise<T> {
    let lastError: unknown;

    for (let attempt = 0; attempt <= MAX_RETRIES; attempt++) {
      try {
        return await operation();
      } catch (err) {
        lastError = err;

        if (!this.isTransient(err) || attempt === MAX_RETRIES) {
          throw err;
        }

        const delay = this.backoffMs(attempt);
        this.logger.warn(
          `[${context}] attempt ${attempt + 1}/${MAX_RETRIES} failed — retrying in ${delay}ms`,
        );
        await this.sleep(delay);
      }
    }

    throw lastError;
  }

  // ── Private ────────────────────────────────────────────────────────────────

  private isTransient(err: unknown): boolean {
    if (err instanceof Error) {
      // Network-level errors (fetch throws TypeError on network failure)
      if (err.name === 'TypeError' || err.message.includes('fetch')) return true;
      // Timeout
      if (err.name === 'AbortError') return true;
    }
    // HTTP status-based transient check
    const status = (err as { status?: number })?.status;
    if (status && TRANSIENT_STATUS_CODES.has(status)) return true;
    return false;
  }

  /** Exponential backoff with full jitter: random(0, base * 2^attempt) */
  private backoffMs(attempt: number): number {
    const cap = BASE_DELAY_MS * Math.pow(2, attempt);
    return Math.floor(Math.random() * cap);
  }

  private sleep(ms: number): Promise<void> {
    return new Promise((resolve) => setTimeout(resolve, ms));
  }
}
