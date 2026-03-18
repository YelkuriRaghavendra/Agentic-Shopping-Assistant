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
      try {
        const data = await httpClient.get<MessageHistoryResponse>(
          endpoints.sessionMessages(sessionId!)
        );
        if (cancelled) return;

        const loaded: ChatMessageUI[] = data.messages.map((msg) => ({
          id: msg.id,
          role: msg.role === "user" ? "user" : "bot",
          content: msg.content,
          timestamp: new Date(msg.created_at),
        }));
        setMessages(loaded);
        setActiveSessionId(sessionId);
        scrollToBottom();
      } catch {
        // preserve existing messages on history load error
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
      if (!trimmed || sessionEnded || isLoading) return;

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
    sessionEnded,
    activeSessionId,
    error,
    bottomRef,
  };
}
