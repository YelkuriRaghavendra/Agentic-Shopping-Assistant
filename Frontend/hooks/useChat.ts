"use client";

import { useState, useCallback, useRef, useEffect } from "react";
import { httpClient } from "@/services/httpClient";
import { endpoints } from "@/config/config";
import type {
  ChatMessageUI,
  ChatRequest,
  ChatResponse,
  MessageHistoryResponse,
} from "@/types/chat.types";

interface UseChatReturn {
  messages: ChatMessageUI[];
  sendMessage: (text: string) => void;
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
  const [isTyping, setIsTyping] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [isHistoryLoading, setIsHistoryLoading] = useState(false);
  const [activeSessionId, setActiveSessionId] = useState<string | null>(sessionId);
  const [sessionEnded, setSessionEnded] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const bottomRef = useRef<HTMLDivElement | null>(null);

  const scrollToBottom = useCallback(() => {
    setTimeout(() => {
      bottomRef.current?.scrollIntoView({ behavior: "smooth" });
    }, 50);
  }, []);

  // Load message history when sessionId prop changes
  useEffect(() => {
    if (!sessionId) return;

    let cancelled = false;

    async function loadHistory() {
      setIsHistoryLoading(true);
      try {
        const data = await httpClient.get<MessageHistoryResponse>(
          endpoints.sessionMessages(sessionId!)
        );
        if (cancelled) return;

        const loaded: ChatMessageUI[] = data.messages.map((msg) => {
          // Extract answer_html from cited_products metadata if present
          const citedMeta = msg.cited_products?.[0] as Record<string, unknown> | undefined;
          const answerHtml =
            typeof citedMeta?.answer_html === "string" && citedMeta.answer_html
              ? citedMeta.answer_html
              : undefined;

          return {
            id: msg.id,
            role: (msg.role === "user" ? "user" : "bot") as "user" | "bot",
            content: msg.content,
            ...(answerHtml ? { answerHtml } : {}),
            timestamp: new Date(msg.created_at),
          };
        });
        setMessages(loaded);
        setActiveSessionId(sessionId);
        scrollToBottom();
      } catch {
        // preserve existing messages on history load error
      } finally {
        if (!cancelled) setIsHistoryLoading(false);
      }
    }

    loadHistory();
    return () => {
      cancelled = true;
    };
  }, [sessionId, scrollToBottom]);

  const sendMessage = useCallback(
    async (text: string) => {
      const trimmed = text.trim();
      if (!trimmed || isLoading) return;

      // Slash command: /start — allowed even when session is ended
      if (trimmed.toLowerCase() === "/start") {
        setIsLoading(true);
        setError(null);
        try {
          const newSession = await httpClient.post<{ id: string }>(
            endpoints.createSession,
            { customer_id: customerId, channel: "web" }
          );
          setActiveSessionId(newSession.id);
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
          setIsLoading(false);
        }
        return;
      }

      // Slash command: /end
      if (trimmed.toLowerCase() === "/end") {
        if (!activeSessionId || sessionEnded || isLoading) return;
        setIsLoading(true);
        setError(null);
        try {
          await httpClient.post(endpoints.endSession(activeSessionId), {});
          setSessionEnded(true);
          const infoMsg: ChatMessageUI = {
            id: generateId(),
            role: "bot",
            content: "Session ended.",
            timestamp: new Date(),
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
          setIsLoading(false);
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
      setIsTyping(true);
      setIsLoading(true);
      setError(null);
      scrollToBottom();

      const body: ChatRequest = {
        message: trimmed,
        ...(customerId ? { customer_id: customerId } : {}),
        ...(activeSessionId ? { session_id: activeSessionId } : {}),
      };

      try {
        const data = await httpClient.post<ChatResponse>(endpoints.chat, body);

        setActiveSessionId(data.session_id);

        const botMessage: ChatMessageUI = {
          id: data.message_id,
          role: "bot",
          content: data.answer,
          answerHtml: data.answer_html || undefined,
          timestamp: new Date(),
          suggestions: data.suggestions,
        };

        setMessages((prev) => [...prev, botMessage]);
        scrollToBottom();
      } catch (err) {
        const errorMessage: ChatMessageUI = {
          id: generateId(),
          role: "bot",
          content: "Oops, something went wrong. Please try again.",
          timestamp: new Date(),
        };
        setMessages((prev) => [...prev, errorMessage]);
        setError(err instanceof Error ? err.message : "Unknown error");
        scrollToBottom();
      } finally {
        setIsTyping(false);
        setIsLoading(false);
      }
    },
    [sessionEnded, isLoading, customerId, activeSessionId, scrollToBottom]
  );

  return {
    messages,
    sendMessage,
    isLoading,
    isTyping,
    isHistoryLoading,
    sessionEnded,
    activeSessionId,
    error,
    bottomRef,
  };
}
