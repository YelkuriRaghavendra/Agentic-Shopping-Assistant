"use client";

import { useState, useCallback, useRef, useEffect } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { httpClient } from "@/services/httpClient";
import { endpoints } from "@/config/config";
import type {
  ChatMessageUI,
  ChatRequest,
  ChatResponse,
  MessageHistoryResponse,
  ProductCardDTO,
  SessionResponse,
  OrderConfirmation,
  CartData,
  OrderHistoryData,
} from "@/types/chat.types";

/** Strip [P1], [P2] etc. citation markers from LLM text */
function stripCitations(text: string): string {
  return text.replace(/\[P\d+\]/g, "").replace(/ {2,}/g, " ").trim();
}

/** Filter out products with missing image or product ID */
function filterValidProducts(products?: ProductCardDTO[]): ProductCardDTO[] | undefined {
  if (!products || products.length === 0) return products;
  const filtered = products.filter((p) => p.productId != null && p.productId !== "");
  return filtered.length > 0 ? filtered : undefined;
}

interface UseChatReturn {
  messages: ChatMessageUI[];
  sendMessage: (text: string, imageBase64?: string) => void;
  sendProductMessage: (productId: string, productName: string) => void;
  sendCompareMessage: (products: ProductCardDTO[]) => void;
  addOrderConfirmation: (order: OrderConfirmation) => void;
  sendCheckoutAction: (action: string, payload: Record<string, unknown>) => void;
  isLoading: boolean;
  isTyping: boolean;
  isHistoryLoading: boolean;
  sessionEnded: boolean;
  activeSessionId: string | null;
  error: string | null;
  bottomRef: React.RefObject<HTMLDivElement>;
}

function generateId(): string {
  return crypto.randomUUID();
}

export function useChat(
  customerId: string | null,
  sessionId: string | null
): UseChatReturn {
  const [messages, setMessages] = useState<ChatMessageUI[]>([]);
  const queryClient = useQueryClient();
  const [isTyping, setIsTyping] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [activeSessionId, setActiveSessionId] = useState<string | null>(sessionId);
  const [sessionEnded, setSessionEnded] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const bottomRef = useRef<HTMLDivElement | null>(null);
  const loadingRef = useRef(false);
  const loadingStartRef = useRef<number | null>(null);

  /** Update active session and refresh sidebar when a new session is created */
  const syncSession = useCallback((newSessionId: string) => {
    setActiveSessionId((prev) => {
      if (prev !== newSessionId) {
        // Refresh sidebar session list
        queryClient.invalidateQueries({ queryKey: ["sessions", customerId] });
        // Sync URL for deep linking
        const url = new URL(window.location.href);
        url.searchParams.set("session", newSessionId);
        window.history.replaceState({}, "", url.toString());
        // Notify useSessions via custom event (no polling needed)
        window.dispatchEvent(new Event("session-updated"));
      }
      return newSessionId;
    });
  }, [customerId, queryClient]);

  const setLoading = useCallback((val: boolean) => {
    loadingRef.current = val;
    loadingStartRef.current = val ? Date.now() : null;
    setIsLoading(val);
  }, []);

  const scrollToBottom = useCallback(() => {
    setTimeout(() => {
      bottomRef.current?.scrollIntoView({ behavior: "smooth" });
    }, 50);
  }, []);

  // Load message history when sessionId prop changes
  const { data: historyData, isLoading: isHistoryLoading } = useQuery<MessageHistoryResponse>({
    queryKey: ["messages", sessionId],
    queryFn: () =>
      httpClient.get<MessageHistoryResponse>(
        endpoints.sessionMessages(sessionId!)
      ),
    enabled: !!sessionId,
  });

  useEffect(() => {
    if (!historyData) return;

    const loaded: ChatMessageUI[] = historyData.messages
      .slice()
      .sort((a, b) => {
        const timeDiff = new Date(a.created_at).getTime() - new Date(b.created_at).getTime();
        if (timeDiff !== 0) return timeDiff;
        // When timestamps are equal (same DB transaction), user messages come before bot
        const roleOrder = (r: string) => (r.toLowerCase() === "user" ? 0 : 1);
        return roleOrder(a.role) - roleOrder(b.role);
      })
      .map((msg) => {
        // Extract answer_html and product cards from cited_products metadata
        const citedRaw = msg.cited_products ?? [];
        let answerHtml: string | undefined;
        const productCards: ProductCardDTO[] = [];

        for (const item of citedRaw) {
          if (typeof item.answer_html === "string" && item.answer_html) {
            answerHtml = item.answer_html;
          }
          // If the item has product fields, treat it as a product card
          if (item.productId && item.productName) {
            productCards.push({
              productId: item.productId as string,
              productName: item.productName as string,
              price: (item.price as number) ?? null,
              rating: (item.rating as number) ?? null,
              productImageUrl: (item.productImageUrl as string) ?? null,
            });
          }
        }

        const validProducts = filterValidProducts(productCards);

        return {
          id: msg.message_id,
          role: (msg.role.toLowerCase() === "user" ? "user" : "bot") as "user" | "bot",
          content: msg.content,
          ...(answerHtml ? { answerHtml } : {}),
          ...(validProducts && validProducts.length > 0 ? { citedProducts: validProducts } : {}),
          timestamp: new Date(msg.created_at),
          streamDone: true,
        };
      });
    // Hydrate order confirmation cards — fetch order details for messages with order IDs
    const orderPattern = /order #?([\w-]+)/i;
    const hydrateOrders = async () => {
      if (!customerId) return;

      // Fetch all orders for this customer in one call
      let allOrders: any[] = [];
      try {
        const res = await fetch(endpoints.orderHistory(customerId));
        if (res.ok) {
          const body = await res.json();
          allOrders = body.data ?? body.orders ?? body ?? [];
        }
      } catch { /* ignore */ }

      if (allOrders.length === 0) return;

      // Build a map of orderId → order data
      const orderMap = new Map<string, any>();
      for (const o of allOrders) {
        const id = (o.orderId ?? o.order_id ?? "").toLowerCase();
        if (id) orderMap.set(id, o);
      }

      const updated = loaded.map((msg) => {
        if (msg.role !== "bot") return msg;
        const match = msg.content.match(orderPattern);
        if (!match) return msg;
        const orderId = match[1];
        const db = orderMap.get(orderId.toLowerCase());
        if (!db) return msg;

        const orderConfirmation: OrderConfirmation = {
          order_id: db.orderId ?? db.order_id ?? orderId,
          line_items: (db.lineItems ?? db.line_items ?? []).map((li: any) => ({
            item: { id: li.item?.id ?? "", title: li.item?.title ?? "", price: li.item?.price ?? 0 },
            quantity: li.quantity ?? 1,
          })),
          totals: {
            subtotal_cents: db.totals?.subtotalCents ?? db.totals?.subtotal_cents ?? 0,
            tax_cents: db.totals?.taxCents ?? db.totals?.tax_cents ?? 0,
            grand_total_cents: db.totals?.grandTotalCents ?? db.totals?.grand_total_cents ?? 0,
          },
          status: db.status ?? "processing",
        };
        return { ...msg, orderConfirmation };
      });
      setMessages(updated);
    };

    setMessages(loaded);
    setActiveSessionId(sessionId);
    setSessionEnded(false);
    scrollToBottom();

    // Hydrate order cards in background (non-blocking)
    hydrateOrders();
  }, [historyData, sessionId, scrollToBottom]);

  // Check session status from cached sessions data to persist ended state across refreshes
  useEffect(() => {
    if (!sessionId) return;
    const sessionsData = queryClient.getQueryData<SessionResponse[]>(["sessions", customerId]);
    if (sessionsData) {
      const current = sessionsData.find((s) => s.session_id === sessionId);
      if (current && current.status === "ended") {
        setSessionEnded(true);
      }
    }
  }, [sessionId, customerId, queryClient]);

  const sendMessage = useCallback(
    async (text: string, imageBase64?: string) => {
      const trimmed = text.trim();
      if (!trimmed && !imageBase64) return;
      // If a previous request is stuck loading for >30s, force-reset
      if (loadingRef.current) {
        if (loadingStartRef.current && Date.now() - loadingStartRef.current > 30000) {
          setLoading(false);
        } else {
          return;
        }
      }

      // Slash command: /start — allowed even when session is ended
      if (trimmed.toLowerCase() === "/start") {
        setLoading(true);
        setError(null);
        try {
          const newSession = await httpClient.post<{ session_id: string }>(
            endpoints.createSession,
            { customer_id: customerId, channel: "web" }
          );
          syncSession(newSession.session_id);
          setMessages([]);
          setSessionEnded(false);
          const infoMsg: ChatMessageUI = {
            id: generateId(),
            role: "bot",
            content: "New session started.",
            timestamp: new Date(),
          };
          setMessages([infoMsg]);
          scrollToBottom();
        } catch (err) {
          const errMsg: ChatMessageUI = {
            id: generateId(),
            role: "bot",
            content: `Failed to start session: ${err instanceof Error ? err.message : "Unknown error"}`,
            timestamp: new Date(),
          };
          setMessages((prev) => [...prev, errMsg]);
        } finally {
          setLoading(false);
        }
        return;
      }

      // Slash command: /end (requires confirmation)
      if (trimmed.toLowerCase() === "/end") {
        if (!activeSessionId || sessionEnded || loadingRef.current) return;

        // Check if last message was the confirmation prompt
        const lastMsg = messages[messages.length - 1];
        const isConfirmed = lastMsg?.content === "/end" && lastMsg?.role === "user";

        if (!isConfirmed) {
          // Show confirmation prompt
          const userMsg: ChatMessageUI = {
            id: generateId(), role: "user", content: "/end", timestamp: new Date(), streamDone: true,
          };
          const confirmMsg: ChatMessageUI = {
            id: generateId(), role: "bot", timestamp: new Date(), streamDone: true,
            content: "Are you sure you want to end this session? Type /end again to confirm.",
          };
          setMessages((prev) => [...prev, userMsg, confirmMsg]);
          scrollToBottom();
          return;
        }

        setLoading(true);
        setError(null);
        try {
          await httpClient.post(endpoints.endSession(activeSessionId), {});
          setSessionEnded(true);
          queryClient.invalidateQueries({ queryKey: ["sessions"] });
          // localStorage.setItem("session_updated", Date.now().toString());
          const infoMsg: ChatMessageUI = {
            id: generateId(),
            role: "bot",
            content: "Session ended.",
            timestamp: new Date(),
            streamDone: true,
          };
          setMessages((prev) => [...prev, infoMsg]);
          scrollToBottom();
        } catch (err) {
          const errMsg: ChatMessageUI = {
            id: generateId(),
            role: "bot",
            content: `Failed to end session: ${err instanceof Error ? err.message : "Unknown error"}`,
            timestamp: new Date(),
          };
          setMessages((prev) => [...prev, errMsg]);
        } finally {
          setLoading(false);
        }
        return;
      }

      if (sessionEnded) return;

      // __checkout: prefixed messages are system actions from card components
      // Don't show them as user messages in the chat
      const isCheckoutAction = trimmed.startsWith("__checkout:");

      const botId = generateId();
      const botMessage: ChatMessageUI = {
        id: botId,
        role: "bot",
        content: "",
        timestamp: new Date(),
      };

      if (isCheckoutAction) {
        // Only add bot placeholder (no user bubble)
        setMessages((prev) => [...prev, botMessage]);
      } else {
        const userMessage: ChatMessageUI = {
          id: generateId(),
          role: "user",
          content: trimmed || "Here's my outfit, help me find matching shoes",
          imageBase64: imageBase64,
          timestamp: new Date(),
        };
        setMessages((prev) => [...prev, userMessage, botMessage]);
      }
      setLoading(true);
      setError(null);
      scrollToBottom();

      const body: ChatRequest = {
        message: trimmed || "Here's my outfit, help me find matching shoes",
        ...(customerId ? { customer_id: customerId } : {}),
        ...(activeSessionId ? { session_id: activeSessionId } : {}),
        ...(imageBase64 ? { image_base64: imageBase64 } : {}),
      };

      setIsTyping(true);
      try {
        const res = await fetch(endpoints.chatStream, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
        });

        if (!res.ok || !res.body) {
          if (res.status === 429) {
            throw new Error("Too many requests. Please wait a moment and try again.");
          }
          throw new Error(`HTTP ${res.status}`);
        }

        const reader = res.body.getReader();
        const decoder = new TextDecoder();
        let buffer = "";
        let streamedContent = "";

        while (true) {
          const { done, value } = await reader.read();

          if (done) {
            // Process any remaining data in the buffer after stream ends
            if (buffer.trim()) {
              const remainingLines = buffer.split("\n");
              for (const line of remainingLines) {
                if (!line.startsWith("data: ")) continue;
                const jsonStr = line.slice(6).trim();
                if (!jsonStr) continue;
                try {
                  const event = JSON.parse(jsonStr);
                  if (event.type === "done") {
                        if (event.session_id) syncSession(event.session_id);
                    setMessages((prev) =>
                      prev.map((m) =>
                        m.id === botId
                          ? {
                              ...m,
                              id: event.message_id || botId,
                              content: streamedContent,
                              answerHtml: event.answer_html || undefined,
                              citedProducts: filterValidProducts(event.cited_products),
                              suggestions: event.suggestions,
                              continueUrl: event.continue_url || undefined,
                              checkoutData: event.checkout_data || undefined,
                              cartData: (event.cart_data as CartData) || undefined,
                              orderHistoryData: (event.order_history_data as OrderHistoryData) || undefined,
                              setupIntentSecret: event.checkout_action?.action === "payment_setup"
                                ? (event.checkout_action.setup_intent_secret as string)
                                : undefined,
                              paymentIntentSecret: event.checkout_action?.action === "confirm_payment"
                                ? (event.checkout_action.payment_intent_secret as string)
                                : undefined,
                              addressFormData: event.checkout_action?.action === "address_form"
                                ? (event.checkout_action.prefilled as ChatMessageUI["addressFormData"])
                                : undefined,
                              checkoutAction: event.checkout_action || undefined,
                              streamDone: true,
                            }
                          : m
                      )
                    );
                  }
                } catch { /* ignore parse errors in trailing buffer */ }
              }
            }
            break;
          }

          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split("\n");
          buffer = lines.pop() ?? "";

          for (const line of lines) {
            if (!line.startsWith("data: ")) continue;
            const jsonStr = line.slice(6).trim();
            if (!jsonStr) continue;

            try {
              const event = JSON.parse(jsonStr);

              if (event.type === "token") {
                streamedContent += event.content;
                setMessages((prev) =>
                  prev.map((m) =>
                    m.id === botId ? { ...m, content: streamedContent } : m
                  )
                );
                scrollToBottom();
              } else if (event.type === "done") {
                // Final event — add products/suggestions
                // Use answer_html if content has HTML tags (e.g. tables from comparisons)
                if (event.session_id) {
                  syncSession(event.session_id);
                }
                setMessages((prev) =>
                  prev.map((m) =>
                    m.id === botId
                      ? {
                          ...m,
                          id: event.message_id || botId,
                          content: stripCitations(streamedContent),
                          answerHtml: event.answer_html || undefined,
                          citedProducts: filterValidProducts(event.cited_products),
                          suggestions: event.suggestions,
                          continueUrl: event.continue_url || undefined,
                          checkoutData: event.checkout_data || undefined,
                          cartData: (event.cart_data as CartData) || undefined,
                          orderHistoryData: (event.order_history_data as OrderHistoryData) || undefined,
                          setupIntentSecret: event.checkout_action?.action === "payment_setup"
                            ? (event.checkout_action.setup_intent_secret as string)
                            : undefined,
                          paymentIntentSecret: event.checkout_action?.action === "confirm_payment"
                            ? (event.checkout_action.payment_intent_secret as string)
                            : undefined,
                          addressFormData: event.checkout_action?.action === "address_form"
                            ? (event.checkout_action.prefilled as ChatMessageUI["addressFormData"])
                            : undefined,
                          checkoutAction: event.checkout_action || undefined,
                          streamDone: true,
                        }
                      : m
                  )
                );
                scrollToBottom();
              } else if (event.type === "error") {
                setMessages((prev) =>
                  prev.map((m) =>
                    m.id === botId ? { ...m, content: event.content, streamDone: true } : m
                  )
                );
              }
            } catch {
              // skip malformed JSON lines
            }
          }
        }
      } catch (err) {
        const errorText = err instanceof Error ? err.message : "Unknown error";
        // Fallback: if streaming fails, preserve partial content
        setMessages((prev) =>
          prev.map((m) =>
            m.id === botId
              ? {
                  ...m,
                  content: m.content
                    ? m.content + "\n\n[Connection lost. Please try again.]"
                    : "Oops, something went wrong. Please try again.",
                  streamDone: true,
                }
              : m
          )
        );
        setError(errorText);
        scrollToBottom();
      } finally {
        setIsTyping(false);
        setLoading(false);
      }
    },
    [sessionEnded, customerId, activeSessionId, scrollToBottom, setLoading, syncSession]
  );

  // Shared streaming helper for product/compare messages
  const streamRequest = useCallback(
    async (displayText: string, apiMessage: string) => {
      if (sessionEnded) return;
      // If a previous request is stuck loading for >30s, force-reset
      if (loadingRef.current) {
        if (loadingStartRef.current && Date.now() - loadingStartRef.current > 30000) {
          setLoading(false);
        } else {
          return;
        }
      }

      const userMessage: ChatMessageUI = {
        id: generateId(),
        role: "user",
        content: displayText,
        timestamp: new Date(),
      };

      const botId = generateId();
      const botPlaceholder: ChatMessageUI = {
        id: botId,
        role: "bot",
        content: "",
        timestamp: new Date(),
      };

      // Add both user message and bot placeholder in a single state update
      // to guarantee user message always appears above bot response
      setMessages((prev) => [...prev, userMessage, botPlaceholder]);
      setLoading(true);
      setError(null);
      scrollToBottom();

      const body: ChatRequest = {
        message: apiMessage,
        ...(customerId ? { customer_id: customerId } : {}),
        ...(activeSessionId ? { session_id: activeSessionId } : {}),
      };

      setIsTyping(true);
      try {
        const res = await fetch(endpoints.chatStream, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
        });
        if (!res.ok || !res.body) {
          if (res.status === 429) {
            throw new Error("Too many requests. Please wait a moment and try again.");
          }
          throw new Error(`HTTP ${res.status}`);
        }

        const reader = res.body.getReader();
        const decoder = new TextDecoder();
        let buffer = "";
        let streamedContent = "";

        while (true) {
          const { done, value } = await reader.read();
          if (done) {
            // Process remaining buffer after stream ends
            if (buffer.trim()) {
              for (const line of buffer.split("\n")) {
                if (!line.startsWith("data: ")) continue;
                try {
                  const event = JSON.parse(line.slice(6).trim());
                  if (event.type === "done") {
                        if (event.session_id) syncSession(event.session_id);
                    setMessages((prev) =>
                      prev.map((m) =>
                        m.id === botId
                          ? {
                              ...m, id: event.message_id || botId, content: streamedContent,
                              answerHtml: event.answer_html || undefined,
                              citedProducts: filterValidProducts(event.cited_products), suggestions: event.suggestions,
                              continueUrl: event.continue_url || undefined,
                              checkoutData: event.checkout_data || undefined,
                              cartData: (event.cart_data as CartData) || undefined,
                              orderHistoryData: (event.order_history_data as OrderHistoryData) || undefined,
                              setupIntentSecret: event.checkout_action?.action === "payment_setup"
                                ? (event.checkout_action.setup_intent_secret as string)
                                : undefined,
                              paymentIntentSecret: event.checkout_action?.action === "confirm_payment"
                                ? (event.checkout_action.payment_intent_secret as string)
                                : undefined,
                              addressFormData: event.checkout_action?.action === "address_form"
                                ? (event.checkout_action.prefilled as ChatMessageUI["addressFormData"])
                                : undefined,
                              checkoutAction: event.checkout_action || undefined,
                              streamDone: true,
                            }
                          : m
                      )
                    );
                  }
                } catch { /* ignore */ }
              }
            }
            break;
          }
          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split("\n");
          buffer = lines.pop() ?? "";

          for (const line of lines) {
            if (!line.startsWith("data: ")) continue;
            try {
              const event = JSON.parse(line.slice(6).trim());
              if (event.type === "token") {
                streamedContent += event.content;
                setMessages((prev) =>
                  prev.map((m) => (m.id === botId ? { ...m, content: streamedContent } : m))
                );
                scrollToBottom();
              } else if (event.type === "done") {
                if (event.session_id) syncSession(event.session_id);
                setMessages((prev) =>
                  prev.map((m) =>
                    m.id === botId
                      ? {
                          ...m,
                          id: event.message_id || botId,
                          content: stripCitations(streamedContent),
                          answerHtml: event.answer_html || undefined,
                          citedProducts: filterValidProducts(event.cited_products),
                          suggestions: event.suggestions,
                          continueUrl: event.continue_url || undefined,
                          checkoutData: event.checkout_data || undefined,
                          cartData: (event.cart_data as CartData) || undefined,
                          orderHistoryData: (event.order_history_data as OrderHistoryData) || undefined,
                          setupIntentSecret: event.checkout_action?.action === "payment_setup"
                            ? (event.checkout_action.setup_intent_secret as string)
                            : undefined,
                          paymentIntentSecret: event.checkout_action?.action === "confirm_payment"
                            ? (event.checkout_action.payment_intent_secret as string)
                            : undefined,
                          addressFormData: event.checkout_action?.action === "address_form"
                            ? (event.checkout_action.prefilled as ChatMessageUI["addressFormData"])
                            : undefined,
                          checkoutAction: event.checkout_action || undefined,
                          streamDone: true,
                        }
                      : m
                  )
                );
                scrollToBottom();
              } else if (event.type === "error") {
                setMessages((prev) =>
                  prev.map((m) => (m.id === botId ? { ...m, content: event.content, streamDone: true } : m))
                );
              }
            } catch {
              // skip malformed lines
            }
          }
        }
      } catch (err) {
        const errorText = err instanceof Error ? err.message : "Unknown error";
        setMessages((prev) =>
          prev.map((m) =>
            m.id === botId
              ? {
                  ...m,
                  content: m.content
                    ? m.content + "\n\n[Connection lost. Please try again.]"
                    : "Oops, something went wrong. Please try again.",
                  streamDone: true,
                }
              : m
          )
        );
        setError(errorText);
        scrollToBottom();
      } finally {
        setIsTyping(false);
        setLoading(false);
      }
    },
    [sessionEnded, customerId, activeSessionId, scrollToBottom, setLoading, syncSession]
  );

  const sendProductMessage = useCallback(
    (productId: string, productName: string) => {
      streamRequest(productName, `Tell me more about ${productName}`);
    },
    [streamRequest]
  );

  const sendCompareMessage = useCallback(
    (products: ProductCardDTO[]) => {
      if (products.length < 2) return;
      const names = products.map((p) => p.productName);
      const compareText = `Compare ${names.join(" and ")}`;
      streamRequest(compareText, compareText);
    },
    [streamRequest]
  );

  const addOrderConfirmation = useCallback(
    async (order: OrderConfirmation) => {
      let finalOrder = order;
      try {
        const res = await fetch(endpoints.orderDetail(order.order_id));
        if (res.ok) {
          const db = await res.json();
          finalOrder = {
            order_id: db.orderId ?? db.order_id ?? order.order_id,
            line_items: db.lineItems ?? db.line_items ?? order.line_items,
            totals: {
              subtotal_cents: db.totals?.subtotalCents ?? db.totals?.subtotal_cents ?? order.totals.subtotal_cents,
              tax_cents: db.totals?.taxCents ?? db.totals?.tax_cents ?? order.totals.tax_cents,
              grand_total_cents: db.totals?.grandTotalCents ?? db.totals?.grand_total_cents ?? order.totals.grand_total_cents,
            },
            status: db.status ?? order.status,
          };
        }
      } catch {
        // DB not ready yet — use checkout data
      }

      const orderContent = `Your order #${finalOrder.order_id} has been placed successfully! 🎉`;
      const confirmMsg: ChatMessageUI = {
        id: finalOrder.order_id,
        role: "bot",
        content: orderContent,
        timestamp: new Date(),
        orderConfirmation: finalOrder,
        streamDone: true,
      };
      setMessages((prev) => {
        // Avoid duplicate
        if (prev.some((m) => m.id === finalOrder.order_id)) return prev;
        return [...prev, confirmMsg];
      });
      setTimeout(() => bottomRef.current?.scrollIntoView({ behavior: "smooth" }), 100);

      // Persist to backend DB so it shows on reload
      if (activeSessionId) {
        try {
          await fetch(endpoints.createMessage, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              session_id: activeSessionId,
              content: orderContent,
              role: "assistant",
              intent: "order_confirmation",
              cited_products: [finalOrder],
            }),
          });
        } catch {
          // Non-critical — local message already shown
        }
      }
    },
    [activeSessionId]
  );

  const sendCheckoutAction = useCallback(
    (action: string, payload: Record<string, unknown>) => {
      // Encode the payload as JSON in the message so the backend can parse it
      const msg = `__checkout:${action}:${JSON.stringify(payload)}`;
      sendMessage(msg);
    },
    [sendMessage]
  );

  return {
    messages,
    sendMessage,
    sendProductMessage,
    sendCompareMessage,
    addOrderConfirmation,
    sendCheckoutAction,
    isLoading,
    isTyping,
    isHistoryLoading,
    sessionEnded,
    activeSessionId,
    error,
    bottomRef,
  };
}
