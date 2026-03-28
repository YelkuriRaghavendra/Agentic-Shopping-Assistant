import { Injectable, Logger, HttpStatus } from '@nestjs/common';
import { InjectRepository } from '@nestjs/typeorm';
import { Repository } from 'typeorm';
import { InjectQueue } from '@nestjs/bull';
import { Queue } from 'bull';
import { randomUUID } from 'crypto';
import { CheckoutSession } from './checkout-session.entity';
import { UcpCheckoutClient } from '../../ucp-client/checkout-client/ucp-checkout.client';
import { UcpCheckoutStatus } from '../../../shared/types/ucp-checkout-status.enum';
import { CommerceException, CommerceErrorCodes } from '../../../shared/errors/commerce.exception';
import type { UcpLineItem, UcpBuyer, UcpContext } from '../../../shared/types/ucp-types.interface';

@Injectable()
export class CheckoutSessionService {
  private readonly logger = new Logger(CheckoutSessionService.name);

  constructor(
    @InjectRepository(CheckoutSession)
    private readonly sessionRepo: Repository<CheckoutSession>,
    private readonly ucpCheckoutClient: UcpCheckoutClient,
    @InjectQueue('order-events')
    private readonly orderEventsQueue: Queue,
  ) {}

  // ── Public methods ──────────────────────────────────────────────────────────

  async createSession(
    merchantId: string,
    customerId: string,
    lineItems: UcpLineItem[],
    buyer?: UcpBuyer,
    context?: UcpContext,
  ): Promise<CheckoutSession> {
    const idempotencyKey = randomUUID();

    const ucpResponse = await this.ucpCheckoutClient.createCheckoutSession(
      merchantId,
      { line_items: lineItems, buyer, context },
      idempotencyKey,
    );

    const session = this.sessionRepo.create({
      merchantId,
      customerId,
      ucpCheckoutId: ucpResponse.id,
      ucpStatus: (ucpResponse.status as UcpCheckoutStatus) ?? UcpCheckoutStatus.INCOMPLETE,
      lineItemsSnapshot: lineItems,
      buyerSnapshot: buyer ?? null,
      contextSnapshot: context ?? null,
      paymentHandlers: ucpResponse.payment_handlers ?? null,
      totalsSnapshot: ucpResponse.totals ?? null,
      expiresAt: ucpResponse.expires_at ? new Date(ucpResponse.expires_at) : null,
      continueUrl: ucpResponse.continue_url ?? null,
    });

    await this.sessionRepo.save(session);

    await this.reactToStatus(session, UcpCheckoutStatus.INCOMPLETE, ucpResponse.status as UcpCheckoutStatus, null);

    return session;
  }

  async updateSession(
    sessionId: string,
    lineItems: UcpLineItem[],
    buyer?: UcpBuyer,
    context?: UcpContext,
  ): Promise<CheckoutSession> {
    const session = await this.loadSession(sessionId);
    this.assertNotCanceled(session);

    const idempotencyKey = randomUUID();

    const ucpResponse = await this.ucpCheckoutClient.updateCheckoutSession(
      session.merchantId,
      session.ucpCheckoutId!,
      { line_items: lineItems, buyer, context },
      idempotencyKey,
    );

    const fromStatus = session.ucpStatus;
    session.lineItemsSnapshot = lineItems;
    session.buyerSnapshot = buyer ?? null;
    session.contextSnapshot = context ?? null;
    session.totalsSnapshot = ucpResponse.totals ?? null;
    session.ucpStatus = ucpResponse.status as UcpCheckoutStatus;
    session.continueUrl = ucpResponse.continue_url ?? null;

    await this.sessionRepo.save(session);
    await this.reactToStatus(session, fromStatus, ucpResponse.status as UcpCheckoutStatus, null);

    return session;
  }

  async completeSession(
    sessionId: string,
    paymentInstrument: unknown,
  ): Promise<CheckoutSession> {
    const session = await this.loadSession(sessionId);
    this.assertNotCanceled(session);

    const idempotencyKey = randomUUID();

    const ucpResponse = await this.ucpCheckoutClient.completeCheckoutSession(
      session.merchantId,
      session.ucpCheckoutId!,
      { payment_instrument: paymentInstrument },
      idempotencyKey,
    );

    const fromStatus = session.ucpStatus;
    session.ucpStatus = ucpResponse.status as UcpCheckoutStatus;
    session.totalsSnapshot = ucpResponse.totals ?? session.totalsSnapshot;

    await this.sessionRepo.save(session);
    await this.reactToStatus(session, fromStatus, ucpResponse.status as UcpCheckoutStatus, paymentInstrument);

    return session;
  }

  async getSession(sessionId: string): Promise<CheckoutSession> {
    return this.loadSession(sessionId);
  }

  async cancelSession(sessionId: string): Promise<CheckoutSession> {
    const session = await this.loadSession(sessionId);
    this.assertNotCanceled(session);

    const idempotencyKey = randomUUID();

    await this.ucpCheckoutClient.cancelCheckoutSession(
      session.merchantId,
      session.ucpCheckoutId!,
      idempotencyKey,
    );

    const fromStatus = session.ucpStatus;
    session.ucpStatus = UcpCheckoutStatus.CANCELED;
    await this.sessionRepo.save(session);

    this.emitStatusLog(session.sessionId, fromStatus, UcpCheckoutStatus.CANCELED);

    return session;
  }

  // ── Private helpers ─────────────────────────────────────────────────────────

  private async loadSession(sessionId: string): Promise<CheckoutSession> {
    const session = await this.sessionRepo.findOne({ where: { sessionId } });
    if (!session) {
      throw new CommerceException(
        CommerceErrorCodes.NOT_FOUND,
        `Checkout session ${sessionId} not found`,
        HttpStatus.NOT_FOUND,
      );
    }
    return session;
  }

  private assertNotCanceled(session: CheckoutSession): void {
    if (session.ucpStatus === UcpCheckoutStatus.CANCELED) {
      throw new CommerceException(
        CommerceErrorCodes.SESSION_CANCELED,
        `Checkout session ${session.sessionId} is canceled and cannot be modified`,
        HttpStatus.UNPROCESSABLE_ENTITY,
      );
    }
  }

  private async reactToStatus(
    session: CheckoutSession,
    fromStatus: UcpCheckoutStatus,
    toStatus: UcpCheckoutStatus,
    paymentInstrument: unknown,
  ): Promise<void> {
    if (fromStatus === toStatus) return;

    this.emitStatusLog(session.sessionId, fromStatus, toStatus);

    switch (toStatus) {
      case UcpCheckoutStatus.REQUIRES_ESCALATION:
        // continue_url already stored on session; caller reads it from the returned session
        break;

      case UcpCheckoutStatus.READY_FOR_COMPLETE:
        if (paymentInstrument != null) {
          await this.completeSession(session.sessionId, paymentInstrument);
        }
        break;

      case UcpCheckoutStatus.COMPLETED:
        await this.handleCompleted(session);
        break;

      case UcpCheckoutStatus.CANCELED:
        throw new CommerceException(
          CommerceErrorCodes.SESSION_CANCELED,
          `Checkout session ${session.sessionId} was canceled by the merchant`,
          HttpStatus.UNPROCESSABLE_ENTITY,
        );
    }
  }

  private async handleCompleted(session: CheckoutSession): Promise<void> {
    const eventId = randomUUID();
    const envelope = {
      eventId,
      eventType: 'order.confirmed',
      version: '1.0',
      timestamp: new Date().toISOString(),
      source: 'checkout-service',
      payload: {
        ucpOrderId: session.ucpOrderId,
        ucpOrderPermalink: session.ucpOrderPermalink,
        checkoutId: session.sessionId,
        customerId: session.customerId,
        merchantId: session.merchantId,
        lineItems: session.lineItemsSnapshot,
        totals: session.totalsSnapshot,
      },
    };

    await this.orderEventsQueue.add('order.confirmed', envelope);
  }

  private emitStatusLog(
    sessionId: string,
    fromStatus: UcpCheckoutStatus,
    toStatus: UcpCheckoutStatus,
  ): void {
    this.logger.log(
      JSON.stringify({
        sessionId,
        fromStatus,
        toStatus,
        timestamp: new Date().toISOString(),
      }),
    );
  }
}
