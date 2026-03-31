import {
  Controller,
  Post,
  Get,
  Put,
  Param,
  Body,
  Res,
  UsePipes,
  ValidationPipe,
  HttpCode,
  HttpStatus,
} from '@nestjs/common';
import type { Response } from 'express';
import { CheckoutSessionService } from './checkout-session.service';
import { CreateCheckoutSessionDto } from './dto/create-checkout-session.dto';
import { UpdateCheckoutSessionDto } from './dto/update-checkout-session.dto';
import { CompleteCheckoutSessionDto } from './dto/complete-checkout-session.dto';
import type { CheckoutSession } from './checkout-session.entity';
import type { UcpTotals } from '../../../shared/types/ucp-types.interface';

interface SummaryResponse {
  subtotal: string;
  discount: string;
  tax: string;
  grand_total: string;
  currency: string;
}

function centsToDisplay(cents: number): string {
  return (cents / 100).toFixed(2);
}

@Controller('commerce/checkout/sessions')
@UsePipes(new ValidationPipe({ transform: true, whitelist: true }))
export class CheckoutController {
  constructor(private readonly checkoutSessionService: CheckoutSessionService) {}

  /** POST /commerce/checkout/sessions — create a new checkout session */
  @Post()
  async createSession(@Body() dto: CreateCheckoutSessionDto): Promise<CheckoutSession> {
    // Use configured default merchant if none provided (local dev / single-merchant setup)
    const merchantId = dto.merchant_id ?? process.env.DEFAULT_MERCHANT_ID ?? 'default-merchant';
    return this.checkoutSessionService.createSession(
      merchantId,
      dto.customer_id,
      dto.line_items,
      dto.buyer,
      dto.context,
    );
  }

  /** GET /commerce/checkout/sessions/:id — return local session state */
  @Get(':id')
  async getSession(@Param('id') id: string): Promise<CheckoutSession> {
    return this.checkoutSessionService.getSession(id);
  }

  /** PUT /commerce/checkout/sessions/:id — full replacement update */
  @Put(':id')
  async updateSession(
    @Param('id') id: string,
    @Body() dto: UpdateCheckoutSessionDto,
  ): Promise<CheckoutSession> {
    return this.checkoutSessionService.updateSession(id, dto.line_items, dto.buyer, dto.context);
  }

  /** POST /commerce/checkout/sessions/:id/complete — trigger Complete Checkout */
  @Post(':id/complete')
  @HttpCode(HttpStatus.OK)
  async completeSession(
    @Param('id') id: string,
    @Body() dto: CompleteCheckoutSessionDto,
  ): Promise<CheckoutSession> {
    return this.checkoutSessionService.completeSession(id, dto.payment_instrument);
  }

  /** POST /commerce/checkout-sessions/:id/payment-intent — create or return existing Stripe PaymentIntent */
  @Post(':id/payment-intent')
  @HttpCode(HttpStatus.OK)
  async createPaymentIntent(
    @Param('id') id: string,
  ): Promise<{ client_secret: string; payment_intent_id: string }> {
    return this.checkoutSessionService.createOrGetPaymentIntent(id);
  }

  /** POST /commerce/checkout/sessions/:id/payment-link — create a Stripe Payment Link */
  @Post(':id/payment-link')
  @HttpCode(HttpStatus.OK)
  async createPaymentLink(
    @Param('id') id: string,
  ): Promise<{ url: string }> {
    return this.checkoutSessionService.createPaymentLink(id);
  }

  /** POST /commerce/checkout/sessions/:id/cancel — cancel session */
  @Post(':id/cancel')
  @HttpCode(HttpStatus.OK)
  async cancelSession(@Param('id') id: string): Promise<CheckoutSession> {
    return this.checkoutSessionService.cancelSession(id);
  }

  /** GET /commerce/checkout/sessions/:id/summary — returns totals as JSON */
  @Get(':id/summary')
  async getSessionSummary(@Param('id') id: string): Promise<SummaryResponse> {
    const session = await this.checkoutSessionService.getSession(id);
    const totals: UcpTotals | null = session.totalsSnapshot;

    const subtotalCents = totals?.subtotal_cents ?? 0;
    const taxCents = totals?.tax_cents ?? 0;
    const grandTotalCents = totals?.grand_total_cents ?? 0;
    const discountCents = Math.max(0, subtotalCents + taxCents - grandTotalCents);

    return {
      subtotal: centsToDisplay(subtotalCents),
      tax: centsToDisplay(taxCents),
      grand_total: centsToDisplay(grandTotalCents),
      discount: centsToDisplay(discountCents),
      currency: 'USD',
    };
  }

  /** GET /commerce/checkout/sessions/:id/page — HTML checkout page */
  @Get(':id/page')
  async getSessionPage(@Param('id') id: string, @Res() res: Response): Promise<void> {
    const session = await this.checkoutSessionService.getSession(id);
    const totals: UcpTotals | null = session.totalsSnapshot;
    const lineItems = session.lineItemsSnapshot ?? [];

    const subtotalCents = totals?.subtotal_cents ?? 0;
    const taxCents = totals?.tax_cents ?? 0;
    const grandTotalCents = totals?.grand_total_cents ?? 0;

    const itemsHtml = lineItems.map((li: any) => {
      const item = li.item ?? {};
      const title = item.title ?? 'Item';
      const price = centsToDisplay(item.price ?? 0);
      const qty = li.quantity ?? 1;
      return `<tr><td>${title}</td><td>${qty}</td><td>₹${price}</td></tr>`;
    }).join('');

    const html = `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Checkout - Vik Rai</title>
  <style>
    * { margin: 0; padding: 0; box-sizing: border-box; }
    body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: #0a0f1a; color: #e0e0e0; min-height: 100vh; display: flex; justify-content: center; align-items: center; }
    .container { background: #141b2d; border-radius: 16px; padding: 40px; max-width: 500px; width: 90%; box-shadow: 0 8px 32px rgba(0,0,0,0.4); }
    h1 { color: #00d4aa; font-size: 24px; margin-bottom: 8px; }
    .subtitle { color: #888; font-size: 14px; margin-bottom: 24px; }
    .session-id { color: #666; font-size: 11px; word-break: break-all; }
    table { width: 100%; border-collapse: collapse; margin: 16px 0; }
    th { text-align: left; padding: 8px 0; color: #888; font-size: 12px; text-transform: uppercase; border-bottom: 1px solid #2a3444; }
    td { padding: 12px 0; border-bottom: 1px solid #1e2738; }
    .totals { margin-top: 16px; padding-top: 16px; border-top: 2px solid #00d4aa; }
    .total-row { display: flex; justify-content: space-between; padding: 6px 0; }
    .grand-total { font-size: 20px; font-weight: bold; color: #00d4aa; }
    .btn { display: block; width: 100%; padding: 14px; margin-top: 24px; background: #00d4aa; color: #0a0f1a; border: none; border-radius: 8px; font-size: 16px; font-weight: 600; cursor: pointer; text-align: center; }
    .btn:hover { background: #00b894; }
    .btn-secondary { background: transparent; border: 1px solid #2a3444; color: #888; margin-top: 8px; }
    .btn-secondary:hover { border-color: #00d4aa; color: #00d4aa; }
    .status { display: inline-block; padding: 4px 12px; border-radius: 12px; font-size: 12px; font-weight: 600; background: #1a3a2a; color: #00d4aa; margin-bottom: 16px; }
    .success { display: none; text-align: center; padding: 40px 0; }
    .success h2 { color: #00d4aa; margin-bottom: 8px; }
    .checkmark { font-size: 48px; margin-bottom: 16px; }
  </style>
</head>
<body>
  <div class="container">
    <div id="checkout-form">
      <h1>Checkout</h1>
      <p class="subtitle">Complete your purchase</p>
      <span class="status">${session.ucpStatus}</span>
      <table>
        <thead><tr><th>Item</th><th>Qty</th><th>Price</th></tr></thead>
        <tbody>${itemsHtml}</tbody>
      </table>
      <div class="totals">
        <div class="total-row"><span>Subtotal</span><span>₹${centsToDisplay(subtotalCents)}</span></div>
        <div class="total-row"><span>Tax</span><span>₹${centsToDisplay(taxCents)}</span></div>
        <div class="total-row grand-total"><span>Total</span><span>₹${centsToDisplay(grandTotalCents)}</span></div>
      </div>
      <button class="btn" id="complete-btn" onclick="completePurchase()">Complete Purchase</button>
      <button class="btn btn-secondary" onclick="window.close()">Cancel</button>
    </div>
    <div id="success" class="success">
      <div class="checkmark">✓</div>
      <h2>Order Confirmed!</h2>
      <p>Your order has been placed successfully.</p>
      <p class="session-id" style="margin-top: 16px;">Order ID: ${id}</p>
      <button class="btn" onclick="window.close()" style="margin-top: 24px;">Close</button>
    </div>
  </div>
  <script>
    const SESSION_ID = '${id}';
    const BASE_URL = window.location.origin;

    async function completePurchase() {
      const btn = document.getElementById('complete-btn');
      btn.disabled = true;
      btn.textContent = 'Processing...';
      try {
        const res = await fetch(BASE_URL + '/commerce/checkout/sessions/' + SESSION_ID + '/complete', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ payment_instrument: { type: 'card', last4: '4242' } }),
        });
        if (res.ok) {
          document.getElementById('checkout-form').style.display = 'none';
          document.getElementById('success').style.display = 'block';
          if (window.opener) {
            window.opener.postMessage({ type: 'checkout_complete', sessionId: SESSION_ID }, '*');
          }
        } else {
          const body = await res.json().catch(() => ({}));
          alert(body.message || 'Payment failed. Please try again.');
          btn.disabled = false;
          btn.textContent = 'Complete Purchase';
        }
      } catch (e) {
        alert('Something went wrong. Please try again.');
        btn.disabled = false;
        btn.textContent = 'Complete Purchase';
      }
    }
  </script>
</body>
</html>`;

    res.type('text/html').send(html);
  }
}
