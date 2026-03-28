import { Injectable, Inject } from '@nestjs/common';
import { ConfigService } from '@nestjs/config';
import { InjectDataSource } from '@nestjs/typeorm';
import { DataSource } from 'typeorm';
import { REDIS_CLIENT } from '../redis.provider';
import Redis from 'ioredis';
import * as https from 'https';
import * as http from 'http';

@Injectable()
export class HealthService {
  constructor(
    @InjectDataSource() private readonly dataSource: DataSource,
    @Inject(REDIS_CLIENT) private readonly redis: Redis,
    private readonly config: ConfigService,
  ) {}

  async checkPostgres(): Promise<boolean> {
    try {
      await this.dataSource.query('SELECT 1');
      return true;
    } catch {
      return false;
    }
  }

  async checkRedis(): Promise<boolean> {
    try {
      const result = await this.redis.ping();
      return result === 'PONG';
    } catch {
      return false;
    }
  }

  /** Probe the UCP well-known URL with a short timeout. */
  async checkUcp(): Promise<boolean> {
    const ucpUrl = this.config.get<string>(
      'UCP_WELL_KNOWN_URL',
      'https://ucp.example.com/.well-known/ucp',
    );

    return new Promise((resolve) => {
      const timeout = setTimeout(() => resolve(false), 3000);
      const lib = ucpUrl.startsWith('https') ? https : http;

      const req = lib.get(ucpUrl, (res) => {
        clearTimeout(timeout);
        resolve(res.statusCode !== undefined && res.statusCode < 500);
        res.resume();
      });

      req.on('error', () => {
        clearTimeout(timeout);
        resolve(false);
      });

      req.setTimeout(3000, () => {
        clearTimeout(timeout);
        req.destroy();
        resolve(false);
      });
    });
  }
}
