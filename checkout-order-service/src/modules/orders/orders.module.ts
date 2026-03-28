import { Module } from '@nestjs/common'
import { TypeOrmModule } from '@nestjs/typeorm'
import { BullModule } from '@nestjs/bull'
import { ConfigModule } from '@nestjs/config'
import { Order } from './orders/order.entity'
import { OrderStatusHistory } from './orders/order-status-history.entity'
import { OrderService } from './orders/order.service'
import { OrderEventsConsumer } from './orders/order-events.consumer'
import { OrderController } from './orders/order.controller'
import { AuditService } from './audit/audit.service'
import { WebhookEvent } from './webhook/webhook-event.entity'
import { WebhookService } from './webhook/webhook.service'
import { WebhookController } from './webhook/webhook.controller'
import { WebhookIngestionConsumer } from './webhook/webhook-ingestion.consumer'
import { PlatformProfileController } from './profile/platform-profile.controller'
import { UcpClientModule } from '../ucp-client/ucp-client.module'
import { RagIndexingService } from './orders/rag-indexing.service'

@Module({
  imports: [
    ConfigModule,
    TypeOrmModule.forFeature([Order, OrderStatusHistory, WebhookEvent]),
    BullModule.registerQueue(
      { name: 'order-events' },
      { name: 'webhook-ingestion' },
    ),
    UcpClientModule,
  ],
  controllers: [OrderController, WebhookController, PlatformProfileController],
  providers: [
    OrderService,
    OrderEventsConsumer,
    AuditService,
    WebhookService,
    WebhookIngestionConsumer,
    RagIndexingService,
  ],
  exports: [OrderService, AuditService],
})
export class OrdersModule {}
