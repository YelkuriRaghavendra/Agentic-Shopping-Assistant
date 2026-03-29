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
} from "@/types/chat.types";

interface UseChatReturn {
  messages: ChatMessageUI[];
  sendMessage: (text: string) => void;
  sendProductMessage: (productId: string, productName: string) => void;
  sendCompareMessage: (products: ProductCardDTO[]) => void;
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

  const setLoading = useCallback((val: boolean) => {
    loadingRef.current = val;
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
      .sort((a, b) => new Date(a.created_at).getTime() - new Date(b.created_at).getTime())
      .map((msg) => {
        const citedMeta = msg.cited_products?.[0] as Record<string, unknown> | undefined;
        const answerHtml =
          typeof citedMeta?.answer_html === "string" && citedMeta.answer_html
            ? citedMeta.answer_html
            : undefined;

        return {
          id: msg.message_id,
          role: (msg.role.toLowerCase() === "user" ? "user" : "bot") as "user" | "bot",
          content: msg.content,
          ...(answerHtml ? { answerHtml } : {}),
          timestamp: new Date(msg.created_at),
          streamDone: true,
        };
      });
    setMessages(loaded);
    setActiveSessionId(sessionId);
    setSessionEnded(false);
    scrollToBottom();
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
    async (text: string) => {
      const trimmed = text.trim();
      if (!trimmed || loadingRef.current) return;

      // Slash command: /start — allowed even when session is ended
      if (trimmed.toLowerCase() === "/start") {
        setLoading(true);
        setError(null);
        try {
          const newSession = await httpClient.post<{ session_id: string }>(
            endpoints.createSession,
            { customer_id: customerId, channel: "web" }
          );
          setActiveSessionId(newSession.session_id);
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
          localStorage.setItem("session_updated", Date.now().toString());
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

      const userMessage: ChatMessageUI = {
        id: generateId(),
        role: "user",
        content: trimmed,
        timestamp: new Date(),
      };

      setMessages((prev) => [...prev, userMessage]);
      setLoading(true);
      setError(null);
      scrollToBottom();

      const body: ChatRequest = {
        message: trimmed,
        ...(customerId ? { customer_id: customerId } : {}),
        ...(activeSessionId ? { session_id: activeSessionId } : {}),
      };

      // Create a placeholder bot message for streaming
      const botId = generateId();
      const botMessage: ChatMessageUI = {
        id: botId,
        role: "bot",
        content: "",
        timestamp: new Date(),
      };
      setMessages((prev) => [...prev, botMessage]);

      setIsTyping(true);
      const controller = new AbortController();
      const timeout = setTimeout(() => controller.abort(), 30000);
      try {
        const res = await fetch(endpoints.chatStream, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
          signal: controller.signal,
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
                    const hasHtml = /<\/?(?:table|tr|td|th|ul|ol|li)\b/i.test(streamedContent);
                    if (event.session_id) setActiveSessionId(event.session_id);
                    if (event.checkout_data) console.log("[useChat] checkout_data from buffer:", event.checkout_data);
                    setMessages((prev) =>
                      prev.map((m) =>
                        m.id === botId
                          ? {
                              ...m,
                              id: event.message_id || botId,
                              content: streamedContent,
                              answerHtml: hasHtml && event.answer_html ? event.answer_html : undefined,
                              citedProducts: event.cited_products,
                              suggestions: event.suggestions,
                              continueUrl: event.continue_url || undefined,
                              checkoutData: event.checkout_data || undefined,
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
                const hasHtml = /<\/?(?:table|tr|td|th|ul|ol|li)\b/i.test(streamedContent);
                if (event.session_id) {
                  setActiveSessionId(event.session_id);
                }
                // Debug checkout data
                if (event.checkout_data) {
                  console.log("[useChat] checkout_data received:", event.checkout_data);
                }
                if (event.continue_url) {
                  console.log("[useChat] continue_url received:", event.continue_url);
                }
                setMessages((prev) =>
                  prev.map((m) =>
                    m.id === botId
                      ? {
                          ...m,
                          id: event.message_id || botId,
                          content: streamedContent,
                          answerHtml: hasHtml && event.answer_html ? event.answer_html : undefined,
                          citedProducts: event.cited_products,
                          suggestions: event.suggestions,
                          continueUrl: event.continue_url || undefined,
                          checkoutData: event.checkout_data || undefined,
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
        clearTimeout(timeout);
        setIsTyping(false);
        setLoading(false);
      }
    },
    [sessionEnded, customerId, activeSessionId, scrollToBottom, setLoading]
  );

  // Shared streaming helper for product/compare messages
  const streamRequest = useCallback(
    async (displayText: string, apiMessage: string) => {
      if (sessionEnded || loadingRef.current) return;

      const userMessage: ChatMessageUI = {
        id: generateId(),
        role: "user",
        content: displayText,
        timestamp: new Date(),
      };

      setMessages((prev) => [...prev, userMessage]);
      setLoading(true);
      setError(null);
      scrollToBottom();

      const botId = generateId();
      setMessages((prev) => [...prev, { id: botId, role: "bot", content: "", timestamp: new Date() }]);

      const body: ChatRequest = {
        message: apiMessage,
        ...(customerId ? { customer_id: customerId } : {}),
        ...(activeSessionId ? { session_id: activeSessionId } : {}),
      };

      setIsTyping(true);
      const controller = new AbortController();
      const timeout = setTimeout(() => controller.abort(), 30000);
      try {
        const res = await fetch(endpoints.chatStream, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
          signal: controller.signal,
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
                    const hasHtml = /<\/?(?:table|tr|td|th|ul|ol|li)\b/i.test(streamedContent);
                    if (event.session_id) setActiveSessionId(event.session_id);
                    setMessages((prev) =>
                      prev.map((m) =>
                        m.id === botId
                          ? {
                              ...m, id: event.message_id || botId, content: streamedContent,
                              answerHtml: hasHtml && event.answer_html ? event.answer_html : undefined,
                              citedProducts: event.cited_products, suggestions: event.suggestions,
                              continueUrl: event.continue_url || undefined,
                              checkoutData: event.checkout_data || undefined,
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
                const hasHtml = /<\/?(?:table|tr|td|th|ul|ol|li)\b/i.test(streamedContent);
                if (event.session_id) setActiveSessionId(event.session_id);
                setMessages((prev) =>
                  prev.map((m) =>
                    m.id === botId
                      ? {
                          ...m,
                          id: event.message_id || botId,
                          content: streamedContent,
                          answerHtml: hasHtml && event.answer_html ? event.answer_html : undefined,
                          citedProducts: event.cited_products,
                          suggestions: event.suggestions,
                          continueUrl: event.continue_url || undefined,
                          checkoutData: event.checkout_data || undefined,
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
        clearTimeout(timeout);
        setIsTyping(false);
        setLoading(false);
      }
    },
    [sessionEnded, customerId, activeSessionId, scrollToBottom, setLoading]
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

  return {
    messages,
    sendMessage,
    sendProductMessage,
    sendCompareMessage,
    isLoading,
    isTyping,
    isHistoryLoading,
    sessionEnded,
    activeSessionId,
    error,
    bottomRef,
  };
}
