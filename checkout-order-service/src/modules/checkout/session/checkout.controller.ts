import {
  Controller,
  Post,
  Get,
  Put,
  Param,
  Body,
  UsePipes,
  ValidationPipe,
  HttpCode,
  HttpStatus,
} from '@nestjs/common';
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
    return this.checkoutSessionService.createSession(
      dto.merchant_id,
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

  /** POST /commerce/checkout/sessions/:id/cancel — cancel session */
  @Post(':id/cancel')
  @HttpCode(HttpStatus.OK)
  async cancelSession(@Param('id') id: string): Promise<CheckoutSession> {
    return this.checkoutSessionService.cancelSession(id);
  }

  /** GET /commerce/checkout/sessions/:id/summary — totals in display currency */
  @Get(':id/summary')
  async getSessionSummary(@Param('id') id: string): Promise<SummaryResponse> {
    const session = await this.checkoutSessionService.getSession(id);
    const totals: UcpTotals | null = session.totalsSnapshot;

    const subtotalCents = totals?.subtotal_cents ?? 0;
    const taxCents = totals?.tax_cents ?? 0;
    const grandTotalCents = totals?.grand_total_cents ?? 0;
    // discount = subtotal + tax - grand_total (derived)
    const discountCents = subtotalCents + taxCents - grandTotalCents;

    return {
      subtotal: centsToDisplay(subtotalCents),
      discount: centsToDisplay(Math.max(0, discountCents)),
      tax: centsToDisplay(taxCents),
      grand_total: centsToDisplay(grandTotalCents),
      currency: 'USD',
    };
  }
}
