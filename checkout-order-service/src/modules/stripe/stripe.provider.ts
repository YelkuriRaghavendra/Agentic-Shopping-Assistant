import { FactoryProvider } from '@nestjs/common';
import { ConfigService } from '@nestjs/config';
import Stripe from 'stripe';

export const STRIPE_CLIENT = 'STRIPE_CLIENT';

export const stripeProvider: FactoryProvider = {
  provide: STRIPE_CLIENT,
  useFactory: (config: ConfigService) => {
    const key = config.get<string>('STRIPE_SECRET_KEY');
    if (!key) throw new Error('STRIPE_SECRET_KEY is required');
    return new Stripe(key, { apiVersion: '2026-03-25.dahlia' });
  },
  inject: [ConfigService],
};
