import { Injectable, Logger } from '@nestjs/common';
import { ConfigService } from '@nestjs/config';
import { TokenExchangeService } from '../token-exchange/token-exchange.service';
import { IdempotencyService } from '../idempotency/idempotency.service';
import { RetryService } from '../retry/retry.service';
import { CircuitBreakerService } from '../circuit-breaker/circuit-breaker.service';

export interface UcpCheckoutSessionPayload {
  customerId: string;
  lineItems: Array<{
    productId: string;
    productName: string;
    quantity: number;
    unitPrice: number;
  }>;
  idempotencyKey: string;
}

export interface UcpUpdateSessionPayload {
  sessionId: string;
  customerId: string;
  shippingAddress?: Record<string, unknown>;
  paymentMethodId?: string;
  idempotencyKey: string;
}

export interface UcpCompleteSessionPayload {
  sessionId: string;
  customerId: string;
  paymentMethodId: string;
  idempotencyKey: string;
}

export interface UcpCancelSessionPayload {
  sessionId: string;
  customerId: string;
  idempotencyKey: string;
}

export interface UcpCancelOrderPayload {
  orderId: string;
  customerId: string;
  reason?: string;
  idempotencyKey: string;
}

export interface UcpReturnOrderPayload {
  orderId: string;
  customerId: string;
  reason?: string;
  idempotencyKey: string;
}

/**
 * UcpProxyService — single chokepoint for all outbound UCP API calls.
 *
 * Every method:
 *  1. Resolves a UCP access token via TokenExchangeService
 *  2. Deduplicates via IdempotencyService
 *  3. Executes through CircuitBreakerService → RetryService
 */
@Injectable()
export class UcpProxyService {
  private readonly logger = new Logger(UcpProxyService.name);
  private readonly baseUrl: string;

  constructor(
    private readonly config: ConfigService,
    private readonly tokenExchange: TokenExchangeService,
    private readonly idempotency: IdempotencyService,
    private readonly retry: RetryService,
    private readonly circuitBreaker: CircuitBreakerService,
  ) {
    this.baseUrl = config.getOrThrow<string>('UCP_BASE_URL');
  }

  // ── Checkout Session ───────────────────────────────────────────────────────

  async createCheckoutSession(payload: UcpCheckoutSessionPayload): Promise<unknown> {
    const endpoint = 'POST /checkout-sessions';
    return this.idempotency.wrap(payload.idempotencyKey, payload, () =>
      this.circuitBreaker.execute(endpoint, () =>
        this.retry.execute(async () => {
          const token = await this.tokenExchange.getToken(payload.customerId);
          return this.ucpRequest('POST', '/checkout-sessions', token, payload);
        }, endpoint),
      ),
    );
  }

  async updateCheckoutSession(payload: UcpUpdateSessionPayload): Promise<unknown> {
    const endpoint = `PATCH /checkout-sessions/${payload.sessionId}`;
    return this.idempotency.wrap(payload.idempotencyKey, payload, () =>
      this.circuitBreaker.execute(endpoint, () =>
        this.retry.execute(async () => {
          const token = await this.tokenExchange.getToken(payload.customerId);
          return this.ucpRequest('PATCH', `/checkout-sessions/${payload.sessionId}`, token, payload);
        }, endpoint),
      ),
    );
  }

  async completeCheckoutSession(payload: UcpCompleteSessionPayload): Promise<unknown> {
    const endpoint = `POST /checkout-sessions/${payload.sessionId}/complete`;
    return this.idempotency.wrap(payload.idempotencyKey, payload, () =>
      this.circuitBreaker.execute(endpoint, () =>
        this.retry.execute(async () => {
          const token = await this.tokenExchange.getToken(payload.customerId);
          return this.ucpRequest('POST', `/checkout-sessions/${payload.sessionId}/complete`, token, payload);
        }, endpoint),
      ),
    );
  }

  async cancelCheckoutSession(payload: UcpCancelSessionPayload): Promise<unknown> {
    const endpoint = `POST /checkout-sessions/${payload.sessionId}/cancel`;
    return this.idempotency.wrap(payload.idempotencyKey, payload, () =>
      this.circuitBreaker.execute(endpoint, () =>
        this.retry.execute(async () => {
          const token = await this.tokenExchange.getToken(payload.customerId);
          return this.ucpRequest('POST', `/checkout-sessions/${payload.sessionId}/cancel`, token, payload);
        }, endpoint),
      ),
    );
  }

  async getCheckoutSession(customerId: string, sessionId: string): Promise<unknown> {
    const endpoint = `GET /checkout-sessions/${sessionId}`;
    return this.circuitBreaker.execute(endpoint, () =>
      this.retry.execute(async () => {
        const token = await this.tokenExchange.getToken(customerId);
        return this.ucpRequest('GET', `/checkout-sessions/${sessionId}`, token);
      }, endpoint),
    );
  }

  // ── Orders ─────────────────────────────────────────────────────────────────

  async cancelOrder(payload: UcpCancelOrderPayload): Promise<unknown> {
    const endpoint = `POST /orders/${payload.orderId}/cancel`;
    return this.idempotency.wrap(payload.idempotencyKey, payload, () =>
      this.circuitBreaker.execute(endpoint, () =>
        this.retry.execute(async () => {
          const token = await this.tokenExchange.getToken(payload.customerId);
          return this.ucpRequest('POST', `/orders/${payload.orderId}/cancel`, token, payload);
        }, endpoint),
      ),
    );
  }

  async returnOrder(payload: UcpReturnOrderPayload): Promise<unknown> {
    const endpoint = `POST /orders/${payload.orderId}/return`;
    return this.idempotency.wrap(payload.idempotencyKey, payload, () =>
      this.circuitBreaker.execute(endpoint, () =>
        this.retry.execute(async () => {
          const token = await this.tokenExchange.getToken(payload.customerId);
          return this.ucpRequest('POST', `/orders/${payload.orderId}/return`, token, payload);
        }, endpoint),
      ),
    );
  }

  // ── Private ────────────────────────────────────────────────────────────────

  private async ucpRequest(
    method: string,
    path: string,
    token: string,
    body?: unknown,
  ): Promise<unknown> {
    const url = `${this.baseUrl}${path}`;
    const init: RequestInit = {
      method,
      headers: {
        Authorization: `Bearer ${token}`,
        'Content-Type': 'application/json',
        Accept: 'application/json',
      },
    };

    if (body && method !== 'GET') {
      init.body = JSON.stringify(body);
    }

    const response = await fetch(url, init);

    if (!response.ok) {
      const err = new Error(`UCP ${method} ${path} returned HTTP ${response.status}`) as Error & { status: number };
      err.status = response.status;
      throw err;
    }

    return response.json();
  }
}
