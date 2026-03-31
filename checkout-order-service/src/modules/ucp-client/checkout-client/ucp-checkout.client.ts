import { Injectable, Logger } from '@nestjs/common';
import { ConfigService } from '@nestjs/config';
import { randomUUID } from 'crypto';
import { MerchantProfileService } from '../merchant-profile/merchant-profile.service';
import { RequestSigningService } from '../signing/request-signing.service';
import { IdempotencyService } from '../idempotency/idempotency.service';
import { RetryService } from '../retry/retry.service';
import { CircuitBreakerService } from '../circuit-breaker/circuit-breaker.service';
import type { UcpLineItem, UcpBuyer, UcpContext } from '../../../shared/types/ucp-types.interface';

export interface CreateCheckoutSessionPayload {
  line_items: UcpLineItem[];
  buyer?: UcpBuyer;
  context?: UcpContext;
}

export interface UpdateCheckoutSessionPayload {
  line_items: UcpLineItem[];
  buyer?: UcpBuyer;
  context?: UcpContext;
}

export interface CompleteCheckoutSessionPayload {
  payment_instrument: unknown;
}

export interface UcpCheckoutSessionResponse {
  id: string;
  status: string;
  continue_url?: string;
  expires_at?: string;
  line_items?: UcpLineItem[];
  buyer?: UcpBuyer;
  context?: UcpContext;
  payment_handlers?: string[];
  totals?: {
    subtotal_cents: number;
    tax_cents: number;
    grand_total_cents: number;
  };
  order?: {
    id: string;
    permalink_url?: string;
  };
  messages?: unknown[];
  [key: string]: unknown;
}

/**
 * UcpCheckoutClient — wraps all five UCP checkout REST operations.
 *
 * Each method builds required UCP REST Binding headers:
 *  - UCP-Agent: profile="..."
 *  - Idempotency-Key (mutating ops)
 *  - Request-Signature (detached JWT via RequestSigningService)
 *  - Request-Id
 *
 * All calls are routed through IdempotencyService, RetryService, and CircuitBreakerService.
 */
@Injectable()
export class UcpCheckoutClient {
  private readonly logger = new Logger(UcpCheckoutClient.name);
  private readonly platformAgentProfile: string;

  constructor(
    private readonly merchantProfileService: MerchantProfileService,
    private readonly signingService: RequestSigningService,
    private readonly idempotencyService: IdempotencyService,
    private readonly retryService: RetryService,
    private readonly circuitBreakerService: CircuitBreakerService,
    config: ConfigService,
  ) {
    this.platformAgentProfile = config.get<string>(
      'PLATFORM_UCP_AGENT_PROFILE',
      'https://platform.example.com/.well-known/ucp',
    );
  }

  /** POST /checkout-sessions — Create a new checkout session */
  async createCheckoutSession(
    merchantId: string,
    payload: CreateCheckoutSessionPayload,
    idempotencyKey: string,
  ): Promise<UcpCheckoutSessionResponse> {
    const baseUrl = await this.merchantProfileService.getCheckoutBaseUrl(merchantId);
    const url = `${baseUrl}/checkout-sessions`;
    const endpoint = `${merchantId}:POST:/checkout-sessions`;

    return this.idempotencyService.wrap(idempotencyKey, payload, () =>
      this.circuitBreakerService.execute(endpoint, () =>
        this.retryService.execute(
          () => this.request('POST', url, payload),
          endpoint,
        ),
      ),
    );
  }

  /** GET /checkout-sessions/{id} — Retrieve a checkout session */
  async getCheckoutSession(
    merchantId: string,
    sessionId: string,
  ): Promise<UcpCheckoutSessionResponse> {
    const baseUrl = await this.merchantProfileService.getCheckoutBaseUrl(merchantId);
    const url = `${baseUrl}/checkout-sessions/${sessionId}`;
    const endpoint = `${merchantId}:GET:/checkout-sessions/${sessionId}`;

    return this.circuitBreakerService.execute(endpoint, () =>
      this.retryService.execute(
        () => this.request('GET', url, undefined),
        endpoint,
      ),
    );
  }

  /** PUT /checkout-sessions/{id} — Update a checkout session (full replacement) */
  async updateCheckoutSession(
    merchantId: string,
    sessionId: string,
    payload: UpdateCheckoutSessionPayload,
    idempotencyKey: string,
  ): Promise<UcpCheckoutSessionResponse> {
    const baseUrl = await this.merchantProfileService.getCheckoutBaseUrl(merchantId);
    const url = `${baseUrl}/checkout-sessions/${sessionId}`;
    const endpoint = `${merchantId}:PUT:/checkout-sessions/${sessionId}`;

    return this.idempotencyService.wrap(idempotencyKey, payload, () =>
      this.circuitBreakerService.execute(endpoint, () =>
        this.retryService.execute(
          () => this.request('PUT', url, payload),
          endpoint,
        ),
      ),
    );
  }

  /** POST /checkout-sessions/{id}/complete — Complete a checkout session */
  async completeCheckoutSession(
    merchantId: string,
    sessionId: string,
    payload: CompleteCheckoutSessionPayload,
    idempotencyKey: string,
  ): Promise<UcpCheckoutSessionResponse> {
    const baseUrl = await this.merchantProfileService.getCheckoutBaseUrl(merchantId);
    const url = `${baseUrl}/checkout-sessions/${sessionId}/complete`;
    const endpoint = `${merchantId}:POST:/checkout-sessions/${sessionId}/complete`;

    return this.idempotencyService.wrap(idempotencyKey, payload, () =>
      this.circuitBreakerService.execute(endpoint, () =>
        this.retryService.execute(
          () => this.request('POST', url, payload),
          endpoint,
        ),
      ),
    );
  }

  /** POST /checkout-sessions/{id}/cancel — Cancel a checkout session */
  async cancelCheckoutSession(
    merchantId: string,
    sessionId: string,
    idempotencyKey: string,
  ): Promise<UcpCheckoutSessionResponse> {
    const baseUrl = await this.merchantProfileService.getCheckoutBaseUrl(merchantId);
    const url = `${baseUrl}/checkout-sessions/${sessionId}/cancel`;
    const endpoint = `${merchantId}:POST:/checkout-sessions/${sessionId}/cancel`;
    const payload = {};

    return this.idempotencyService.wrap(idempotencyKey, payload, () =>
      this.circuitBreakerService.execute(endpoint, () =>
        this.retryService.execute(
          () => this.request('POST', url, payload),
          endpoint,
        ),
      ),
    );
  }

  // ── Private ────────────────────────────────────────────────────────────────

  private async request<T>(
    method: 'GET' | 'POST' | 'PUT',
    url: string,
    body: unknown,
  ): Promise<T> {
    const requestId = randomUUID();
    const bodyBuffer = body !== undefined ? Buffer.from(JSON.stringify(body)) : Buffer.alloc(0);

    const signature = await this.signingService.signRequest(bodyBuffer);

    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
      'UCP-Agent': `profile="${this.platformAgentProfile}"`,
      'Request-Id': requestId,
      'Request-Signature': signature,
    };

    const fetchOptions: RequestInit = {
      method,
      headers,
      signal: AbortSignal.timeout(10_000),
    };

    if (method !== 'GET' && body !== undefined) {
      fetchOptions.body = bodyBuffer;
    }

    this.logger.debug(`${method} ${url} request-id=${requestId}`);

    const res = await fetch(url, fetchOptions);

    if (!res.ok) {
      const errBody = await res.text().catch(() => '');
      const err = Object.assign(new Error(`UCP ${method} ${url} → HTTP ${res.status}: ${errBody}`), {
        status: res.status,
      });
      throw err;
    }

    return res.json() as Promise<T>;
  }
}
