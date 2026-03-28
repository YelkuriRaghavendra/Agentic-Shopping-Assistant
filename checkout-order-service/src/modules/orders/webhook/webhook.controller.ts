import {
  Controller,
  Post,
  Req,
  Res,
  Headers,
  Query,
  Logger,
  HttpStatus,
} from '@nestjs/common'
import { RawBodyRequest } from '@nestjs/common'
import { Request, Response } from 'express'
import { WebhookService } from './webhook.service'

/**
 * WebhookController — receives inbound UCP order lifecycle events from merchants.
 *
 * POST /commerce/webhooks/ucp/orders
 *   - Extracts merchant_id from query param or header
 *   - Delegates to WebhookService for signature verification, dedup, and enqueue
 *   - Returns 401 on invalid signature, 200 otherwise (Req 9.1, 9.2, 9.3, 9.7, 9.8)
 */
@Controller('commerce/webhooks/ucp')
export class WebhookController {
  private readonly logger = new Logger(WebhookController.name)

  constructor(private readonly webhookService: WebhookService) {}

  @Post('orders')
  async receiveOrderWebhook(
    @Req() req: RawBodyRequest<Request>,
    @Res() res: Response,
    @Query('merchant_id') merchantIdQuery: string,
    @Headers('x-merchant-id') merchantIdHeader: string,
    @Headers('request-signature') signature: string,
  ): Promise<void> {
    const merchantId = merchantIdQuery || merchantIdHeader

    if (!merchantId) {
      this.logger.warn('Webhook received without merchant_id')
      res.status(HttpStatus.BAD_REQUEST).json({ error: 'merchant_id is required' })
      return
    }

    if (!signature) {
      this.logger.warn(`Webhook received without Request-Signature for merchant ${merchantId}`)
      res.status(HttpStatus.UNAUTHORIZED).json({ error: 'Request-Signature header is required' })
      return
    }

    // rawBody is captured by NestJS rawBody: true option in main.ts (Req 9.2)
    const rawBody: Buffer = req.rawBody ?? Buffer.from(JSON.stringify(req.body))
    const payload = req.body as Record<string, unknown>

    const result = await this.webhookService.ingest({
      merchantId,
      signature,
      rawBody,
      payload,
    })

    if (!result.accepted) {
      res.status(HttpStatus.UNAUTHORIZED).json({ error: 'Invalid webhook signature' })
      return
    }

    // Return 200 immediately — processing is async (Req 9.7)
    res.status(HttpStatus.OK).json({
      received: true,
      eventId: result.eventId,
      duplicate: result.duplicate,
    })
  }
}
