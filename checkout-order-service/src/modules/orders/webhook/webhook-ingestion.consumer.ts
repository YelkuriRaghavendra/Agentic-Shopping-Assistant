import { Injectable, Logger } from '@nestjs/common'
import { Processor, Process, InjectQueue } from '@nestjs/bull'
import { Job, Queue } from 'bull'
import { InjectRepository } from '@nestjs/typeorm'
import { DataSource, Repository } from 'typeorm'
import { Order } from '../orders/order.entity'
import { OrderStatusHistory } from '../orders/order-status-history.entity'
import { WebhookEvent } from './webhook-event.entity'
import { AuditService } from '../audit/audit.service'
import { RagIndexingService } from '../orders/rag-indexing.service'
import { UcpOrderStatus } from '../../../shared/types/ucp-order-status.enum'
import type {
  UcpFulfillmentEvent,
  UcpAdjustment,
  UcpTotals,
} from '../../../shared/types/ucp-types.interface'
import { randomUUID } from 'crypto'

interface WebhookJobData {
  eventId: string
  merchantId: string
  eventType: string
  payload: Record<string, unknown>
}

/**
 * WebhookIngestionConsumer — processes UCP order lifecycle events from the
 * `webhook-ingestion` BullMQ queue.
 *
 * For each event:
 *  - Appends new fulfillment events to `fulfillment.events` (append-only)
 *  - Appends new adjustments to `adjustments` (append-only)
 *  - Updates `totals` if provided
 *  - Derives and updates `status` from the event type
 *  - Writes `order_status_history` and `audit_log` in the same transaction
 *  - Publishes `order.shipped` or `payment.failed` to `order-events` queue
 *
 * Requirements 9.4, 9.5, 9.6
 */
@Processor('webhook-ingestion')
@Injectable()
export class WebhookIngestionConsumer {
  private readonly logger = new Logger(WebhookIngestionConsumer.name)

  constructor(
    @InjectRepository(Order)
    private readonly orderRepo: Repository<Order>,
    @InjectRepository(WebhookEvent)
    private readonly webhookEventRepo: Repository<WebhookEvent>,
    @InjectQueue('order-events')
    private readonly orderEventsQueue: Queue,
    private readonly dataSource: DataSource,
    private readonly auditService: AuditService,
    private readonly ragIndexingService: RagIndexingService,
  ) {}

  @Process('ucp.order.event')
  async handleOrderEvent(job: Job<WebhookJobData>): Promise<void> {
    const { eventId, merchantId, eventType, payload } = job.data

    this.logger.log(
      JSON.stringify({ event: 'webhook.processing', eventId, merchantId, eventType }),
    )

    try {
      await this.processEvent(eventId, merchantId, eventType, payload)

      // Mark webhook_events record as processed
      await this.webhookEventRepo.update(
        { eventId },
        { status: 'processed', processedAt: new Date() },
      )

      this.logger.log(
        JSON.stringify({ event: 'webhook.processed', eventId, merchantId, eventType }),
      )
    } catch (err) {
      this.logger.error(
        JSON.stringify({
          event: 'webhook.failed',
          eventId,
          merchantId,
          eventType,
          error: (err as Error).message,
        }),
      )
      // Mark as failed so we can inspect it
      await this.webhookEventRepo.update(
        { eventId },
        { status: 'failed', error: (err as Error).message },
      )
      throw err // re-throw so BullMQ retries
    }
  }

  // ── Private ────────────────────────────────────────────────────────────────

  private async processEvent(
    eventId: string,
    merchantId: string,
    eventType: string,
    payload: Record<string, unknown>,
  ): Promise<void> {
    const ucpOrderId = payload['order_id'] as string | undefined
    if (!ucpOrderId) {
      this.logger.warn(
        JSON.stringify({ event: 'webhook.missing_order_id', eventId, eventType }),
      )
      return
    }

    const order = await this.orderRepo.findOne({ where: { ucpOrderId } })
    if (!order) {
      this.logger.warn(
        JSON.stringify({ event: 'webhook.order_not_found', eventId, ucpOrderId }),
      )
      return
    }

    const newStatus = this.deriveStatus(eventType, order.status)
    const fulfillmentEvent = this.extractFulfillmentEvent(eventType, payload)
    const adjustment = this.extractAdjustment(eventType, payload)
    const newTotals = payload['totals'] as UcpTotals | undefined

    await this.dataSource.transaction(async (em) => {
      const beforeState = {
        status: order.status,
        fulfillment: order.fulfillment,
        adjustments: order.adjustments,
        totals: order.totals,
      }

      // Append fulfillment event (append-only — Req 9.5)
      if (fulfillmentEvent) {
        order.fulfillment = {
          ...order.fulfillment,
          events: [...(order.fulfillment.events ?? []), fulfillmentEvent],
        }
      }

      // Append adjustment (append-only — Req 9.6)
      if (adjustment) {
        order.adjustments = [...order.adjustments, adjustment]
      }

      // Update totals if provided
      if (newTotals) {
        order.totals = newTotals
      }

      const fromStatus = order.status
      if (newStatus && newStatus !== order.status) {
        order.status = newStatus
      }

      const savedOrder = await em.save(Order, order)

      // Write status history
      if (newStatus && newStatus !== fromStatus) {
        await em.save(OrderStatusHistory, {
          orderId: order.orderId,
          fromStatus,
          toStatus: newStatus,
          source: 'webhook',
          actor: `merchant:${merchantId}`,
          note: `event_id=${eventId}`,
        })
      }

      // Write audit log (Req 19.1, 19.2, 19.5)
      await this.auditService.write(em, {
        orderId: order.orderId,
        actor: `merchant:${merchantId}`,
        actionType: 'status_changed',
        beforeState,
        afterState: {
          status: savedOrder.status,
          fulfillment: savedOrder.fulfillment,
          adjustments: savedOrder.adjustments,
          totals: savedOrder.totals,
        },
        source: 'webhook',
      })

      this.logger.log(
        JSON.stringify({
          orderId: order.orderId,
          fromStatus,
          toStatus: savedOrder.status,
          source: 'webhook',
          timestamp: new Date().toISOString(),
        }),
      )
    })

    // Publish downstream events after transaction commits (Req 9.4, 9.5)
    await this.publishDownstreamEvent(eventType, order, payload, eventId)

    // Trigger RAG re-indexing after status change (Requirement 12.3) — fire-and-forget
    void this.ragIndexingService.indexOrder(order.customerId, {
      ucpOrderId: order.ucpOrderId,
      orderId: order.orderId,
      customerId: order.customerId,
      merchantId: order.merchantId,
      status: order.status,
      lineItems: order.lineItems,
      totals: order.totals,
      fulfillment: order.fulfillment,
      adjustments: order.adjustments,
    })
  }

  /**
   * Derive the new order status from the UCP event type.
   * Returns null if the event does not trigger a status change.
   */
  private deriveStatus(
    eventType: string,
    currentStatus: UcpOrderStatus,
  ): UcpOrderStatus | null {
    switch (eventType) {
      case 'order.shipped':
        return UcpOrderStatus.PARTIAL // partial fulfillment until all items shipped
      case 'order.fulfilled':
        return UcpOrderStatus.FULFILLED
      case 'order.payment_failed':
        return UcpOrderStatus.PAYMENT_FAILED
      case 'order.cancelled':
        return UcpOrderStatus.CANCELLED
      case 'order.return_completed':
        return UcpOrderStatus.RETURNED
      default:
        return null
    }
  }

  private extractFulfillmentEvent(
    eventType: string,
    payload: Record<string, unknown>,
  ): UcpFulfillmentEvent | null {
    if (eventType === 'order.shipped' || eventType === 'order.fulfilled') {
      return {
        type: eventType === 'order.shipped' ? 'shipped' : 'delivered',
        occurred_at: (payload['occurred_at'] as string | undefined) ?? new Date().toISOString(),
        tracking_number: payload['tracking_number'] as string | undefined,
        carrier: payload['carrier'] as string | undefined,
        note: payload['note'] as string | undefined,
      }
    }
    return null
  }

  private extractAdjustment(
    eventType: string,
    payload: Record<string, unknown>,
  ): UcpAdjustment | null {
    if (eventType === 'order.payment_failed') {
      return {
        type: 'payment_failed',
        amount_cents: 0,
        occurred_at: (payload['occurred_at'] as string | undefined) ?? new Date().toISOString(),
        reason: (payload['reason'] as string | undefined) ?? 'Payment failed',
      }
    }
    return null
  }

  private async publishDownstreamEvent(
    eventType: string,
    order: Order,
    payload: Record<string, unknown>,
    eventId: string,
  ): Promise<void> {
    if (eventType === 'order.shipped') {
      // Req 9.5 — publish order.shipped
      await this.orderEventsQueue.add('order.shipped', {
        eventId: randomUUID(),
        eventType: 'order.shipped',
        version: '1.0',
        timestamp: new Date().toISOString(),
        source: 'webhook-handler',
        payload: {
          orderId: order.orderId,
          ucpOrderId: order.ucpOrderId,
          customerId: order.customerId,
          merchantId: order.merchantId,
          trackingNumber: payload['tracking_number'],
          carrier: payload['carrier'],
          sourceEventId: eventId,
        },
      })
    } else if (eventType === 'order.payment_failed') {
      // Req 9.4 — publish payment.failed
      await this.orderEventsQueue.add('payment.failed', {
        eventId: randomUUID(),
        eventType: 'payment.failed',
        version: '1.0',
        timestamp: new Date().toISOString(),
        source: 'webhook-handler',
        payload: {
          orderId: order.orderId,
          ucpOrderId: order.ucpOrderId,
          customerId: order.customerId,
          merchantId: order.merchantId,
          reason: payload['reason'],
          sourceEventId: eventId,
        },
      })
    }
  }
}
