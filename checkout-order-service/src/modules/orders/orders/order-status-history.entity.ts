import {
  Column,
  CreateDateColumn,
  Entity,
  JoinColumn,
  ManyToOne,
  PrimaryGeneratedColumn,
  RelationId,
} from 'typeorm'
import { Order } from './order.entity'

@Entity({ schema: 'orders', name: 'order_status_history' })
export class OrderStatusHistory {
  @PrimaryGeneratedColumn('uuid', { name: 'history_id' })
  historyId: string

  // The FK column — owned by the @ManyToOne relation below
  @RelationId((h: OrderStatusHistory) => h.order)
  orderId: string

  @Column({ name: 'from_status', type: 'varchar', nullable: true })
  fromStatus: string | null

  @Column({ name: 'to_status', type: 'varchar' })
  toStatus: string

  @Column({ type: 'varchar' })
  source: 'webhook' | 'api' | 'system'

  @Column({ type: 'text', nullable: true })
  actor: string | null

  @Column({ type: 'text', nullable: true })
  note: string | null

  @CreateDateColumn({ name: 'created_at', type: 'timestamptz' })
  createdAt: Date

  @ManyToOne(() => Order, (order) => order.statusHistory, { onDelete: 'CASCADE' })
  @JoinColumn({ name: 'order_id' })
  order: Order
}
