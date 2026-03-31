import { Module } from '@nestjs/common';
import { MerchantProfileService } from './merchant-profile/merchant-profile.service';
import { RequestSigningService } from './signing/request-signing.service';
import { WebhookVerificationService } from './verification/webhook-verification.service';
import { IdempotencyService } from './idempotency/idempotency.service';
import { RetryService } from './retry/retry.service';
import { CircuitBreakerService } from './circuit-breaker/circuit-breaker.service';
import { UcpCheckoutClient } from './checkout-client/ucp-checkout.client';

/**
 * UcpClientModule — single chokepoint for all outbound UCP calls.
 *
 * Provides and exports:
 *  - MerchantProfileService   (/.well-known/ucp discovery + Redis cache)
 *  - RequestSigningService    (detached JWT signing for outbound requests)
 *  - WebhookVerificationService (detached JWT verification for inbound webhooks)
 *  - IdempotencyService       (24-hour Redis dedup for mutating calls)
 *  - RetryService             (exponential backoff + jitter)
 *  - CircuitBreakerService    (per-endpoint circuit breaker in Redis)
 *  - UcpCheckoutClient        (5 UCP checkout REST operations)
 *
 * Import this module into CheckoutModule and OrderModule.
 * The REDIS_CLIENT token is provided by AppModule's RedisProvider (global).
 */
@Module({
  providers: [
    MerchantProfileService,
    RequestSigningService,
    WebhookVerificationService,
    IdempotencyService,
    RetryService,
    CircuitBreakerService,
    UcpCheckoutClient,
  ],
  exports: [
    MerchantProfileService,
    RequestSigningService,
    WebhookVerificationService,
    IdempotencyService,
    RetryService,
    CircuitBreakerService,
    UcpCheckoutClient,
  ],
})
export class UcpClientModule {}
