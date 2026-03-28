import {
  Column,
  CreateDateColumn,
  Entity,
  PrimaryGeneratedColumn,
  UpdateDateColumn,
} from 'typeorm';
import { UcpCheckoutStatus } from '../../../shared/types/ucp-checkout-status.enum';
import type {
  UcpLineItem,
  UcpBuyer,
  UcpContext,
  UcpTotals,
} from '../../../shared/types/ucp-types.interface';

@Entity({ schema: 'checkout', name: 'checkout_sessions' })
export class CheckoutSession {
  @PrimaryGeneratedColumn('uuid', { name: 'session_id' })
  sessionId: string;

  @Column({ name: 'customer_id', type: 'uuid' })
  customerId: string;

  @Column({ name: 'merchant_id' })
  merchantId: string;

  @Column({ name: 'ucp_checkout_id', nullable: true })
  ucpCheckoutId: string | null;

  @Column({ name: 'ucp_status', default: UcpCheckoutStatus.INCOMPLETE })
  ucpStatus: UcpCheckoutStatus;

  @Column({ name: 'continue_url', type: 'text', nullable: true })
  continueUrl: string | null;

  @Column({ name: 'expires_at', type: 'timestamptz', nullable: true })
  expiresAt: Date | null;

  @Column({ name: 'line_items_snapshot', type: 'jsonb', default: '[]' })
  lineItemsSnapshot: UcpLineItem[];

  @Column({ name: 'buyer_snapshot', type: 'jsonb', nullable: true })
  buyerSnapshot: UcpBuyer | null;

  @Column({ name: 'context_snapshot', type: 'jsonb', nullable: true })
  contextSnapshot: UcpContext | null;

  @Column({ name: 'payment_handlers', type: 'jsonb', nullable: true })
  paymentHandlers: unknown | null;

  @Column({ name: 'totals_snapshot', type: 'jsonb', nullable: true })
  totalsSnapshot: UcpTotals | null;

  @Column({ name: 'ucp_order_id', nullable: true })
  ucpOrderId: string | null;

  @Column({ name: 'ucp_order_permalink', type: 'text', nullable: true })
  ucpOrderPermalink: string | null;

  @CreateDateColumn({ name: 'created_at', type: 'timestamptz' })
  createdAt: Date;

  @UpdateDateColumn({ name: 'updated_at', type: 'timestamptz' })
  updatedAt: Date;
}
