import { Module } from '@nestjs/common';
import { VaultService } from './vault/vault.service';
import { TokenExchangeService } from './token-exchange/token-exchange.service';
import { IdempotencyService } from './idempotency/idempotency.service';
import { RetryService } from './retry/retry.service';
import { CircuitBreakerService } from './circuit-breaker/circuit-breaker.service';
import { UcpProxyService } from './proxy/ucp-proxy.service';

@Module({
  providers: [
    VaultService,
    TokenExchangeService,
    IdempotencyService,
    RetryService,
    CircuitBreakerService,
    UcpProxyService,
  ],
  exports: [
    VaultService,
    TokenExchangeService,
    IdempotencyService,
    RetryService,
    CircuitBreakerService,
    UcpProxyService,
  ],
})
export class UcpGatewayModule {}
