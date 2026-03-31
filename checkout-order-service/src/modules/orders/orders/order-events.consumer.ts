import { Logger } from '@nestjs/common'
import { Processor, Process } from '@nestjs/bull'
import { Job } from 'bull'
import { OrderService } from './order.service'
import type { EventEnvelope } from '../../../shared/types/event-envelope.interface'
import type { ConfirmedOrderPayload } from './order.service'

@Processor('order-events')
export class OrderEventsConsumer {
  private readonly logger = new Logger(OrderEventsConsumer.name)

  constructor(private readonly orderService: OrderService) {}

  @Process('order.confirmed')
  async handleOrderConfirmed(job: Job<EventEnvelope<ConfirmedOrderPayload>>): Promise<void> {
    const { eventId, payload } = job.data
    this.logger.log(JSON.stringify({ event: 'order.confirmed.received', eventId }))

    try {
      const result = await this.orderService.createFromConfirmedEvent(payload)
      this.logger.log(
        JSON.stringify({ event: 'order.confirmed.processed', eventId, orderId: result.orderId }),
      )
    } catch (err) {
      this.logger.error(
        JSON.stringify({ event: 'order.confirmed.failed', eventId, error: (err as Error).message }),
      )
      throw err
    }
  }
}
