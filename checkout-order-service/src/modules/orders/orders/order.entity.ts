import {
  Column,
  CreateDateColumn,
  Entity,
  OneToMany,
  PrimaryGeneratedColumn,
  UpdateDateColumn,
} from 'typeorm'
import { UcpOrderStatus } from '../../../shared/types/ucp-order-status.enum'
import type {
  UcpOrderLineItem,
  UcpFulfillment,
  UcpAdjustment,
  UcpTotals,
} from '../../../shared/types/ucp-types.interface'
import { OrderStatusHistory } from './order-status-history.entity'

@Entity({ schema: 'orders', name: 'orders' })
export class Order {
  @PrimaryGeneratedColumn('uuid', { name: 'order_id' })
  orderId: string

  @Column({ name: 'customer_id', type: 'uuid' })
  customerId: string

  @Column({ name: 'checkout_id', type: 'uuid', nullable: true })
  checkoutId: string | null

  @Column({ name: 'merchant_id' })
  merchantId: string

  @Column({ name: 'ucp_order_id', nullable: true })
  ucpOrderId: string | null

  @Column({ name: 'permalink_url', type: 'text', nullable: true })
  permalinkUrl: string | null

  @Column({ default: UcpOrderStatus.PROCESSING })
  status: UcpOrderStatus

  @Column({ name: 'line_items', type: 'jsonb', default: '[]' })
  lineItems: UcpOrderLineItem[]

  @Column({ type: 'jsonb', default: '{}' })
  fulfillment: UcpFulfillment

  @Column({ type: 'jsonb', default: '[]' })
  adjustments: UcpAdjustment[]

  @Column({ type: 'jsonb', default: '{}' })
  totals: UcpTotals

  @CreateDateColumn({ name: 'created_at', type: 'timestamptz' })
  createdAt: Date

  @UpdateDateColumn({ name: 'updated_at', type: 'timestamptz' })
  updatedAt: Date

  @OneToMany(() => OrderStatusHistory, (history) => history.order, { cascade: true })
  statusHistory: OrderStatusHistory[]
}
