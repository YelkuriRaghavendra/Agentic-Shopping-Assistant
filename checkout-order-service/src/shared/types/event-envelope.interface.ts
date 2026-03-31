export interface EventEnvelope<T = unknown> {
  eventId: string;       // UUID, idempotency key
  eventType: string;     // e.g. "order.confirmed"
  version: string;       // "1.0"
  timestamp: string;     // ISO 8601
  source: string;        // "checkout-service" | "order-service" | "webhook-handler"
  payload: T;
}
