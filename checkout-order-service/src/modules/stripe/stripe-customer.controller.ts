import { Controller, Post, Get, Param, HttpCode, HttpStatus } from '@nestjs/common';
import { StripeCustomerService } from './stripe-customer.service';

@Controller('commerce/customers')
export class StripeCustomerController {
  constructor(private readonly stripeCustomerService: StripeCustomerService) {}

  /** POST /commerce/customers/:customerId/setup-intent — create SetupIntent for card save */
  @Post(':customerId/setup-intent')
  @HttpCode(HttpStatus.OK)
  async createSetupIntent(
    @Param('customerId') customerId: string,
  ): Promise<{ clientSecret: string }> {
    return this.stripeCustomerService.createSetupIntent(customerId);
  }

  /** GET /commerce/customers/:customerId/payment-methods — list saved cards */
  @Get(':customerId/payment-methods')
  async listPaymentMethods(
    @Param('customerId') customerId: string,
  ): Promise<{ paymentMethods: Array<Record<string, unknown>> }> {
    return this.stripeCustomerService.listPaymentMethods(customerId);
  }
}
