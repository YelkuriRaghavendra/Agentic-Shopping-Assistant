import { Injectable, Logger } from '@nestjs/common'
import { ConfigService } from '@nestjs/config'

/**
 * RagIndexingService — fires-and-forgets order embedding requests to the
 * RAG service whenever an order is created or its status changes.
 *
 * Satisfies Requirements 12.1 and 12.3:
 *  - Indexes order records as user-scoped embeddings keyed by customer_id
 *  - Triggers re-indexing within 5 minutes of any order status change
 *
 * Failures are logged but never propagate — RAG indexing is best-effort and
 * must not block order mutations.
 */
@Injectable()
export class RagIndexingService {
  private readonly logger = new Logger(RagIndexingService.name)
  private readonly ragUrl: string
  private readonly ragApiKey: string
  private readonly ragSourceId: string

  constructor(private readonly config: ConfigService) {
    this.ragUrl = config.get<string>('RAG_SERVICE_URL', 'http://localhost:8001')
    this.ragApiKey = config.get<string>('RAG_SERVICE_API_KEY', '')
    this.ragSourceId = config.get<string>('RAG_ORDER_SOURCE_ID', '')
  }

  /**
   * Enqueue an order for (re-)indexing in the RAG service.
   * Called after order creation and after every status change.
   * Never throws — failures are logged only.
   */
  async indexOrder(customerId: string, order: Record<string, unknown>): Promise<void> {
    if (!this.ragSourceId) {
      this.logger.warn('rag_indexing.skipped', { reason: 'RAG_ORDER_SOURCE_ID not configured' })
      return
    }

    const body = JSON.stringify({
      source_id: this.ragSourceId,
      customer_id: customerId,
      order,
    })

    try {
      const response = await fetch(`${this.ragUrl}/api/v1/orders/index`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-API-Key': this.ragApiKey,
        },
        body,
        signal: AbortSignal.timeout(10_000), // 10 s — non-blocking
      })

      if (!response.ok) {
        const text = await response.text().catch(() => '')
        this.logger.warn('rag_indexing.failed', {
          status: response.status,
          body: text.slice(0, 200),
          customerId,
        })
      } else {
        this.logger.log('rag_indexing.queued', { customerId, orderId: order['ucpOrderId'] })
      }
    } catch (err) {
      this.logger.warn('rag_indexing.error', {
        error: (err as Error).message,
        customerId,
      })
    }
  }
}
