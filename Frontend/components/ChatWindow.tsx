"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import { AnimatePresence } from "framer-motion";
import { MessageBubble } from "./MessageBubble";
import { ChatInput } from "./ChatInput";
import { TypingIndicator } from "./TypingIndicator";
// CheckoutModal removed — checkout is now conversational
import { CartPanel } from "./CartPanel";
import { OrderHistoryPanel } from "./OrderHistoryPanel";
import { endpoints } from "@/config/config";
import type {
  ChatMessageUI,
  ProductCardDTO,
  CartData,
  OrderHistoryData,
  OrderConfirmation,
  CheckoutLineItem,
} from "@/types/chat.types";

import type React from "react";

export interface ChatWindowProps {
  messages: ChatMessageUI[];
  sendMessage: (text: string, imageBase64?: string) => void;
  sendProductMessage: (productId: string, productName: string) => void;
  sendCompareMessage: (products: ProductCardDTO[]) => void;
  isLoading: boolean;
  isTyping: boolean;
  inputDisabled: boolean;
  sessionEnded: boolean;
  bottomRef: React.RefObject<HTMLDivElement>;
  isHistoryLoading?: boolean;
  customerId?: string | null;
  updateProfile?: (profile: Record<string, unknown>) => Promise<void>;
  addOrderConfirmation?: (order: OrderConfirmation) => void;
  sendCheckoutAction?: (action: string, payload: Record<string, unknown>) => void;
  agentStatus?: string | null;
}

function HistorySkeleton() {
  return (
    <div className="flex flex-col gap-4 px-6 py-6">
      <div className="animate-pulse rounded-2xl h-10 w-3/4 self-end" style={{ background: "#141418" }} />
      <div className="animate-pulse rounded-2xl h-14 w-1/2 self-start" style={{ background: "#141418" }} />
      <div className="animate-pulse rounded-2xl h-10 w-2/3 self-end" style={{ background: "#141418" }} />
    </div>
  );
}

// ── Inline SVG icons ──────────────────────────────────────────────────────

function CartIcon({ color }: { color: string }) {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="9" cy="21" r="1" />
      <circle cx="20" cy="21" r="1" />
      <path d="M1 1h4l2.68 13.39a2 2 0 0 0 2 1.61h9.72a2 2 0 0 0 2-1.61L23 6H6" />
    </svg>
  );
}

function OrdersIcon({ color }: { color: string }) {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <rect x="8" y="2" width="8" height="4" rx="1" ry="1" />
      <path d="M16 4h2a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h2" />
      <line x1="9" y1="12" x2="15" y2="12" />
      <line x1="9" y1="16" x2="13" y2="16" />
    </svg>
  );
}

export function ChatWindow({
  messages,
  sendMessage,
  sendProductMessage,
  sendCompareMessage,
  isLoading,
  isTyping,
  inputDisabled,
  sessionEnded,
  bottomRef,
  isHistoryLoading = false,
  customerId,
  updateProfile,
  addOrderConfirmation,
  sendCheckoutAction,
  agentStatus,
}: ChatWindowProps) {
  // Task 8.1: cart/orders drawer state
  const [cartData, setCartData] = useState<CartData | null>(null);
  const [orderHistoryData, setOrderHistoryData] = useState<OrderHistoryData | null>(null);
  const [cartOpen, setCartOpen] = useState(false);
  const [ordersOpen, setOrdersOpen] = useState(false);

  // Track last processed message index to avoid re-processing on re-renders
  const lastProcessedRef = useRef<string | null>(null);

  // Fetch active cart for this customer from checkout-order-service
  const fetchCart = useCallback(async () => {
    if (!customerId) return;
    try {
      const res = await fetch(endpoints.activeCart(customerId));
      if (!res.ok) return;
      const session = await res.json();
      if (!session) return;
      const lineItems: CheckoutLineItem[] = (session.lineItemsSnapshot ?? []).map((li: any) => ({
        item: { id: li.item?.id ?? "", title: li.item?.title ?? "", price: li.item?.price ?? 0 },
        quantity: li.quantity ?? 1,
      }));
      const totals = session.totalsSnapshot ?? { subtotal_cents: 0, tax_cents: 0, grand_total_cents: 0 };
      if (lineItems.length > 0) {
        setCartData({
          line_items: lineItems,
          totals: {
            subtotal_cents: totals.subtotal_cents ?? totals.subtotalCents ?? 0,
            tax_cents: totals.tax_cents ?? totals.taxCents ?? 0,
            grand_total_cents: totals.grand_total_cents ?? totals.grandTotalCents ?? 0,
          },
          checkout_session_id: session.sessionId,
        });
      }
    } catch { /* silently ignore */ }
  }, [customerId]);

  // Fetch order history for this customer from checkout-order-service
  const fetchOrders = useCallback(async () => {
    if (!customerId) return;
    try {
      const res = await fetch(endpoints.orderHistory(customerId));
      if (!res.ok) return;
      const body = await res.json();
      const orders = (body.data ?? body.orders ?? body ?? []).map((o: any) => ({
        order_id: o.orderId ?? o.order_id ?? "",
        ucp_order_id: o.ucpOrderId ?? o.ucp_order_id,
        status: o.status ?? "processing",
        totals: {
          grand_total_cents: o.totals?.grandTotalCents ?? o.totals?.grand_total_cents ?? 0,
        },
        created_at: o.createdAt ?? o.created_at ?? new Date().toISOString(),
      }));
      setOrderHistoryData({ orders, next_cursor: body.nextCursor ?? null });
    } catch { /* silently ignore */ }
  }, [customerId]);

  // Task 8.4: auto-open drawers when SSE data arrives
  useEffect(() => {
    if (messages.length === 0) return;
    const lastMsg = messages[messages.length - 1];
    if (!lastMsg.streamDone) return;
    if (lastMsg.id === lastProcessedRef.current) return;
    lastProcessedRef.current = lastMsg.id;

    if (lastMsg.cartData) {
      setCartData(lastMsg.cartData);
      setCartOpen(true);
    }
    if (lastMsg.orderHistoryData) {
      setOrderHistoryData(lastMsg.orderHistoryData);
      // Only auto-open when there are orders (Requirement 5.6)
      if (lastMsg.orderHistoryData.orders.length > 0) {
        setOrdersOpen(true);
      }
    }
  }, [messages]);

  const cartItemCount = cartData?.line_items.length ?? 0;
  const orderCount = orderHistoryData?.orders.length ?? 0;

  const iconColor = (count: number) =>
    count > 0 ? "#1D9E75" : "rgba(255,255,255,0.5)";

  return (
    <div className="flex h-full w-full flex-col" style={{ background: "#080809", position: "relative" }}>
      {/* Header */}
      <div
        className="flex items-center gap-3 px-6 py-4 shrink-0"
        style={{ borderBottom: "0.5px solid rgba(255,255,255,0.06)", background: "#0C0C0F" }}
      >
        {/* Avatar */}
        <div
          className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full"
          style={{
            background: "#111116",
            border: "1px solid rgba(29,158,117,0.3)",
          }}
        >
          <span className="font-mono text-[9px] uppercase tracking-wider" style={{ color: "#1D9E75" }}>
            Vy
          </span>
        </div>

        <div>
          <div className="flex items-center justify-between gap-2">
            <h1
              className="font-josefin font-bold uppercase tracking-widest text-sm"
              style={{ color: "#fff", letterSpacing: "2px" }}
            >
              Vik <span style={{color: "#1D9E75"}}>rai</span>
            </h1>
            <span
              className="font-mono text-[9px] uppercase tracking-widest px-2 py-0.5"
              style={{
                color: "rgba(29,158,117,0.8)",
                border: "1px solid rgba(29,158,117,0.18)",
                letterSpacing: "1.5px",
              }}
            >
              LIVE
            </span>
          </div>
          <p
            className="font-mono text-[9px] uppercase tracking-widest mt-0.5"
            style={{ color: "rgba(255,255,255,0.3)", letterSpacing: "2px" }}
          >
            your commerce companion
          </p>
        </div>

        {/* Task 8.1: Cart + Orders icon buttons (top-right) */}
        <div className="flex items-center gap-2 ml-auto">
          {/* Cart icon */}
          <button
            onClick={() => {
              if (!cartData) fetchCart();
              setCartOpen((o) => !o);
            }}
            aria-label="Toggle cart"
            style={{
              position: "relative",
              background: "transparent",
              border: "none",
              cursor: "pointer",
              padding: "4px",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
            }}
          >
            <CartIcon color={iconColor(cartItemCount)} />
            {cartItemCount > 0 && (
              <span
                style={{
                  position: "absolute",
                  top: 0,
                  right: 0,
                  background: "#1D9E75",
                  color: "#000",
                  fontSize: "8px",
                  fontWeight: 700,
                  fontFamily: "var(--font-mono, monospace)",
                  borderRadius: "100px",
                  minWidth: "14px",
                  height: "14px",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  padding: "0 3px",
                  lineHeight: 1,
                }}
              >
                {cartItemCount}
              </span>
            )}
          </button>

          {/* Orders icon */}
          <button
            onClick={() => {
              if (!orderHistoryData) fetchOrders();
              setOrdersOpen((o) => !o);
            }}
            aria-label="Toggle order history"
            style={{
              position: "relative",
              background: "transparent",
              border: "none",
              cursor: "pointer",
              padding: "4px",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
            }}
          >
            <OrdersIcon color={iconColor(orderCount)} />
            {orderCount > 0 && (
              <span
                style={{
                  position: "absolute",
                  top: 0,
                  right: 0,
                  background: "#1D9E75",
                  color: "#000",
                  fontSize: "8px",
                  fontWeight: 700,
                  fontFamily: "var(--font-mono, monospace)",
                  borderRadius: "100px",
                  minWidth: "14px",
                  height: "14px",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  padding: "0 3px",
                  lineHeight: 1,
                }}
              >
                {orderCount}
              </span>
            )}
          </button>
        </div>
      </div>

      {/* Chat body */}
      <div className="flex-1 flex flex-col overflow-hidden">
        {/* Messages area */}
        <div className="flex-1 overflow-y-auto py-4" suppressHydrationWarning>
          {isHistoryLoading ? (
            <HistorySkeleton />
          ) : (
            <AnimatePresence initial={false}>
              {/* Welcome message when no messages yet */}
              {messages.length === 0 && !isTyping && (
                <div className="flex flex-col items-center justify-center h-full gap-4 px-6 py-16">
                  <div
                    className="flex h-14 w-14 items-center justify-center rounded-full"
                    style={{ background: "#111116", border: "1px solid rgba(29,158,117,0.3)" }}
                  >
                    <span className="font-mono text-sm uppercase tracking-wider" style={{ color: "#1D9E75" }}>Vy</span>
                  </div>
                  <h2
                    className="font-josefin font-bold uppercase tracking-widest text-lg text-center"
                    style={{ color: "#fff", letterSpacing: "3px" }}
                  >
                    Welcome to Vik<span style={{ color: "#1D9E75" }}>rai</span>
                  </h2>
                  <p
                    className="text-[13px] text-center max-w-md leading-relaxed"
                    style={{ color: "rgba(255,255,255,0.45)", fontWeight: 300 }}
                  >
                    I can help you find the perfect shoes. Tell me what you&apos;re looking for, or upload a photo of your outfit and I&apos;ll suggest matching shoes.
                  </p>
                  <div className="flex gap-2 mt-2 flex-wrap justify-center">
                    {[
                      { label: "Casual sneakers", msg: "I'm looking for casual sneakers" },
                      { label: "Running shoes", msg: "Show me running shoes" },
                      { label: "Formal shoes", msg: "I need formal shoes" },
                    ].map((item) => (
                      <button
                        key={item.label}
                        onClick={() => sendMessage(item.msg)}
                        className="px-4 py-2 font-mono text-[9px] uppercase tracking-widest transition-all duration-150"
                        style={{
                          background: "transparent",
                          color: "rgba(29,158,117,0.8)",
                          border: "1px solid rgba(29,158,117,0.25)",
                          borderRadius: "20px",
                          letterSpacing: "1.5px",
                        }}
                        onMouseEnter={(e) => { e.currentTarget.style.background = "rgba(29,158,117,0.1)"; }}
                        onMouseLeave={(e) => { e.currentTarget.style.background = "transparent"; }}
                      >
                        {item.label}
                      </button>
                    ))}
                  </div>
                </div>
              )}
              {messages.map((msg) => (
                <MessageBubble
                  key={msg.id}
                  message={msg}
                  onSelectProduct={sendProductMessage}
                  onSelectSuggestion={sendMessage}
                  onCompareProducts={sendCompareMessage}
                  onCheckoutAction={sendCheckoutAction}
                />
              ))}
              {isTyping && !messages.some((m) => m.role === "bot" && !m.streamDone) && (
                <TypingIndicator key="typing" status={agentStatus} />
              )}
            </AnimatePresence>
          )}
          <div ref={bottomRef} />
        </div>

        {/* Task 8.2: CartDrawer — absolutely positioned overlay */}
        <div
          aria-label="Cart drawer"
          style={{
            position: "absolute",
            top: 0,
            right: 0,
            height: "100%",
            width: "320px",
            background: "#0C0C0F",
            borderLeft: "0.5px solid rgba(255,255,255,0.08)",
            transform: cartOpen ? "translateX(0)" : "translateX(100%)",
            transition: "transform 0.3s ease",
            zIndex: 20,
            display: "flex",
            flexDirection: "column",
          }}
        >
          {/* Close button */}
          <button
            onClick={() => setCartOpen(false)}
            aria-label="Close cart"
            style={{
              position: "absolute",
              top: "12px",
              right: "12px",
              background: "transparent",
              border: "none",
              color: "rgba(255,255,255,0.4)",
              fontSize: "18px",
              cursor: "pointer",
              lineHeight: 1,
              zIndex: 1,
            }}
          >
            &times;
          </button>
          {/* Task 8.5: CartPanel with onCheckout wiring */}
          {cartData && (
            <CartPanel
              cartData={cartData}
              onCheckout={() => {
                setCartOpen(false);
                sendMessage("checkout");
              }}
            />
          )}
        </div>

        {/* Task 8.2: OrdersDrawer — absolutely positioned overlay */}
        <div
          aria-label="Orders drawer"
          style={{
            position: "absolute",
            top: 0,
            right: 0,
            height: "100%",
            width: "320px",
            background: "#0C0C0F",
            borderLeft: "0.5px solid rgba(255,255,255,0.08)",
            transform: ordersOpen ? "translateX(0)" : "translateX(100%)",
            transition: "transform 0.3s ease",
            zIndex: 20,
            display: "flex",
            flexDirection: "column",
          }}
        >
          {/* Close button */}
          <button
            onClick={() => setOrdersOpen(false)}
            aria-label="Close orders"
            style={{
              position: "absolute",
              top: "12px",
              right: "12px",
              background: "transparent",
              border: "none",
              color: "rgba(255,255,255,0.4)",
              fontSize: "18px",
              cursor: "pointer",
              lineHeight: 1,
              zIndex: 1,
            }}
          >
            &times;
          </button>
          {orderHistoryData && (
            <OrderHistoryPanel data={orderHistoryData} />
          )}
        </div>
      </div>

      {/* Input */}
      <ChatInput
        onSend={sendMessage}
        disabled={inputDisabled || sessionEnded}
        sessionEnded={sessionEnded}
      />

      {/* CartDrawer — slides in from right, overlays full chat height */}
      <div
        aria-label="Cart drawer"
        style={{
          position: "absolute",
          top: 0,
          right: 0,
          height: "100%",
          width: "320px",
          background: "#0C0C0F",
          borderLeft: "0.5px solid rgba(255,255,255,0.08)",
          transform: cartOpen ? "translateX(0)" : "translateX(100%)",
          transition: "transform 0.3s ease",
          zIndex: 30,
          display: "flex",
          flexDirection: "column",
        }}
      >
        <button
          onClick={() => setCartOpen(false)}
          aria-label="Close cart"
          style={{
            position: "absolute",
            top: "12px",
            right: "12px",
            background: "transparent",
            border: "none",
            color: "rgba(255,255,255,0.4)",
            fontSize: "18px",
            cursor: "pointer",
            lineHeight: 1,
            zIndex: 1,
          }}
        >
          &times;
        </button>
        {cartData && (
          <CartPanel
            cartData={cartData}
            onCheckout={() => {
              setCartOpen(false);
              sendMessage("checkout");
            }}
          />
        )}
      </div>

      {/* OrdersDrawer — slides in from right, overlays full chat height */}
      <div
        aria-label="Orders drawer"
        style={{
          position: "absolute",
          top: 0,
          right: 0,
          height: "100%",
          width: "320px",
          background: "#0C0C0F",
          borderLeft: "0.5px solid rgba(255,255,255,0.08)",
          transform: ordersOpen ? "translateX(0)" : "translateX(100%)",
          transition: "transform 0.3s ease",
          zIndex: 30,
          display: "flex",
          flexDirection: "column",
        }}
      >
        <button
          onClick={() => setOrdersOpen(false)}
          aria-label="Close orders"
          style={{
            position: "absolute",
            top: "12px",
            right: "12px",
            background: "transparent",
            border: "none",
            color: "rgba(255,255,255,0.4)",
            fontSize: "18px",
            cursor: "pointer",
            lineHeight: 1,
            zIndex: 1,
          }}
        >
          &times;
        </button>
        {orderHistoryData && (
          <OrderHistoryPanel data={orderHistoryData} />
        )}
      </div>
    </div>
  );
}
