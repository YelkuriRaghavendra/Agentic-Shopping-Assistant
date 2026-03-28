import { Test } from '@nestjs/testing';
import { getRepositoryToken } from '@nestjs/typeorm';
import { DataSource } from 'typeorm';
import { OrderService } from './order.service';
import { Order } from './order.entity';
import { OrderStatusHistory } from './order-status-history.entity';
import { AuditService } from '../audit/audit.service';
import { UcpOrderStatus } from '../../../shared/types/ucp-order-status.enum';
import { CommerceErrorCodes } from '../../../shared/errors/commerce.exception';

// ── Mocks ──────────────────────────────────────────────────────────────────

const mockOrderRepo = { findOne: jest.fn(), save: jest.fn(), create: jest.fn() };
const mockHistoryRepo = { save: jest.fn(), create: jest.fn() };
const mockAuditService = { write: jest.fn() };

// EntityManager mock used inside transactions
function makeEntityManager(savedOrder: Partial<Order> = {}) {
  return {
    create: jest.fn((_Entity: unknown, data: Record<string, unknown>) => ({ ...data })),
    save: jest.fn().mockResolvedValue(savedOrder),
    query: jest.fn().mockResolvedValue(undefined),
    findOne: jest.fn(),
  };
}

// DataSource mock that runs the callback with a fake EntityManager
function makeDataSource(em: ReturnType<typeof makeEntityManager>) {
  return {
    transaction: jest.fn((cb: (em: unknown) => Promise<unknown>) => cb(em)),
  };
}

// ── Helpers ────────────────────────────────────────────────────────────────

function makeOrder(overrides: Partial<Order> = {}): Order {
  return {
    orderId: 'order-1',
    customerId: 'cust-1',
    checkoutId: 'sess-1',
    merchantId: 'merch-1',
    ucpOrderId: 'ucp-ord-1',
    permalinkUrl: 'https://merchant.example.com/orders/1',
    status: UcpOrderStatus.PROCESSING,
    lineItems: [],
    fulfillment: { events: [] } as any,
    adjustments: [],
    totals: { subtotal_cents: 1000, tax_cents: 100, grand_total_cents: 1100 },
    createdAt: new Date(),
    updatedAt: new Date(),
    statusHistory: [],
    ...overrides,
  } as Order;
}

const confirmedPayload = {
  ucpOrderId: 'ucp-ord-1',
  ucpOrderPermalink: 'https://merchant.example.com/orders/1',
  checkoutId: 'sess-1',
  customerId: 'cust-1',
  merchantId: 'merch-1',
  lineItems: [],
  totals: { subtotal_cents: 1000, tax_cents: 100, grand_total_cents: 1100 },
};

// ── Tests ──────────────────────────────────────────────────────────────────

describe('OrderService', () => {
  let service: OrderService;

  beforeEach(async () => {
    jest.clearAllMocks();
    mockAuditService.write.mockResolvedValue(undefined);
  });

  async function buildService(em: ReturnType<typeof makeEntityManager>) {
    const dataSource = makeDataSource(em);
    const module = await Test.createTestingModule({
      providers: [
        OrderService,
        { provide: getRepositoryToken(Order), useValue: mockOrderRepo },
        { provide: getRepositoryToken(OrderStatusHistory), useValue: mockHistoryRepo },
        { provide: DataSource, useValue: dataSource },
        { provide: AuditService, useValue: mockAuditService },
      ],
    }).compile();
    service = module.get(OrderService);
    return { service, dataSource };
  }

  // ── createFromConfirmedEvent ───────────────────────────────────────────────

  describe('createFromConfirmedEvent', () => {
    it('creates order with status=processing and returns orderId', async () => {
      const savedOrder = makeOrder();
      const em = makeEntityManager(savedOrder);
      const { service } = await buildService(em);

      const result = await service.createFromConfirmedEvent(confirmedPayload);

      expect(result.status).toBe(UcpOrderStatus.PROCESSING);
      expect(result.orderId).toBe(savedOrder.orderId);
    });

    it('writes audit log inside the transaction', async () => {
      const savedOrder = makeOrder();
      const em = makeEntityManager(savedOrder);
      const { service } = await buildService(em);

      await service.createFromConfirmedEvent(confirmedPayload);

      expect(mockAuditService.write).toHaveBeenCalledWith(
        em,
        expect.objectContaining({ actionType: 'order_created', source: 'system' }),
      );
    });

    it('saves initial status history entry', async () => {
      const savedOrder = makeOrder();
      const em = makeEntityManager(savedOrder);
      const { service } = await buildService(em);

      await service.createFromConfirmedEvent(confirmedPayload);

      // em.save should be called twice: once for Order, once for OrderStatusHistory
      // (audit log uses em.query, not em.save)
      expect(em.save).toHaveBeenCalledTimes(2);
    });

    it('rolls back if audit write fails', async () => {
      const savedOrder = makeOrder();
      const em = makeEntityManager(savedOrder);
      mockAuditService.write.mockRejectedValue(new Error('audit failed'));
      const { service } = await buildService(em);

      await expect(service.createFromConfirmedEvent(confirmedPayload)).rejects.toThrow();
    });
  });

  // ── cancelOrder ───────────────────────────────────────────────────────────

  describe('cancelOrder', () => {
    it('cancels a processing order and appends cancellation adjustment', async () => {
      const order = makeOrder({ status: UcpOrderStatus.PROCESSING });
      const savedOrder = makeOrder({ status: UcpOrderStatus.CANCELLED, adjustments: [{ type: 'cancellation', amount_cents: 0, occurred_at: new Date().toISOString() }] as any });
      const em = makeEntityManager(savedOrder);
      em.findOne.mockResolvedValue(order);
      const { service } = await buildService(em);

      const result = await service.cancelOrder('order-1', 'cust-1', 'Changed my mind');

      expect(result.status).toBe(UcpOrderStatus.CANCELLED);
    });

    it('throws CANCELLATION_NOT_ALLOWED for fulfilled orders', async () => {
      const order = makeOrder({ status: UcpOrderStatus.FULFILLED });
      const em = makeEntityManager(makeOrder());
      em.findOne.mockResolvedValue(order);
      const { service } = await buildService(em);

      await expect(service.cancelOrder('order-1', 'cust-1')).rejects.toMatchObject({
        errorCode: CommerceErrorCodes.CANCELLATION_NOT_ALLOWED,
      });
    });

    it('throws CANCELLATION_NOT_ALLOWED for non-processing orders', async () => {
      const order = makeOrder({ status: UcpOrderStatus.CANCELLED });
      const em = makeEntityManager(makeOrder());
      em.findOne.mockResolvedValue(order);
      const { service } = await buildService(em);

      await expect(service.cancelOrder('order-1', 'cust-1')).rejects.toMatchObject({
        errorCode: CommerceErrorCodes.CANCELLATION_NOT_ALLOWED,
      });
    });

    it('throws NOT_FOUND when order does not belong to customer', async () => {
      const order = makeOrder({ customerId: 'other-cust' });
      const em = makeEntityManager(makeOrder());
      em.findOne.mockResolvedValue(order);
      const { service } = await buildService(em);

      await expect(service.cancelOrder('order-1', 'cust-1')).rejects.toMatchObject({
        errorCode: CommerceErrorCodes.NOT_FOUND,
      });
    });

    it('throws NOT_FOUND when order does not exist', async () => {
      const em = makeEntityManager(makeOrder());
      em.findOne.mockResolvedValue(null);
      const { service } = await buildService(em);

      await expect(service.cancelOrder('order-1', 'cust-1')).rejects.toMatchObject({
        errorCode: CommerceErrorCodes.NOT_FOUND,
      });
    });

    it('writes audit log on successful cancellation', async () => {
      const order = makeOrder({ status: UcpOrderStatus.PROCESSING });
      const savedOrder = makeOrder({ status: UcpOrderStatus.CANCELLED });
      const em = makeEntityManager(savedOrder);
      em.findOne.mockResolvedValue(order);
      const { service } = await buildService(em);

      await service.cancelOrder('order-1', 'cust-1');

      expect(mockAuditService.write).toHaveBeenCalledWith(
        em,
        expect.objectContaining({ actionType: 'cancelled', source: 'api' }),
      );
    });
  });

  // ── returnOrder ───────────────────────────────────────────────────────────

  describe('returnOrder', () => {
    it('transitions fulfilled order to return_requested', async () => {
      const order = makeOrder({ status: UcpOrderStatus.FULFILLED });
      const savedOrder = makeOrder({ status: UcpOrderStatus.RETURN_REQUESTED });
      const em = makeEntityManager(savedOrder);
      em.findOne.mockResolvedValue(order);
      const { service } = await buildService(em);

      const result = await service.returnOrder('order-1', 'cust-1', 'Defective item');

      expect(result.status).toBe(UcpOrderStatus.RETURN_REQUESTED);
    });

    it('throws RETURN_NOT_ELIGIBLE for non-fulfilled orders', async () => {
      const order = makeOrder({ status: UcpOrderStatus.PROCESSING });
      const em = makeEntityManager(makeOrder());
      em.findOne.mockResolvedValue(order);
      const { service } = await buildService(em);

      await expect(service.returnOrder('order-1', 'cust-1')).rejects.toMatchObject({
        errorCode: CommerceErrorCodes.RETURN_NOT_ELIGIBLE,
      });
    });

    it('throws RETURN_NOT_ELIGIBLE for cancelled orders', async () => {
      const order = makeOrder({ status: UcpOrderStatus.CANCELLED });
      const em = makeEntityManager(makeOrder());
      em.findOne.mockResolvedValue(order);
      const { service } = await buildService(em);

      await expect(service.returnOrder('order-1', 'cust-1')).rejects.toMatchObject({
        errorCode: CommerceErrorCodes.RETURN_NOT_ELIGIBLE,
      });
    });

    it('throws NOT_FOUND when order does not belong to customer', async () => {
      const order = makeOrder({ customerId: 'other-cust', status: UcpOrderStatus.FULFILLED });
      const em = makeEntityManager(makeOrder());
      em.findOne.mockResolvedValue(order);
      const { service } = await buildService(em);

      await expect(service.returnOrder('order-1', 'cust-1')).rejects.toMatchObject({
        errorCode: CommerceErrorCodes.NOT_FOUND,
      });
    });

    it('writes audit log on successful return request', async () => {
      const order = makeOrder({ status: UcpOrderStatus.FULFILLED });
      const savedOrder = makeOrder({ status: UcpOrderStatus.RETURN_REQUESTED });
      const em = makeEntityManager(savedOrder);
      em.findOne.mockResolvedValue(order);
      const { service } = await buildService(em);

      await service.returnOrder('order-1', 'cust-1');

      expect(mockAuditService.write).toHaveBeenCalledWith(
        em,
        expect.objectContaining({ actionType: 'return_initiated', source: 'api' }),
      );
    });
  });
});
