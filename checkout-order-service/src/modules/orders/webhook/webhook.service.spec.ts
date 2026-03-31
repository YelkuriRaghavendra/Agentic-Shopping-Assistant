import { Test } from '@nestjs/testing';
import { getRepositoryToken } from '@nestjs/typeorm';
import { getQueueToken } from '@nestjs/bull';
import { WebhookService } from './webhook.service';
import { WebhookEvent } from './webhook-event.entity';
import { WebhookVerificationService } from '../../ucp-client/verification/webhook-verification.service';

// ── Mocks ──────────────────────────────────────────────────────────────────

const mockWebhookEventRepo = {
  findOne: jest.fn(),
  create: jest.fn(),
  save: jest.fn(),
};

const mockWebhookQueue = {
  add: jest.fn(),
};

const mockVerificationService = {
  verifyWebhook: jest.fn(),
};

// ── Helpers ────────────────────────────────────────────────────────────────

const validPayload = {
  event_id: 'evt-123',
  event_type: 'order.shipped',
  order_id: 'ucp-ord-1',
};

const rawBody = Buffer.from(JSON.stringify(validPayload));

// ── Tests ──────────────────────────────────────────────────────────────────

describe('WebhookService', () => {
  let service: WebhookService;

  beforeEach(async () => {
    jest.clearAllMocks();
    const module = await Test.createTestingModule({
      providers: [
        WebhookService,
        { provide: getRepositoryToken(WebhookEvent), useValue: mockWebhookEventRepo },
        { provide: getQueueToken('webhook-ingestion'), useValue: mockWebhookQueue },
        { provide: WebhookVerificationService, useValue: mockVerificationService },
      ],
    }).compile();
    service = module.get(WebhookService);
  });

  describe('ingest', () => {
    it('returns accepted=false when signature is invalid', async () => {
      mockVerificationService.verifyWebhook.mockResolvedValue(false);

      const result = await service.ingest({
        merchantId: 'merch-1',
        signature: 'bad-sig',
        rawBody,
        payload: validPayload,
      });

      expect(result.accepted).toBe(false);
      expect(result.duplicate).toBe(false);
      expect(mockWebhookEventRepo.save).not.toHaveBeenCalled();
      expect(mockWebhookQueue.add).not.toHaveBeenCalled();
    });

    it('returns accepted=true, duplicate=true for duplicate event_id', async () => {
      mockVerificationService.verifyWebhook.mockResolvedValue(true);
      mockWebhookEventRepo.findOne.mockResolvedValue({ eventId: 'evt-123' });

      const result = await service.ingest({
        merchantId: 'merch-1',
        signature: 'valid-sig',
        rawBody,
        payload: validPayload,
      });

      expect(result.accepted).toBe(true);
      expect(result.duplicate).toBe(true);
      expect(result.eventId).toBe('evt-123');
      expect(mockWebhookEventRepo.save).not.toHaveBeenCalled();
      expect(mockWebhookQueue.add).not.toHaveBeenCalled();
    });

    it('inserts webhook_events record and enqueues for new valid event', async () => {
      mockVerificationService.verifyWebhook.mockResolvedValue(true);
      mockWebhookEventRepo.findOne.mockResolvedValue(null);
      const record = { eventId: 'evt-123', status: 'queued', signatureVerified: true };
      mockWebhookEventRepo.create.mockReturnValue(record);
      mockWebhookEventRepo.save.mockResolvedValue(record);
      mockWebhookQueue.add.mockResolvedValue(undefined);

      const result = await service.ingest({
        merchantId: 'merch-1',
        signature: 'valid-sig',
        rawBody,
        payload: validPayload,
      });

      expect(result.accepted).toBe(true);
      expect(result.duplicate).toBe(false);
      expect(result.eventId).toBe('evt-123');
      expect(mockWebhookEventRepo.save).toHaveBeenCalledWith(
        expect.objectContaining({ signatureVerified: true, status: 'queued' }),
      );
      expect(mockWebhookQueue.add).toHaveBeenCalledWith(
        'ucp.order.event',
        expect.objectContaining({ eventId: 'evt-123', merchantId: 'merch-1' }),
        expect.any(Object),
      );
    });

    it('calls verifyWebhook with correct merchantId, signature, and rawBody', async () => {
      mockVerificationService.verifyWebhook.mockResolvedValue(false);

      await service.ingest({
        merchantId: 'merch-1',
        signature: 'test-sig',
        rawBody,
        payload: validPayload,
      });

      expect(mockVerificationService.verifyWebhook).toHaveBeenCalledWith(
        'merch-1',
        'test-sig',
        rawBody,
      );
    });

    it('generates a random eventId when payload has no event_id', async () => {
      mockVerificationService.verifyWebhook.mockResolvedValue(true);
      mockWebhookEventRepo.findOne.mockResolvedValue(null);
      const record = { eventId: 'generated-id', status: 'queued', signatureVerified: true };
      mockWebhookEventRepo.create.mockReturnValue(record);
      mockWebhookEventRepo.save.mockResolvedValue(record);
      mockWebhookQueue.add.mockResolvedValue(undefined);

      const payloadWithoutId = { event_type: 'order.shipped', order_id: 'ucp-ord-1' };
      const result = await service.ingest({
        merchantId: 'merch-1',
        signature: 'valid-sig',
        rawBody: Buffer.from(JSON.stringify(payloadWithoutId)),
        payload: payloadWithoutId,
      });

      expect(result.accepted).toBe(true);
      expect(result.eventId).toBeTruthy();
    });
  });
});
