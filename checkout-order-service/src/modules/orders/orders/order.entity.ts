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
  @PrimaryGeneratedColumn('uuid')
  orderId: string

  @Column({ type: 'uuid' })
  customerId: string

  @Column({ type: 'uuid', nullable: true })
  checkoutId: string | null

  @Column()
  merchantId: string

  @Column({ nullable: true })
  ucpOrderId: string | null

  @Column({ type: 'text', nullable: true })
  permalinkUrl: string | null

  @Column({ default: UcpOrderStatus.PROCESSING })
  status: UcpOrderStatus

  @Column({ type: 'jsonb', default: '[]' })
  lineItems: UcpOrderLineItem[]

  @Column({ type: 'jsonb', default: '{}' })
  fulfillment: UcpFulfillment

  @Column({ type: 'jsonb', default: '[]' })
  adjustments: UcpAdjustment[]

  @Column({ type: 'jsonb', default: '{}' })
  totals: UcpTotals

  @CreateDateColumn({ type: 'timestamptz' })
  createdAt: Date

  @UpdateDateColumn({ type: 'timestamptz' })
  updatedAt: Date

  @OneToMany(() => OrderStatusHistory, (history) => history.order, { cascade: true })
  statusHistory: OrderStatusHistory[]
}
