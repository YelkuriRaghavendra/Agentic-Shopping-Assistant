import { Test } from '@nestjs/testing';
import { getRepositoryToken } from '@nestjs/typeorm';
import { getQueueToken } from '@nestjs/bull';
import { HttpStatus } from '@nestjs/common';
import { CheckoutSessionService } from './checkout-session.service';
import { CheckoutSession } from './checkout-session.entity';
import { UcpCheckoutClient } from '../../ucp-client/checkout-client/ucp-checkout.client';
import { UcpCheckoutStatus } from '../../../shared/types/ucp-checkout-status.enum';
import { CommerceException, CommerceErrorCodes } from '../../../shared/errors/commerce.exception';

const mockRepo = {
  findOne: jest.fn(),
  save: jest.fn(),
  create: jest.fn(),
};

const mockUcpClient = {
  createCheckoutSession: jest.fn(),
  updateCheckoutSession: jest.fn(),
  completeCheckoutSession: jest.fn(),
  cancelCheckoutSession: jest.fn(),
  getCheckoutSession: jest.fn(),
};

const mockQueue = {
  add: jest.fn(),
};

const lineItems = [{ item: { id: 'p1', title: 'Shoe', price: 1000 }, quantity: 1 }];
const paymentInstrument = { type: 'card', token: 'tok_123' };

function makeSession(overrides: Partial<CheckoutSession> = {}): CheckoutSession {
  return {
    sessionId: 'sess-1',
    customerId: 'cust-1',
    merchantId: 'merch-1',
    ucpCheckoutId: 'chk_123',
    ucpStatus: UcpCheckoutStatus.INCOMPLETE,
    continueUrl: null,
    expiresAt: null,
    lineItemsSnapshot: lineItems,
    buyerSnapshot: null,
    contextSnapshot: null,
    paymentHandlers: null,
    totalsSnapshot: null,
    ucpOrderId: null,
    ucpOrderPermalink: null,
    createdAt: new Date(),
    updatedAt: new Date(),
    ...overrides,
  } as CheckoutSession;
}

describe('CheckoutSessionService', () => {
  let service: CheckoutSessionService;

  beforeEach(async () => {
    jest.clearAllMocks();
    const module = await Test.createTestingModule({
      providers: [
        CheckoutSessionService,
        { provide: getRepositoryToken(CheckoutSession), useValue: mockRepo },
        { provide: UcpCheckoutClient, useValue: mockUcpClient },
        { provide: getQueueToken('order-events'), useValue: mockQueue },
      ],
    }).compile();
    service = module.get(CheckoutSessionService);
  });

  // ── createSession ──────────────────────────────────────────────────────────

  describe('createSession', () => {
    it('calls UcpCheckoutClient.createCheckoutSession and saves session', async () => {
      const ucpResponse = { id: 'chk_123', status: 'incomplete', totals: null, payment_handlers: null, expires_at: null, continue_url: null };
      mockUcpClient.createCheckoutSession.mockResolvedValue(ucpResponse);
      const session = makeSession();
      mockRepo.create.mockReturnValue(session);
      mockRepo.save.mockResolvedValue(session);

      const result = await service.createSession('merch-1', 'cust-1', lineItems);

      expect(mockUcpClient.createCheckoutSession).toHaveBeenCalledWith(
        'merch-1',
        expect.objectContaining({ line_items: lineItems }),
        expect.any(String),
      );
      expect(mockRepo.save).toHaveBeenCalled();
      expect(result).toBe(session);
    });

    it('sets ucpStatus from UCP response', async () => {
      const ucpResponse = { id: 'chk_123', status: 'ready_for_complete', totals: null, payment_handlers: null, expires_at: null, continue_url: null };
      mockUcpClient.createCheckoutSession.mockResolvedValue(ucpResponse);
      const session = makeSession({ ucpStatus: UcpCheckoutStatus.READY_FOR_COMPLETE });
      mockRepo.create.mockReturnValue(session);
      mockRepo.save.mockResolvedValue(session);

      const result = await service.createSession('merch-1', 'cust-1', lineItems);

      expect(result.ucpStatus).toBe(UcpCheckoutStatus.READY_FOR_COMPLETE);
    });

    it('stores continue_url when UCP returns requires_escalation', async () => {
      const ucpResponse = { id: 'chk_123', status: 'requires_escalation', totals: null, payment_handlers: null, expires_at: null, continue_url: 'https://escalate.example.com' };
      mockUcpClient.createCheckoutSession.mockResolvedValue(ucpResponse);
      const session = makeSession({ ucpStatus: UcpCheckoutStatus.REQUIRES_ESCALATION, continueUrl: 'https://escalate.example.com' });
      mockRepo.create.mockReturnValue(session);
      mockRepo.save.mockResolvedValue(session);

      const result = await service.createSession('merch-1', 'cust-1', lineItems);

      expect(result.continueUrl).toBe('https://escalate.example.com');
    });
  });

  // ── updateSession ──────────────────────────────────────────────────────────

  describe('updateSession', () => {
    it('loads session, calls UcpCheckoutClient.updateCheckoutSession, updates snapshot', async () => {
      const session = makeSession();
      mockRepo.findOne.mockResolvedValue(session);
      const ucpResponse = { id: 'chk_123', status: 'incomplete', totals: { subtotal_cents: 2000, tax_cents: 200, grand_total_cents: 2200 }, continue_url: null };
      mockUcpClient.updateCheckoutSession.mockResolvedValue(ucpResponse);
      mockRepo.save.mockResolvedValue(session);

      const newItems = [{ item: { id: 'p2', title: 'Hat', price: 2000 }, quantity: 1 }];
      const result = await service.updateSession('sess-1', newItems);

      expect(mockRepo.findOne).toHaveBeenCalledWith({ where: { sessionId: 'sess-1' } });
      expect(mockUcpClient.updateCheckoutSession).toHaveBeenCalledWith(
        'merch-1',
        'chk_123',
        expect.objectContaining({ line_items: newItems }),
        expect.any(String),
      );
      expect(result.lineItemsSnapshot).toEqual(newItems);
    });

    it('throws SESSION_CANCELED when session is canceled', async () => {
      const session = makeSession({ ucpStatus: UcpCheckoutStatus.CANCELED });
      mockRepo.findOne.mockResolvedValue(session);

      await expect(service.updateSession('sess-1', lineItems)).rejects.toMatchObject({
        errorCode: CommerceErrorCodes.SESSION_CANCELED,
      });
    });

    it('throws NOT_FOUND when session does not exist', async () => {
      mockRepo.findOne.mockResolvedValue(null);

      await expect(service.updateSession('missing', lineItems)).rejects.toMatchObject({
        errorCode: CommerceErrorCodes.NOT_FOUND,
      });
    });
  });

  // ── completeSession ────────────────────────────────────────────────────────

  describe('completeSession', () => {
    it('calls UcpCheckoutClient.completeCheckoutSession and updates status', async () => {
      const session = makeSession();
      mockRepo.findOne.mockResolvedValue(session);
      const ucpResponse = { status: 'complete_in_progress', totals: null };
      mockUcpClient.completeCheckoutSession.mockResolvedValue(ucpResponse);
      mockRepo.save.mockResolvedValue(session);

      const result = await service.completeSession('sess-1', paymentInstrument);

      expect(mockUcpClient.completeCheckoutSession).toHaveBeenCalledWith(
        'merch-1',
        'chk_123',
        expect.objectContaining({ payment_instrument: paymentInstrument }),
        expect.any(String),
      );
      expect(result.ucpStatus).toBe(UcpCheckoutStatus.COMPLETE_IN_PROGRESS);
    });

    it('throws SESSION_CANCELED when session is canceled', async () => {
      const session = makeSession({ ucpStatus: UcpCheckoutStatus.CANCELED });
      mockRepo.findOne.mockResolvedValue(session);

      await expect(service.completeSession('sess-1', paymentInstrument)).rejects.toMatchObject({
        errorCode: CommerceErrorCodes.SESSION_CANCELED,
      });
    });

    it('publishes order.confirmed event when UCP returns completed', async () => {
      const session = makeSession();
      mockRepo.findOne.mockResolvedValue(session);
      const ucpResponse = { status: 'completed', totals: null };
      mockUcpClient.completeCheckoutSession.mockResolvedValue(ucpResponse);
      mockRepo.save.mockResolvedValue(session);

      await service.completeSession('sess-1', paymentInstrument);

      expect(mockQueue.add).toHaveBeenCalledWith(
        'order.confirmed',
        expect.objectContaining({ eventType: 'order.confirmed' }),
      );
    });
  });

  // ── cancelSession ──────────────────────────────────────────────────────────

  describe('cancelSession', () => {
    it('calls UcpCheckoutClient.cancelCheckoutSession and sets status to canceled', async () => {
      const session = makeSession();
      mockRepo.findOne.mockResolvedValue(session);
      mockUcpClient.cancelCheckoutSession.mockResolvedValue({ status: 'canceled' });
      mockRepo.save.mockResolvedValue(session);

      const result = await service.cancelSession('sess-1');

      expect(mockUcpClient.cancelCheckoutSession).toHaveBeenCalledWith(
        'merch-1',
        'chk_123',
        expect.any(String),
      );
      expect(result.ucpStatus).toBe(UcpCheckoutStatus.CANCELED);
    });

    it('throws SESSION_CANCELED when session is already canceled', async () => {
      const session = makeSession({ ucpStatus: UcpCheckoutStatus.CANCELED });
      mockRepo.findOne.mockResolvedValue(session);

      await expect(service.cancelSession('sess-1')).rejects.toMatchObject({
        errorCode: CommerceErrorCodes.SESSION_CANCELED,
      });
    });
  });

  // ── getSession ─────────────────────────────────────────────────────────────

  describe('getSession', () => {
    it('returns session when found', async () => {
      const session = makeSession();
      mockRepo.findOne.mockResolvedValue(session);

      const result = await service.getSession('sess-1');

      expect(result).toBe(session);
    });

    it('throws NOT_FOUND when session does not exist', async () => {
      mockRepo.findOne.mockResolvedValue(null);

      await expect(service.getSession('missing')).rejects.toMatchObject({
        errorCode: CommerceErrorCodes.NOT_FOUND,
      });
    });
  });

  // ── status reactions ───────────────────────────────────────────────────────

  describe('status reactions', () => {
    it('requires_escalation: stores continue_url, does not auto-complete', async () => {
      const session = makeSession();
      mockRepo.findOne.mockResolvedValue(session);
      const ucpResponse = { status: 'requires_escalation', totals: null, continue_url: 'https://escalate.example.com' };
      mockUcpClient.updateCheckoutSession.mockResolvedValue(ucpResponse);
      mockRepo.save.mockResolvedValue(session);

      await service.updateSession('sess-1', lineItems);

      expect(mockUcpClient.completeCheckoutSession).not.toHaveBeenCalled();
      expect(session.continueUrl).toBe('https://escalate.example.com');
    });

    it('ready_for_complete without paymentInstrument: does not auto-call completeSession', async () => {
      const session = makeSession();
      mockRepo.findOne.mockResolvedValue(session);
      mockUcpClient.updateCheckoutSession.mockResolvedValue({ status: 'ready_for_complete', totals: null, continue_url: null });
      mockRepo.save.mockResolvedValue(session);

      // updateSession passes null paymentInstrument to reactToStatus, so no auto-complete
      await service.updateSession('sess-1', lineItems, undefined, undefined);

      expect(mockUcpClient.completeCheckoutSession).not.toHaveBeenCalled();
    });

    it('ready_for_complete + paymentInstrument present: auto-calls completeSession', async () => {
      const session = makeSession();
      mockRepo.findOne.mockResolvedValue(session);
      // Use a counter to return different values on successive calls
      let callCount = 0;
      mockUcpClient.completeCheckoutSession.mockImplementation(() => {
        callCount++;
        if (callCount === 1) return Promise.resolve({ status: 'ready_for_complete', totals: null });
        return Promise.resolve({ status: 'complete_in_progress', totals: null });
      });
      mockRepo.save.mockResolvedValue(session);

      await service.completeSession('sess-1', paymentInstrument);

      expect(mockUcpClient.completeCheckoutSession).toHaveBeenCalledTimes(2);
    });

    it('completed: publishes order.confirmed to order-events queue', async () => {
      const session = makeSession();
      mockRepo.findOne.mockResolvedValue(session);
      mockUcpClient.completeCheckoutSession.mockResolvedValue({ status: 'completed', totals: null });
      mockRepo.save.mockResolvedValue(session);
      mockQueue.add.mockResolvedValue(undefined);

      await service.completeSession('sess-1', paymentInstrument);

      expect(mockQueue.add).toHaveBeenCalledWith(
        'order.confirmed',
        expect.objectContaining({
          eventType: 'order.confirmed',
          source: 'checkout-service',
        }),
      );
    });

    it('canceled status from UCP throws SESSION_CANCELED', async () => {
      const session = makeSession();
      mockRepo.findOne.mockResolvedValue(session);
      mockUcpClient.completeCheckoutSession.mockResolvedValue({ status: 'canceled', totals: null });
      mockRepo.save.mockResolvedValue(session);

      await expect(service.completeSession('sess-1', paymentInstrument)).rejects.toMatchObject({
        errorCode: CommerceErrorCodes.SESSION_CANCELED,
      });
    });
  });
});
