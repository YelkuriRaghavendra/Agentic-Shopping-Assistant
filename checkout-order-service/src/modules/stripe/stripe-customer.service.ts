import { Injectable, Logger, Inject } from '@nestjs/common';
import Stripe from 'stripe';
import { STRIPE_CLIENT } from './stripe.provider';

@Injectable()
export class StripeCustomerService {
  private readonly logger = new Logger(StripeCustomerService.name);

  constructor(@Inject(STRIPE_CLIENT) private readonly stripe: Stripe) {}

  /**
   * Get or create a Stripe Customer for our internal customer ID.
   * Uses metadata.internal_customer_id to link.
   */
  async getOrCreateCustomer(customerId: string): Promise<string> {
    const existing = await this.stripe.customers.search({
      query: `metadata['internal_customer_id']:'${customerId}'`,
      limit: 1,
    });

    if (existing.data.length > 0) {
      return existing.data[0].id;
    }

    const customer = await this.stripe.customers.create({
      metadata: { internal_customer_id: customerId },
    });
    this.logger.log(`Created Stripe customer ${customer.id} for ${customerId}`);
    return customer.id;
  }

  /**
   * Create a SetupIntent for saving a card.
   */
  async createSetupIntent(customerId: string): Promise<{ clientSecret: string }> {
    const stripeCustomerId = await this.getOrCreateCustomer(customerId);
    const setupIntent = await this.stripe.setupIntents.create({
      customer: stripeCustomerId,
      payment_method_types: ['card'],
      metadata: { internal_customer_id: customerId },
    });

    return { clientSecret: setupIntent.client_secret! };
  }

  /**
   * List saved payment methods for a customer.
   */
  async listPaymentMethods(
    customerId: string,
  ): Promise<{ paymentMethods: Array<Record<string, unknown>> }> {
    const stripeCustomerId = await this.getOrCreateCustomer(customerId);
    const methods = await this.stripe.paymentMethods.list({
      customer: stripeCustomerId,
      type: 'card',
    });

    return {
      paymentMethods: methods.data.map((pm) => ({
        id: pm.id,
        type: pm.type,
        brand: pm.card?.brand ?? 'unknown',
        last4: pm.card?.last4 ?? '****',
        exp_month: pm.card?.exp_month,
        exp_year: pm.card?.exp_year,
        is_default: false,
      })),
    };
  }

  /**
   * Charge a saved payment method off-session.
   */
  async chargeSavedCard(
    amountCents: number,
    paymentMethodId: string,
    customerId: string,
    metadata: Record<string, string>,
  ): Promise<Stripe.PaymentIntent> {
    const stripeCustomerId = await this.getOrCreateCustomer(customerId);

    const paymentIntent = await this.stripe.paymentIntents.create({
      amount: amountCents,
      currency: 'inr',
      customer: stripeCustomerId,
      payment_method: paymentMethodId,
      off_session: true,
      confirm: true,
      metadata,
    });

    return paymentIntent;
  }
}
