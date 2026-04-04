"use client";

import { useState } from "react";
import { AnimatePresence } from "framer-motion";
import { MessageBubble } from "./MessageBubble";
import { ChatInput } from "./ChatInput";
import { TypingIndicator } from "./TypingIndicator";
import { CheckoutModal } from "./CheckoutModal";
import type { ChatMessageUI, ProductCardDTO, CheckoutData, OrderConfirmation } from "@/types/chat.types";

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
}: ChatWindowProps) {
  const [checkoutOpen, setCheckoutOpen] = useState(false);
  const [checkoutData, setCheckoutData] = useState<CheckoutData | null>(null);

  const handleCheckout = (message: ChatMessageUI) => {
    if (message.checkoutData) {
      setCheckoutData(message.checkoutData);
      setCheckoutOpen(true);
    }
  };

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
                onCheckout={handleCheckout}
              />
            ))}
            {isTyping && !messages.some((m) => m.role === "bot" && !m.streamDone) && (
              <TypingIndicator key="typing" />
            )}
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

      {/* Checkout Modal */}
      {checkoutData && (
        <CheckoutModal
          open={checkoutOpen}
          checkoutData={checkoutData}
          customerId={customerId ?? undefined}
          updateProfile={updateProfile}
          onClose={() => setCheckoutOpen(false)}
          onComplete={(orderInfo) => {
            if (orderInfo && addOrderConfirmation) {
              addOrderConfirmation(orderInfo);
            } else {
              sendMessage("My order has been placed successfully!");
            }
          }}
        />
      )}
    </div>
  );
}
