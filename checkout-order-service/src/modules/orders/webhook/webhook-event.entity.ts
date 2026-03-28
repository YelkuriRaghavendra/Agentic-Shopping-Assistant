import { Column, CreateDateColumn, Entity, PrimaryColumn } from 'typeorm'

export type WebhookEventStatus = 'queued' | 'processed' | 'failed' | 'duplicate'

@Entity({ schema: 'orders', name: 'webhook_events' })
export class WebhookEvent {
  @PrimaryColumn({ name: 'event_id', type: 'varchar', length: 255 })
  eventId: string

  @Column({ name: 'merchant_id', type: 'varchar', length: 255 })
  merchantId: string

  @Column({ name: 'event_type', type: 'varchar', length: 100 })
  eventType: string

  @Column({ type: 'jsonb' })
  payload: Record<string, unknown>

  @Column({ type: 'varchar', length: 20, default: 'queued' })
  status: WebhookEventStatus

  @Column({ name: 'signature_verified', type: 'boolean', default: false })
  signatureVerified: boolean

  @Column({ name: 'processed_at', type: 'timestamptz', nullable: true })
  processedAt: Date | null

  @Column({ type: 'text', nullable: true })
  error: string | null

  @CreateDateColumn({ name: 'created_at', type: 'timestamptz' })
  createdAt: Date
}
