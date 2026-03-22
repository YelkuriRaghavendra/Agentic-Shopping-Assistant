"use client";

import { AnimatePresence } from "framer-motion";
import { MessageBubble } from "./MessageBubble";
import { ChatInput } from "./ChatInput";
import { TypingIndicator } from "./TypingIndicator";
import type { ChatMessageUI } from "@/types/chat.types";
import type React from "react";

export interface ChatWindowProps {
  messages: ChatMessageUI[];
  sendMessage: (text: string) => void;
  sendProductMessage: (productId: string, productName: string) => void;
  isLoading: boolean;
  isTyping: boolean;
  inputDisabled: boolean;
  sessionEnded: boolean;
  bottomRef: React.RefObject<HTMLDivElement>;
  isHistoryLoading?: boolean;
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

export function ChatWindow({
  messages,
  sendMessage,
  sendProductMessage,
  isLoading,
  isTyping,
  inputDisabled,
  sessionEnded,
  bottomRef,
  isHistoryLoading = false,
}: ChatWindowProps) {
  return (
    <div className="flex h-full w-full flex-col" style={{ background: "#080809" }}>
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
      </div>

      {/* Messages area */}
      <div className="flex-1 overflow-y-auto py-4">
        {isHistoryLoading ? (
          <HistorySkeleton />
        ) : (
          <AnimatePresence initial={false}>
            {messages.map((msg) => (
              <MessageBubble
                key={msg.id}
                message={msg}
                onSelectProduct={sendProductMessage}
                onSelectSuggestion={sendMessage}
              />
            ))}
            {isTyping && <TypingIndicator key="typing" />}
          </AnimatePresence>
        )}
        <div ref={bottomRef} />
      </div>

      {/* Input */}
      <ChatInput
        onSend={sendMessage}
        disabled={inputDisabled || sessionEnded}
        sessionEnded={sessionEnded}
      />
    </div>
  );
}
