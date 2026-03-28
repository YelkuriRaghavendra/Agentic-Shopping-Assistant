import { Module } from '@nestjs/common';
import { ConfigModule, ConfigService } from '@nestjs/config';
import { TypeOrmModule } from '@nestjs/typeorm';
import { BullModule } from '@nestjs/bull';
import { TerminusModule } from '@nestjs/terminus';
import { RedisProvider } from './redis.provider';
import { HealthController } from './health/health.controller';
import { HealthService } from './health/health.service';
import { UcpGatewayModule } from './modules/ucp-gateway/ucp-gateway.module';

@Module({
  imports: [
    ConfigModule.forRoot({
      isGlobal: true,
      envFilePath: '.env',
    }),

    // TypeORM — single connection, entities registered per module
    TypeOrmModule.forRootAsync({
      inject: [ConfigService],
      useFactory: (config: ConfigService) => {
        const url = config.getOrThrow<string>('DATABASE_URL');
        return {
          type: 'postgres',
          url,
          synchronize: false,
          migrationsRun: false,
          logging: config.get('NODE_ENV') !== 'production',
          autoLoadEntities: true,
          ssl:
            config.get('NODE_ENV') === 'production'
              ? { rejectUnauthorized: false }
              : false,
        };
      },
    }),

    // BullMQ queues
    BullModule.forRootAsync({
      inject: [ConfigService],
      useFactory: (config: ConfigService): any => ({
        redis: {
          host: config.get<string>('REDIS_HOST', 'localhost'),
          port: config.get<number>('REDIS_PORT', 6379),
          password: config.get<string>('REDIS_PASSWORD') || undefined,
        },
      }),
    }),
    BullModule.registerQueue(
      { name: 'order-events' },
      { name: 'webhook-ingestion' },
    ),

    TerminusModule,
    UcpGatewayModule,
  ],
  controllers: [HealthController],
  providers: [RedisProvider, HealthService],
  exports: [RedisProvider],
})
export class AppModule {}
