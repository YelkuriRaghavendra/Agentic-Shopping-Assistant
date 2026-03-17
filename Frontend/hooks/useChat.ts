"use client";

import { useState, useCallback, useRef } from "react";
import { useMutation } from "@tanstack/react-query";
import { sendChatMessage } from "@/services/chatService";
import { generateId } from "@/lib/utils";
import type { ChatMessage, SendMessagePayload } from "@/types/chat.types";

const CONVERSATION_ID = generateId();

const WELCOME_MESSAGE: ChatMessage = {
  id: "welcome",
  role: "bot",
  content:
    "Hey there! 👋 I'm your personal shopping assistant. Ask me about shoes, headphones, laptops, watches, or anything else you're looking for!",
  timestamp: new Date(),
};

export function useChat() {
  const [messages, setMessages] = useState<ChatMessage[]>([WELCOME_MESSAGE]);
  const [isTyping, setIsTyping] = useState(false);
  const bottomRef = useRef<HTMLDivElement | null>(null);

  const scrollToBottom = useCallback(() => {
    setTimeout(() => {
      bottomRef.current?.scrollIntoView({ behavior: "smooth" });
    }, 50);
  }, []);

  const { mutate, isPending, error } = useMutation({
    mutationFn: (payload: SendMessagePayload) => sendChatMessage(payload),
    onMutate: () => {
      setIsTyping(true);
      scrollToBottom();
    },
    onSuccess: (data) => {
      setIsTyping(false);
      const botMessage: ChatMessage = {
        id: data.id,
        role: "bot",
        content: data.content,
        timestamp: data.timestamp,
        products: data.products,
      };
      setMessages((prev) => [...prev, botMessage]);
      scrollToBottom();
    },
    onError: () => {
      setIsTyping(false);
      const errorMessage: ChatMessage = {
        id: generateId(),
        role: "bot",
        content: "Oops, something went wrong. Please try again! 😅",
        timestamp: new Date(),
      };
      setMessages((prev) => [...prev, errorMessage]);
      scrollToBottom();
    },
  });

  const sendMessage = useCallback(
    (text: string) => {
      const trimmed = text.trim();
      if (!trimmed || isPending) return;

      const userMessage: ChatMessage = {
        id: generateId(),
        role: "user",
        content: trimmed,
        timestamp: new Date(),
      };

      setMessages((prev) => [...prev, userMessage]);
      scrollToBottom();

      mutate({ message: trimmed, conversationId: CONVERSATION_ID });
    },
    [isPending, mutate, scrollToBottom]
  );

  return {
    messages,
    sendMessage,
    isLoading: isPending,
    isTyping,
    error,
    bottomRef,
  };
}
