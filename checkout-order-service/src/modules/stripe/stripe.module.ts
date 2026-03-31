import { Global, Module } from '@nestjs/common';
import { ConfigModule } from '@nestjs/config';
import { stripeProvider } from './stripe.provider';
import { StripeWebhookController } from './stripe-webhook.controller';
import { CheckoutModule } from '../checkout/checkout.module';

@Global()
@Module({
  imports: [ConfigModule, CheckoutModule],
  controllers: [StripeWebhookController],
  providers: [stripeProvider],
  exports: [stripeProvider],
})
export class StripeModule {}
