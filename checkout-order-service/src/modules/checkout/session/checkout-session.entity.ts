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
  @PrimaryGeneratedColumn('uuid')
  sessionId: string;

  @Column({ type: 'uuid' })
  customerId: string;

  @Column()
  merchantId: string;

  @Column({ nullable: true })
  ucpCheckoutId: string | null;

  @Column({ default: UcpCheckoutStatus.INCOMPLETE })
  ucpStatus: UcpCheckoutStatus;

  @Column({ type: 'text', nullable: true })
  continueUrl: string | null;

  @Column({ type: 'timestamptz', nullable: true })
  expiresAt: Date | null;

  @Column({ type: 'jsonb', default: '[]' })
  lineItemsSnapshot: UcpLineItem[];

  @Column({ type: 'jsonb', nullable: true })
  buyerSnapshot: UcpBuyer | null;

  @Column({ type: 'jsonb', nullable: true })
  contextSnapshot: UcpContext | null;

  @Column({ type: 'jsonb', nullable: true })
  paymentHandlers: unknown | null;

  @Column({ type: 'jsonb', nullable: true })
  totalsSnapshot: UcpTotals | null;

  @Column({ nullable: true })
  ucpOrderId: string | null;

  @Column({ type: 'text', nullable: true })
  ucpOrderPermalink: string | null;

  @CreateDateColumn({ type: 'timestamptz' })
  createdAt: Date;

  @UpdateDateColumn({ type: 'timestamptz' })
  updatedAt: Date;
}
