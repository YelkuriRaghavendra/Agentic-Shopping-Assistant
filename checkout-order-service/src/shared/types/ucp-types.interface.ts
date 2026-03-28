/** A single line item in a UCP checkout session or order. Price is in minor units (cents). */
export interface UcpLineItem {
  item: {
    id: string;
    title: string;
    price: number; // cents
  };
  quantity: number;
}

/** Buyer information collected during checkout. */
export interface UcpBuyer {
  first_name: string;
  last_name: string;
  email: string;
  phone_number?: string;
}

/** Contextual hints for checkout (address, locale, etc.). */
export interface UcpContext {
  address_country?: string;
  address_region?: string;
  postal_code?: string;
}

/** Monetary totals — all amounts in minor units (cents). */
export interface UcpTotals {
  subtotal_cents: number;
  tax_cents: number;
  grand_total_cents: number;
}

/** A single fulfillment event from a merchant webhook. */
export interface UcpFulfillmentEvent {
  type: string;           // e.g. 'shipped' | 'delivered' | 'out_for_delivery'
  occurred_at: string;    // ISO 8601
  tracking_number?: string;
  carrier?: string;
  note?: string;
}

/** An order adjustment (discount, return credit, etc.) — append-only. */
export interface UcpAdjustment {
  type: string;           // e.g. 'cancellation' | 'return' | 'discount'
  amount_cents: number;
  occurred_at: string;    // ISO 8601
  reason?: string;
}

/** Full fulfillment payload stored on an order. */
export interface UcpFulfillment {
  expectations?: unknown[];
  events: UcpFulfillmentEvent[];
}

/** Line item as stored on a confirmed order (may include additional merchant fields). */
export interface UcpOrderLineItem extends UcpLineItem {
  [key: string]: unknown;
}
