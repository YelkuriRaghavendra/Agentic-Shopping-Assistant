import { Injectable, Logger, HttpStatus } from '@nestjs/common'
import { InjectRepository } from '@nestjs/typeorm'
import { DataSource, Repository } from 'typeorm'
import { randomUUID } from 'crypto'
import { Order } from './order.entity'
import { OrderStatusHistory } from './order-status-history.entity'
import { UcpOrderStatus } from '../../../shared/types/ucp-order-status.enum'
import { CommerceException, CommerceErrorCodes } from '../../../shared/errors/commerce.exception'
import { AuditService } from '../audit/audit.service'
import { RagIndexingService } from './rag-indexing.service'
import type {
  UcpOrderLineItem,
  UcpTotals,
  UcpAdjustment,
} from '../../../shared/types/ucp-types.interface'

export interface ConfirmedOrderPayload {
  ucpOrderId: string
  ucpOrderPermalink: string | null
  checkoutId: string
  customerId: string
  merchantId: string
  lineItems: UcpOrderLineItem[]
  totals: UcpTotals | null
}

export interface OrderCreationResult {
  orderId: string
  ucpOrderId: string | null
  status: UcpOrderStatus
  permalinkUrl: string | null
}

@Injectable()
export class OrderService {
  private readonly logger = new Logger(OrderService.name)

  constructor(
    @InjectRepository(Order)
    private readonly orderRepo: Repository<Order>,
    @InjectRepository(OrderStatusHistory)
    private readonly historyRepo: Repository<OrderStatusHistory>,
    private readonly dataSource: DataSource,
    private readonly auditService: AuditService,
    private readonly ragIndexingService: RagIndexingService,
  ) {}

  async createFromConfirmedEvent(payload: ConfirmedOrderPayload): Promise<OrderCreationResult> {
    const result = await this.dataSource.transaction(async (em) => {
      // 1. Insert order
      const order = em.create(Order, {
        customerId: payload.customerId,
        checkoutId: payload.checkoutId,
        merchantId: payload.merchantId,
        ucpOrderId: payload.ucpOrderId,
        permalinkUrl: payload.ucpOrderPermalink ?? null,
        status: UcpOrderStatus.PROCESSING,
        lineItems: payload.lineItems ?? [],
        fulfillment: { events: [] },
        adjustments: [],
        totals: payload.totals ?? ({} as UcpTotals),
      })
      const savedOrder = await em.save(Order, order)

      // 2. Insert initial status history
      const history = em.create(OrderStatusHistory, {
        orderId: savedOrder.orderId,
        fromStatus: null,
        toStatus: UcpOrderStatus.PROCESSING,
        source: 'system',
        actor: 'system',
        note: null,
      })
      await em.save(OrderStatusHistory, history)

      // 3. Write audit log via AuditService (Requirement 19.5 — rolls back on failure)
      await this.auditService.write(em, {
        orderId: savedOrder.orderId,
        actor: 'system',
        actionType: 'order_created',
        beforeState: null,
        afterState: { orderId: savedOrder.orderId, status: UcpOrderStatus.PROCESSING },
        source: 'system',
      })

      return savedOrder
    })

    this.logger.log(
      JSON.stringify({
        orderId: result.orderId,
        fromStatus: null,
        toStatus: UcpOrderStatus.PROCESSING,
        source: 'system',
        timestamp: new Date().toISOString(),
      }),
    )

    // Trigger RAG indexing (Requirement 12.1, 12.3) — fire-and-forget
    void this.ragIndexingService.indexOrder(payload.customerId, {
      ucpOrderId: result.ucpOrderId,
      orderId: result.orderId,
      customerId: payload.customerId,
      merchantId: payload.merchantId,
      status: result.status,
      lineItems: payload.lineItems,
      totals: payload.totals,
      ucpOrderPermalink: payload.ucpOrderPermalink,
    })

    return {
      orderId: result.orderId,
      ucpOrderId: result.ucpOrderId,
      status: result.status,
      permalinkUrl: result.permalinkUrl,
    }
  }

  /**
   * Cancel an order.
   * Only orders in `processing` status may be cancelled (Requirement 8.1, 8.2).
   * Appends a `cancellation` adjustment, transitions to `cancelled`, writes
   * status history and audit log in one transaction (Requirement 8.5, 19.5).
   */
  async cancelOrder(
    orderId: string,
    customerId: string,
    reason?: string,
    actor = 'customer',
  ): Promise<Order> {
    const result = await this.dataSource.transaction(async (em) => {
      const order = await em.findOne(Order, {
        where: { orderId },
        relations: ['statusHistory'],
      })

      if (!order || order.customerId !== customerId) {
        throw new CommerceException(
          CommerceErrorCodes.NOT_FOUND,
          `Order ${orderId} not found`,
          HttpStatus.NOT_FOUND,
        )
      }

      if (order.status === UcpOrderStatus.FULFILLED) {
        throw new CommerceException(
          CommerceErrorCodes.CANCELLATION_NOT_ALLOWED,
          'Fulfilled orders cannot be cancelled',
          HttpStatus.UNPROCESSABLE_ENTITY,
        )
      }

      if (order.status !== UcpOrderStatus.PROCESSING) {
        throw new CommerceException(
          CommerceErrorCodes.CANCELLATION_NOT_ALLOWED,
          `Order cannot be cancelled in status: ${order.status}`,
          HttpStatus.UNPROCESSABLE_ENTITY,
        )
      }

      const beforeState = { status: order.status, adjustments: order.adjustments }

      // Append cancellation adjustment (append-only — Requirement 8.5)
      const adjustment: UcpAdjustment = {
        type: 'cancellation',
        amount_cents: 0,
        occurred_at: new Date().toISOString(),
        reason: reason ?? 'Customer requested cancellation',
      }
      order.adjustments = [...order.adjustments, adjustment]
      order.status = UcpOrderStatus.CANCELLED

      const savedOrder = await em.save(Order, order)

      // Status history
      await em.save(OrderStatusHistory, {
        orderId,
        fromStatus: UcpOrderStatus.PROCESSING,
        toStatus: UcpOrderStatus.CANCELLED,
        source: 'api',
        actor,
        note: reason ?? null,
      })

      // Audit log (Requirement 19.1, 19.2, 19.5)
      await this.auditService.write(em, {
        orderId,
        actor,
        actionType: 'cancelled',
        beforeState,
        afterState: { status: UcpOrderStatus.CANCELLED, adjustments: savedOrder.adjustments },
        source: 'api',
      })

      this.logger.log(
        JSON.stringify({
          orderId,
          fromStatus: UcpOrderStatus.PROCESSING,
          toStatus: UcpOrderStatus.CANCELLED,
          source: 'api',
          timestamp: new Date().toISOString(),
        }),
      )

      return savedOrder
    })

    // Trigger RAG re-indexing after status change (Requirement 12.3) — fire-and-forget
    void this.ragIndexingService.indexOrder(result.customerId, {
      ucpOrderId: result.ucpOrderId,
      orderId: result.orderId,
      customerId: result.customerId,
      merchantId: result.merchantId,
      status: result.status,
      lineItems: result.lineItems,
      totals: result.totals,
      adjustments: result.adjustments,
    })

    return result
  }

  /**
   * Request a return for a fulfilled order.
   * Only orders in `fulfilled` status are eligible (Requirement 8.3, 8.4).
   * Appends a `return` adjustment, transitions to `return_requested`, writes
   * status history and audit log in one transaction (Requirement 8.5, 19.5).
   */
  async returnOrder(
    orderId: string,
    customerId: string,
    reason?: string,
    actor = 'customer',
  ): Promise<Order> {
    const result = await this.dataSource.transaction(async (em) => {
      const order = await em.findOne(Order, {
        where: { orderId },
        relations: ['statusHistory'],
      })

      if (!order || order.customerId !== customerId) {
        throw new CommerceException(
          CommerceErrorCodes.NOT_FOUND,
          `Order ${orderId} not found`,
          HttpStatus.NOT_FOUND,
        )
      }

      if (order.status !== UcpOrderStatus.FULFILLED) {
        throw new CommerceException(
          CommerceErrorCodes.RETURN_NOT_ELIGIBLE,
          `Returns are only allowed for fulfilled orders; current status: ${order.status}`,
          HttpStatus.UNPROCESSABLE_ENTITY,
        )
      }

      const beforeState = { status: order.status, adjustments: order.adjustments }

      // Append return adjustment (append-only — Requirement 8.5)
      const adjustment: UcpAdjustment = {
        type: 'return',
        amount_cents: 0,
        occurred_at: new Date().toISOString(),
        reason: reason ?? 'Customer requested return',
      }
      order.adjustments = [...order.adjustments, adjustment]
      order.status = UcpOrderStatus.RETURN_REQUESTED

      const savedOrder = await em.save(Order, order)

      // Status history
      await em.save(OrderStatusHistory, {
        orderId,
        fromStatus: UcpOrderStatus.FULFILLED,
        toStatus: UcpOrderStatus.RETURN_REQUESTED,
        source: 'api',
        actor,
        note: reason ?? null,
      })

      // Audit log (Requirement 19.1, 19.2, 19.5)
      await this.auditService.write(em, {
        orderId,
        actor,
        actionType: 'return_initiated',
        beforeState,
        afterState: { status: UcpOrderStatus.RETURN_REQUESTED, adjustments: savedOrder.adjustments },
        source: 'api',
      })

      this.logger.log(
        JSON.stringify({
          orderId,
          fromStatus: UcpOrderStatus.FULFILLED,
          toStatus: UcpOrderStatus.RETURN_REQUESTED,
          source: 'api',
          timestamp: new Date().toISOString(),
        }),
      )

      return savedOrder
    })

    // Trigger RAG re-indexing after status change (Requirement 12.3) — fire-and-forget
    void this.ragIndexingService.indexOrder(result.customerId, {
      ucpOrderId: result.ucpOrderId,
      orderId: result.orderId,
      customerId: result.customerId,
      merchantId: result.merchantId,
      status: result.status,
      lineItems: result.lineItems,
      totals: result.totals,
      adjustments: result.adjustments,
    })

    return result
  }
}
