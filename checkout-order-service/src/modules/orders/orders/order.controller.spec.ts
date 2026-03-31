import { Test } from '@nestjs/testing';
import { getRepositoryToken } from '@nestjs/typeorm';
import { HttpStatus } from '@nestjs/common';
import { OrderController } from './order.controller';
import { Order } from './order.entity';
import { OrderService } from './order.service';
import { UcpOrderStatus } from '../../../shared/types/ucp-order-status.enum';
import { CommerceException, CommerceErrorCodes } from '../../../shared/errors/commerce.exception';

// ── Mocks ──────────────────────────────────────────────────────────────────

const mockOrderRepo = {
  findOne: jest.fn(),
  createQueryBuilder: jest.fn(),
};

const mockOrderService = {
  cancelOrder: jest.fn(),
  returnOrder: jest.fn(),
};

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
    createdAt: new Date('2024-01-01T00:00:00Z'),
    updatedAt: new Date('2024-01-01T00:00:00Z'),
    statusHistory: [],
    ...overrides,
  } as Order;
}

// ── Tests ──────────────────────────────────────────────────────────────────

describe('OrderController', () => {
  let controller: OrderController;

  beforeEach(async () => {
    jest.clearAllMocks();
    const module = await Test.createTestingModule({
      controllers: [OrderController],
      providers: [
        { provide: getRepositoryToken(Order), useValue: mockOrderRepo },
        { provide: OrderService, useValue: mockOrderService },
      ],
    }).compile();
    controller = module.get(OrderController);
  });

  // ── GET /commerce/orders ───────────────────────────────────────────────────

  describe('listOrders', () => {
    it('returns paginated orders for a customer', async () => {
      const orders = [makeOrder(), makeOrder({ orderId: 'order-2' })];
      const qb = {
        where: jest.fn().mockReturnThis(),
        orderBy: jest.fn().mockReturnThis(),
        addOrderBy: jest.fn().mockReturnThis(),
        take: jest.fn().mockReturnThis(),
        andWhere: jest.fn().mockReturnThis(),
        getMany: jest.fn().mockResolvedValue(orders),
      };
      mockOrderRepo.createQueryBuilder.mockReturnValue(qb);

      const result = await controller.listOrders({ customerId: 'cust-1', limit: 20 });

      expect(result.data).toHaveLength(2);
      expect(result.nextCursor).toBeNull();
    });

    it('returns nextCursor when there are more results', async () => {
      // Return limit+1 rows to trigger cursor generation
      const orders = Array.from({ length: 21 }, (_, i) =>
        makeOrder({ orderId: `order-${i}`, createdAt: new Date(`2024-01-${String(i + 1).padStart(2, '0')}T00:00:00Z`) }),
      );
      const qb = {
        where: jest.fn().mockReturnThis(),
        orderBy: jest.fn().mockReturnThis(),
        addOrderBy: jest.fn().mockReturnThis(),
        take: jest.fn().mockReturnThis(),
        andWhere: jest.fn().mockReturnThis(),
        getMany: jest.fn().mockResolvedValue(orders),
      };
      mockOrderRepo.createQueryBuilder.mockReturnValue(qb);

      const result = await controller.listOrders({ customerId: 'cust-1', limit: 20 });

      expect(result.data).toHaveLength(20);
      expect(result.nextCursor).toBeTruthy();
    });

    it('scopes query to customerId', async () => {
      const qb = {
        where: jest.fn().mockReturnThis(),
        orderBy: jest.fn().mockReturnThis(),
        addOrderBy: jest.fn().mockReturnThis(),
        take: jest.fn().mockReturnThis(),
        andWhere: jest.fn().mockReturnThis(),
        getMany: jest.fn().mockResolvedValue([]),
      };
      mockOrderRepo.createQueryBuilder.mockReturnValue(qb);

      await controller.listOrders({ customerId: 'cust-1' });

      expect(qb.where).toHaveBeenCalledWith(
        expect.stringContaining('customerId'),
        expect.objectContaining({ customerId: 'cust-1' }),
      );
    });
  });

  // ── GET /commerce/orders/:id ───────────────────────────────────────────────

  describe('getOrder', () => {
    it('returns order when found and belongs to customer', async () => {
      const order = makeOrder();
      mockOrderRepo.findOne.mockResolvedValue(order);

      const result = await controller.getOrder('order-1', { customerId: 'cust-1' });

      expect(result).toBe(order);
    });

    it('throws NOT_FOUND when order does not exist', async () => {
      mockOrderRepo.findOne.mockResolvedValue(null);

      await expect(controller.getOrder('missing', { customerId: 'cust-1' })).rejects.toMatchObject({
        errorCode: CommerceErrorCodes.NOT_FOUND,
      });
    });

    it('throws NOT_FOUND when order belongs to different customer (cross-customer isolation)', async () => {
      const order = makeOrder({ customerId: 'other-cust' });
      mockOrderRepo.findOne.mockResolvedValue(order);

      await expect(controller.getOrder('order-1', { customerId: 'cust-1' })).rejects.toMatchObject({
        errorCode: CommerceErrorCodes.NOT_FOUND,
      });
    });
  });

  // ── POST /commerce/orders/:id/cancel ──────────────────────────────────────

  describe('cancelOrder', () => {
    it('delegates to OrderService.cancelOrder', async () => {
      const cancelledOrder = makeOrder({ status: UcpOrderStatus.CANCELLED });
      mockOrderService.cancelOrder.mockResolvedValue(cancelledOrder);

      const result = await controller.cancelOrder(
        'order-1',
        { reason: 'Changed my mind', customerId: 'cust-1' },
        { customerId: 'cust-1' },
      );

      expect(mockOrderService.cancelOrder).toHaveBeenCalledWith(
        'order-1',
        'cust-1',
        'Changed my mind',
      );
      expect(result.status).toBe(UcpOrderStatus.CANCELLED);
    });

    it('propagates CANCELLATION_NOT_ALLOWED error from service', async () => {
      mockOrderService.cancelOrder.mockRejectedValue(
        new CommerceException(
          CommerceErrorCodes.CANCELLATION_NOT_ALLOWED,
          'Fulfilled orders cannot be cancelled',
          HttpStatus.UNPROCESSABLE_ENTITY,
        ),
      );

      await expect(
        controller.cancelOrder('order-1', { customerId: 'cust-1' }, { customerId: 'cust-1' }),
      ).rejects.toMatchObject({ errorCode: CommerceErrorCodes.CANCELLATION_NOT_ALLOWED });
    });
  });

  // ── POST /commerce/orders/:id/return ──────────────────────────────────────

  describe('returnOrder', () => {
    it('delegates to OrderService.returnOrder', async () => {
      const returnedOrder = makeOrder({ status: UcpOrderStatus.RETURN_REQUESTED });
      mockOrderService.returnOrder.mockResolvedValue(returnedOrder);

      const result = await controller.returnOrder(
        'order-1',
        { reason: 'Defective', customerId: 'cust-1' },
        { customerId: 'cust-1' },
      );

      expect(mockOrderService.returnOrder).toHaveBeenCalledWith(
        'order-1',
        'cust-1',
        'Defective',
      );
      expect(result.status).toBe(UcpOrderStatus.RETURN_REQUESTED);
    });

    it('propagates RETURN_NOT_ELIGIBLE error from service', async () => {
      mockOrderService.returnOrder.mockRejectedValue(
        new CommerceException(
          CommerceErrorCodes.RETURN_NOT_ELIGIBLE,
          'Returns are only allowed for fulfilled orders',
          HttpStatus.UNPROCESSABLE_ENTITY,
        ),
      );

      await expect(
        controller.returnOrder('order-1', { customerId: 'cust-1' }, { customerId: 'cust-1' }),
      ).rejects.toMatchObject({ errorCode: CommerceErrorCodes.RETURN_NOT_ELIGIBLE });
    });
  });
});
