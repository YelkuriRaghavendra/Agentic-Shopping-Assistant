"use client";

import { AnimatePresence } from "framer-motion";
import { Bot, Sparkles } from "lucide-react";
import { ChatMessage } from "./ChatMessage";
import { ChatInput } from "./ChatInput";
import { TypingIndicator } from "./TypingIndicator";
import { useChat } from "@/hooks/useChat";

export function ChatWindow() {
  const { messages, sendMessage, isLoading, isTyping, bottomRef } = useChat();

  return (
    <div className="flex h-full w-full flex-col overflow-hidden rounded-2xl border border-white/10 bg-[hsl(var(--background))] shadow-2xl shadow-black/40">
      {/* Header */}
      <div className="flex items-center gap-3 border-b border-white/10 bg-white/5 px-5 py-4 backdrop-blur-sm">
        <div className="flex h-10 w-10 items-center justify-center rounded-full bg-gradient-to-br from-violet-500 to-indigo-600 shadow-lg shadow-violet-500/30">
          <Bot className="h-5 w-5 text-white" />
        </div>
        <div>
          <div className="flex items-center gap-1.5">
            <h1 className="text-sm font-semibold text-white">ShopBot AI</h1>
            <Sparkles className="h-3.5 w-3.5 text-violet-400" />
          </div>
          <div className="flex items-center gap-1.5">
            <span className="h-1.5 w-1.5 rounded-full bg-emerald-400 shadow-sm shadow-emerald-400/50" />
            <p className="text-xs text-white/50">Online · Your personal shopping assistant</p>
          </div>
        </div>
      </div>

      {/* Messages area */}
      <div className="flex-1 overflow-y-auto py-4 scrollbar-thin scrollbar-track-transparent scrollbar-thumb-white/10">
        <AnimatePresence initial={false}>
          {messages.map((msg) => (
            <ChatMessage key={msg.id} message={msg} />
          ))}

          {isTyping && <TypingIndicator key="typing" />}
        </AnimatePresence>

        {/* Scroll anchor */}
        <div ref={bottomRef} />
      </div>

      {/* Input */}
      <ChatInput onSend={sendMessage} disabled={isLoading} />
    </div>
  );
}
