import { Column, CreateDateColumn, Entity, PrimaryColumn } from 'typeorm'

export type WebhookEventStatus = 'queued' | 'processed' | 'failed' | 'duplicate'

@Entity({ schema: 'orders', name: 'webhook_events' })
export class WebhookEvent {
  @PrimaryColumn({ type: 'varchar', length: 255 })
  eventId: string

  @Column({ type: 'varchar', length: 255 })
  merchantId: string

  @Column({ type: 'varchar', length: 100 })
  eventType: string

  @Column({ type: 'jsonb' })
  payload: Record<string, unknown>

  @Column({ type: 'varchar', length: 20, default: 'queued' })
  status: WebhookEventStatus

  @Column({ type: 'boolean', default: false })
  signatureVerified: boolean

  @Column({ type: 'timestamptz', nullable: true })
  processedAt: Date | null

  @Column({ type: 'text', nullable: true })
  error: string | null

  @CreateDateColumn({ type: 'timestamptz' })
  createdAt: Date
}
