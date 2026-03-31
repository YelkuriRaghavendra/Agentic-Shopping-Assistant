import { Test } from '@nestjs/testing';
import { CheckoutController } from './checkout.controller';
import { CheckoutSessionService } from './checkout-session.service';
import { UcpCheckoutStatus } from '../../../shared/types/ucp-checkout-status.enum';
import type { CheckoutSession } from './checkout-session.entity';

const mockService = {
  createSession: jest.fn(),
  getSession: jest.fn(),
  updateSession: jest.fn(),
  completeSession: jest.fn(),
  cancelSession: jest.fn(),
};

const lineItems = [{ item: { id: 'p1', title: 'Shoe', price: 1000 }, quantity: 1 }];

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

describe('CheckoutController', () => {
  let controller: CheckoutController;

  beforeEach(async () => {
    jest.clearAllMocks();
    const module = await Test.createTestingModule({
      controllers: [CheckoutController],
      providers: [{ provide: CheckoutSessionService, useValue: mockService }],
    }).compile();
    controller = module.get(CheckoutController);
  });

  describe('POST /commerce/checkout/sessions (createSession)', () => {
    it('calls createSession and returns session', async () => {
      const session = makeSession();
      mockService.createSession.mockResolvedValue(session);

      const dto = { merchant_id: 'merch-1', customer_id: 'cust-1', line_items: lineItems };
      const result = await controller.createSession(dto as any);

      expect(mockService.createSession).toHaveBeenCalledWith('merch-1', 'cust-1', lineItems, undefined, undefined);
      expect(result).toBe(session);
    });

    it('passes buyer and context when provided', async () => {
      const session = makeSession();
      mockService.createSession.mockResolvedValue(session);
      const buyer = { first_name: 'Jane', last_name: 'Doe', email: 'jane@example.com' };
      const context = { address_country: 'US' };

      const dto = { merchant_id: 'merch-1', customer_id: 'cust-1', line_items: lineItems, buyer, context };
      await controller.createSession(dto as any);

      expect(mockService.createSession).toHaveBeenCalledWith('merch-1', 'cust-1', lineItems, buyer, context);
    });
  });

  describe('GET /commerce/checkout/sessions/:id (getSession)', () => {
    it('calls getSession and returns session', async () => {
      const session = makeSession();
      mockService.getSession.mockResolvedValue(session);

      const result = await controller.getSession('sess-1');

      expect(mockService.getSession).toHaveBeenCalledWith('sess-1');
      expect(result).toBe(session);
    });
  });

  describe('PUT /commerce/checkout/sessions/:id (updateSession)', () => {
    it('calls updateSession and returns session', async () => {
      const session = makeSession();
      mockService.updateSession.mockResolvedValue(session);

      const dto = { line_items: lineItems };
      const result = await controller.updateSession('sess-1', dto as any);

      expect(mockService.updateSession).toHaveBeenCalledWith('sess-1', lineItems, undefined, undefined);
      expect(result).toBe(session);
    });
  });

  describe('POST /commerce/checkout/sessions/:id/complete (completeSession)', () => {
    it('calls completeSession and returns session', async () => {
      const session = makeSession({ ucpStatus: UcpCheckoutStatus.COMPLETE_IN_PROGRESS });
      mockService.completeSession.mockResolvedValue(session);

      const dto = { payment_instrument: { type: 'card', token: 'tok_123' } };
      const result = await controller.completeSession('sess-1', dto as any);

      expect(mockService.completeSession).toHaveBeenCalledWith('sess-1', dto.payment_instrument);
      expect(result).toBe(session);
    });
  });

  describe('POST /commerce/checkout/sessions/:id/cancel (cancelSession)', () => {
    it('calls cancelSession and returns session', async () => {
      const session = makeSession({ ucpStatus: UcpCheckoutStatus.CANCELED });
      mockService.cancelSession.mockResolvedValue(session);

      const result = await controller.cancelSession('sess-1');

      expect(mockService.cancelSession).toHaveBeenCalledWith('sess-1');
      expect(result).toBe(session);
    });
  });

  describe('GET /commerce/checkout/sessions/:id/summary (getSessionSummary)', () => {
    it('returns totals converted from cents to display currency', async () => {
      const session = makeSession({
        totalsSnapshot: { subtotal_cents: 10000, tax_cents: 800, grand_total_cents: 10800 },
      });
      mockService.getSession.mockResolvedValue(session);

      const result = await controller.getSessionSummary('sess-1');

      expect(result.subtotal).toBe('100.00');
      expect(result.tax).toBe('8.00');
      expect(result.grand_total).toBe('108.00');
      expect(result.discount).toBe('0.00');
      expect(result.currency).toBe('USD');
    });

    it('calculates grand_total = subtotal + tax - discount', async () => {
      // subtotal=200, tax=10, grand_total=190 → discount=20
      const session = makeSession({
        totalsSnapshot: { subtotal_cents: 20000, tax_cents: 1000, grand_total_cents: 19000 },
      });
      mockService.getSession.mockResolvedValue(session);

      const result = await controller.getSessionSummary('sess-1');

      expect(result.subtotal).toBe('200.00');
      expect(result.tax).toBe('10.00');
      expect(result.grand_total).toBe('190.00');
      expect(result.discount).toBe('20.00'); // 200 + 10 - 190 = 20
    });

    it('returns zeros when totalsSnapshot is null', async () => {
      const session = makeSession({ totalsSnapshot: null });
      mockService.getSession.mockResolvedValue(session);

      const result = await controller.getSessionSummary('sess-1');

      expect(result.subtotal).toBe('0.00');
      expect(result.tax).toBe('0.00');
      expect(result.grand_total).toBe('0.00');
      expect(result.discount).toBe('0.00');
    });

    it('clamps discount to 0 when grand_total > subtotal + tax', async () => {
      // grand_total > subtotal + tax (unusual but should not produce negative discount)
      const session = makeSession({
        totalsSnapshot: { subtotal_cents: 5000, tax_cents: 0, grand_total_cents: 6000 },
      });
      mockService.getSession.mockResolvedValue(session);

      const result = await controller.getSessionSummary('sess-1');

      expect(result.discount).toBe('0.00');
    });
  });
});
