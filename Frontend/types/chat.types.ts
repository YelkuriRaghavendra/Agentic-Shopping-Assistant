// Types aligned with backend Pydantic DTOs

export type MessageRole = "user" | "bot";
export type Channel = "web" | "mobile" | "whatsapp" | "sdk";
export type GuardrailStatus = "passed" | "blocked" | "warned";
export type ChipType = "quick_reply" | "refine" | "action" | "navigate";

// ── Inbound (sent to API) ─────────────────────────────────────────────────

export interface ChatRequest {
  message: string;
  customer_id?: string;
  session_id?: string;
  channel?: Channel;
  filters?: Record<string, unknown>;
}

export interface CustomerCreateRequest {
  external_id?: string;
  email?: string;
  name?: string;
  phone?: string;
  profile?: Record<string, unknown>;
}

export interface SessionCreateRequest {
  customer_id?: string;
  channel?: Channel;
}

export interface FeedbackRequest {
  rating: -1 | 1;
  comment?: string;
  feedback_type?: "helpful" | "wrong_product" | "bad_link" | "hallucination" | "other";
}

// ── Outbound (received from API) ──────────────────────────────────────────

export interface ProductCardDTO {
  productId: string;
  productName: string;
  price: number | null;
  rating: number | null;
  productImageUrl: string | null;
}

export interface SuggestionChip {
  label: string;
  message: string;
  icon?: string;
  chip_type: ChipType;
}

export interface ChatResponse {
  message_id: string;
  session_id: string;
  answer: string;
  answer_html: string;
  cited_products: ProductCardDTO[];
  suggestions: SuggestionChip[];
  intent: string;
  guardrail_status: GuardrailStatus;
  blocked: boolean;
  latency_ms: number;
  tokens_used: number;
  continue_url?: string;
}

export interface CustomerResponse {
  customer_id: string;
  external_id: string | null;
  email: string | null;
  name: string | null;
  status: string;
  profile: Record<string, unknown>;
  created_at: string;
}

export interface SessionResponse {
  session_id: string;
  customer_id: string | null;
  channel: string;
  status: "active" | "ended";
  message_count: number;
  total_tokens: number;
  started_at: string;
  ended_at: string | null;
}

export interface MessageResponse {
  message_id: string;
  role: string;
  content: string;
  cited_products: Record<string, unknown>[];
  intent: string | null;
  created_at: string;
}

export interface MessageHistoryResponse {
  messages: MessageResponse[];
  next_cursor: string | null;
  has_more: boolean;
}

// ── UI-only types ─────────────────────────────────────────────────────────

export interface CheckoutLineItem {
  item: { id: string; title: string; price: number };
  quantity: number;
}

export interface CheckoutData {
  line_items: CheckoutLineItem[];
  totals: { subtotal_cents: number; tax_cents: number; grand_total_cents: number };
  checkout_session_id: string;
}

export interface ChatMessageUI {
  id: string;
  role: MessageRole;
  content: string;
  answerHtml?: string;
  timestamp: Date;
  citedProducts?: ProductCardDTO[];
  suggestions?: SuggestionChip[];
  streamDone?: boolean;
  continueUrl?: string;
  checkoutData?: CheckoutData;
}
