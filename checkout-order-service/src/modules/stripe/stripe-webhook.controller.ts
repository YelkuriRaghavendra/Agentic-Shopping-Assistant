import {
  Controller,
  Post,
  Req,
  Res,
  Headers,
  Inject,
  Logger,
  HttpStatus,
} from '@nestjs/common';
import { RawBodyRequest } from '@nestjs/common';
import { ConfigService } from '@nestjs/config';
import { Request, Response } from 'express';
import Stripe from 'stripe';
import { STRIPE_CLIENT } from './stripe.provider';
import { CheckoutSessionService } from '../checkout/session/checkout-session.service';

/**
 * StripeWebhookController — receives and verifies Stripe webhook events.
 *
 * POST /stripe/webhooks
 *   - Verifies Stripe-Signature header using STRIPE_WEBHOOK_SECRET
 *   - On payment_intent.succeeded: marks session COMPLETED and enqueues order.confirmed
 *   - On payment_intent.payment_failed: marks session PAYMENT_FAILED
 *   - All other event types: returns 200 immediately
 *   - Signature failure: returns 400
 *
 * Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 5.6, 5.7
 */
@Controller('stripe')
export class StripeWebhookController {
  private readonly logger = new Logger(StripeWebhookController.name);

  constructor(
    @Inject(STRIPE_CLIENT)
    private readonly stripe: Stripe,
    private readonly checkoutSessionService: CheckoutSessionService,
    private readonly configService: ConfigService,
  ) {}

  @Post('webhooks')
  async handleWebhook(
    @Req() req: RawBodyRequest<Request>,
    @Res() res: Response,
    @Headers('stripe-signature') sig: string,
  ): Promise<void> {
    const rawBody: Buffer = req.rawBody ?? Buffer.from(JSON.stringify(req.body));
    const webhookSecret = this.configService.get<string>('STRIPE_WEBHOOK_SECRET') ?? '';

    let event: Stripe.Event;

    try {
      event = this.stripe.webhooks.constructEvent(rawBody, sig, webhookSecret);
    } catch (err) {
      this.logger.warn(`Stripe webhook signature verification failed: ${(err as Error).message}`);
      res.status(HttpStatus.BAD_REQUEST).json({ error: 'Invalid webhook signature' });
      return;
    }

    switch (event.type) {
      case 'payment_intent.succeeded': {
        const paymentIntent = event.data.object as Stripe.PaymentIntent;
        await this.checkoutSessionService.handlePaymentSucceeded(paymentIntent.id);
        break;
      }

      case 'payment_intent.payment_failed': {
        const paymentIntent = event.data.object as Stripe.PaymentIntent;
        const reason = paymentIntent.last_payment_error?.message ?? null;
        await this.checkoutSessionService.handlePaymentFailed(paymentIntent.id, reason);
        break;
      }

      default:
        // Unrecognised event type — acknowledge without processing (Req 5.6)
        break;
    }

    // Return 200 for all successfully verified events (Req 5.7)
    res.status(HttpStatus.OK).json({ received: true });
  }
}
