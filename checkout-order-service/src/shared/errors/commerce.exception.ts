import { HttpException, HttpStatus } from '@nestjs/common';

export class CommerceException extends HttpException {
  constructor(
    public readonly errorCode: string,
    message: string,
    statusCode: HttpStatus = HttpStatus.BAD_REQUEST,
  ) {
    super({ errorCode, message }, statusCode);
  }
}

export const CommerceErrorCodes = {
  // Checkout / cart
  OUT_OF_STOCK: 'out_of_stock',
  LINE_ITEM_LIMIT_EXCEEDED: 'line_item_limit_exceeded',
  CHECKOUT_LOCKED: 'checkout_locked',
  SESSION_CANCELED: 'session_canceled',
  VALIDATION: 'validation',

  // Payment
  PAYMENT_FAILED: 'payment_failed',
  PAYMENT_INSTRUMENT_REQUIRED: 'payment_instrument_required',

  // Promo / tax
  PROMO_INVALID: 'promo_invalid',

  // Orders
  CANCELLATION_NOT_ALLOWED: 'cancellation_not_allowed',
  RETURN_NOT_ELIGIBLE: 'return_not_eligible',
  NOT_FOUND: 'not_found',

  // UCP platform
  UCP_UNAVAILABLE: 'ucp_unavailable',
  MERCHANT_PROFILE_UNAVAILABLE: 'merchant_profile_unavailable',
  IDEMPOTENCY_CONFLICT: 'idempotency_conflict',

  // Webhooks
  WEBHOOK_SIGNATURE_INVALID: 'webhook_signature_invalid',
} as const;

export type CommerceErrorCode = (typeof CommerceErrorCodes)[keyof typeof CommerceErrorCodes];
