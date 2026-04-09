import { Global, Module } from '@nestjs/common';
import { ConfigModule } from '@nestjs/config';
import { stripeProvider } from './stripe.provider';
import { StripeWebhookController } from './stripe-webhook.controller';
import { StripeCustomerController } from './stripe-customer.controller';
import { StripeCustomerService } from './stripe-customer.service';
import { CheckoutModule } from '../checkout/checkout.module';

@Global()
@Module({
  imports: [ConfigModule, CheckoutModule],
  controllers: [StripeWebhookController, StripeCustomerController],
  providers: [stripeProvider, StripeCustomerService],
  exports: [stripeProvider, StripeCustomerService],
})
export class StripeModule {}
