import { Injectable, Logger } from '@nestjs/common'
import { InjectRepository } from '@nestjs/typeorm'
import { Repository } from 'typeorm'
import { InjectQueue } from '@nestjs/bull'
import { Queue } from 'bull'
import { WebhookEvent } from './webhook-event.entity'
import { WebhookVerificationService } from '../../ucp-client/verification/webhook-verification.service'
import { randomUUID } from 'crypto'

export interface IngestWebhookParams {
  merchantId: string
  signature: string
  rawBody: Buffer
  payload: Record<string, unknown>
}

export interface IngestWebhookResult {
  accepted: boolean
  duplicate: boolean
  eventId: string
}

/**
 * WebhookService — verifies, deduplicates, and enqueues inbound UCP order webhooks.
 *
 * Requirements 9.1, 9.2, 9.3, 9.7, 9.8
 */
@Injectable()
export class WebhookService {
  private readonly logger = new Logger(WebhookService.name)

  constructor(
    @InjectRepository(WebhookEvent)
    private readonly webhookEventRepo: Repository<WebhookEvent>,
    @InjectQueue('webhook-ingestion')
    private readonly webhookQueue: Queue,
    private readonly verificationService: WebhookVerificationService,
  ) {}

  /**
   * Ingest a UCP order webhook event.
   *
   * 1. Verify the JWT signature (Req 9.2, 9.3)
   * 2. Check for duplicate event_id (Req 9.8)
   * 3. Insert webhook_events record with status=queued (Req 9.7)
   * 4. Enqueue to BullMQ webhook-ingestion queue (Req 9.7)
   *
   * Returns false for `accepted` when signature verification fails.
   * Returns true + duplicate=true when the event_id was already seen.
   */
  async ingest(params: IngestWebhookParams): Promise<IngestWebhookResult> {
    const { merchantId, signature, rawBody, payload } = params

    // 1. Verify signature (Req 9.2, 9.3)
    const signatureValid = await this.verificationService.verifyWebhook(
      merchantId,
      signature,
      rawBody,
    )
    if (!signatureValid) {
      this.logger.warn(
        JSON.stringify({ event: 'webhook.signature_invalid', merchantId }),
      )
      return { accepted: false, duplicate: false, eventId: '' }
    }

    // Extract event_id from payload (UCP standard field)
    const eventId = (payload['event_id'] as string | undefined) ?? randomUUID()
    const eventType = (payload['event_type'] as string | undefined) ?? 'unknown'

    // 2. Idempotency check — duplicate event_id (Req 9.8)
    const existing = await this.webhookEventRepo.findOne({ where: { eventId } })
    if (existing) {
      this.logger.log(
        JSON.stringify({ event: 'webhook.duplicate', eventId, merchantId }),
      )
      return { accepted: true, duplicate: true, eventId }
    }

    // 3. Insert webhook_events record (Req 9.7)
    const record = this.webhookEventRepo.create({
      eventId,
      merchantId,
      eventType,
      payload,
      status: 'queued',
      signatureVerified: true,
      processedAt: null,
      error: null,
    })
    await this.webhookEventRepo.save(record)

    // 4. Enqueue to BullMQ (Req 9.7 — respond within 2s, defer processing)
    await this.webhookQueue.add(
      'ucp.order.event',
      { eventId, merchantId, eventType, payload },
      { attempts: 3, backoff: { type: 'exponential', delay: 2000 } },
    )

    this.logger.log(
      JSON.stringify({ event: 'webhook.accepted', eventId, merchantId, eventType }),
    )

    return { accepted: true, duplicate: false, eventId }
  }
}
