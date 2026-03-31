import { Controller, Get } from '@nestjs/common';
import { HealthService } from './health.service';

@Controller('health')
export class HealthController {
  constructor(private readonly healthService: HealthService) {}

  /** GET /commerce/health */
  @Get()
  async check() {
    const [postgres, redis, ucp] = await Promise.all([
      this.healthService.checkPostgres(),
      this.healthService.checkRedis(),
      this.healthService.checkUcp(),
    ]);

    const allUp = postgres && redis && ucp;
    const status = allUp ? 'ok' : 'degraded';

    return {
      service: 'checkout-order-service',
      version: process.env.npm_package_version ?? '1.0.0',
      status,
      dependencies: {
        postgres: postgres ? 'up' : 'down',
        redis: redis ? 'up' : 'down',
        ucp: ucp ? 'up' : 'down',
      },
      timestamp: new Date().toISOString(),
    };
  }
}
