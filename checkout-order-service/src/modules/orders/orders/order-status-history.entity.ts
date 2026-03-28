import {
  Column,
  CreateDateColumn,
  Entity,
  ManyToOne,
  PrimaryGeneratedColumn,
} from 'typeorm'
import { Order } from './order.entity'

@Entity({ schema: 'orders', name: 'order_status_history' })
export class OrderStatusHistory {
  @PrimaryGeneratedColumn('uuid')
  historyId: string

  @Column({ type: 'uuid' })
  orderId: string

  @Column({ type: 'varchar', nullable: true })
  fromStatus: string | null

  @Column({ type: 'varchar' })
  toStatus: string

  @Column({ type: 'varchar' })
  source: 'webhook' | 'api' | 'system'

  @Column({ type: 'text', nullable: true })
  actor: string | null

  @Column({ type: 'text', nullable: true })
  note: string | null

  @CreateDateColumn({ type: 'timestamptz' })
  createdAt: Date

  @ManyToOne(() => Order, (order) => order.statusHistory, { onDelete: 'CASCADE' })
  order: Order
}
