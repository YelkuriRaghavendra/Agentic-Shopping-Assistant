import { Test } from '@nestjs/testing';
import { InternalServerErrorException } from '@nestjs/common';
import { AuditService } from './audit.service';

// ── Mocks ──────────────────────────────────────────────────────────────────

function makeEntityManager(queryResult: unknown = undefined, shouldThrow = false) {
  return {
    query: jest.fn().mockImplementation(() => {
      if (shouldThrow) return Promise.reject(new Error('DB error'));
      return Promise.resolve(queryResult);
    }),
  };
}

// ── Tests ──────────────────────────────────────────────────────────────────

describe('AuditService', () => {
  let service: AuditService;

  beforeEach(async () => {
    const module = await Test.createTestingModule({
      providers: [AuditService],
    }).compile();
    service = module.get(AuditService);
  });

  describe('write', () => {
    it('inserts an audit log entry via raw SQL', async () => {
      const em = makeEntityManager();

      await service.write(em as any, {
        orderId: 'order-1',
        actor: 'system',
        actionType: 'order_created',
        beforeState: null,
        afterState: { status: 'processing' },
        source: 'system',
      });

      expect(em.query).toHaveBeenCalledWith(
        expect.stringContaining('INSERT INTO orders.audit_log'),
        expect.arrayContaining(['order-1', 'system', 'order_created']),
      );
    });

    it('throws InternalServerErrorException when INSERT fails', async () => {
      const em = makeEntityManager(undefined, true);

      await expect(
        service.write(em as any, {
          orderId: 'order-1',
          actor: 'system',
          actionType: 'order_created',
          beforeState: null,
          afterState: { status: 'processing' },
          source: 'system',
        }),
      ).rejects.toThrow(InternalServerErrorException);
    });

    it('passes beforeState as null when not provided', async () => {
      const em = makeEntityManager();

      await service.write(em as any, {
        orderId: 'order-1',
        actor: 'customer',
        actionType: 'cancelled',
        beforeState: null,
        afterState: { status: 'cancelled' },
        source: 'api',
      });

      const callArgs = em.query.mock.calls[0][1];
      // beforeState is the 5th parameter (index 4)
      expect(callArgs[4]).toBeNull();
    });

    it('serializes beforeState and afterState as JSON strings', async () => {
      const em = makeEntityManager();
      const beforeState = { status: 'processing' };
      const afterState = { status: 'cancelled' };

      await service.write(em as any, {
        orderId: 'order-1',
        actor: 'customer',
        actionType: 'cancelled',
        beforeState,
        afterState,
        source: 'api',
      });

      const callArgs = em.query.mock.calls[0][1];
      expect(callArgs[4]).toBe(JSON.stringify(beforeState));
      expect(callArgs[5]).toBe(JSON.stringify(afterState));
    });

    it('uses null for ipAddress when not provided', async () => {
      const em = makeEntityManager();

      await service.write(em as any, {
        orderId: 'order-1',
        actor: 'system',
        actionType: 'order_created',
        beforeState: null,
        afterState: {},
        source: 'system',
      });

      const callArgs = em.query.mock.calls[0][1];
      // ipAddress is the 8th parameter (index 7)
      expect(callArgs[7]).toBeNull();
    });
  });
});
