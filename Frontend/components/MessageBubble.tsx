"use client";

import { memo } from "react";
import { motion } from "framer-motion";
import { cn, formatTimestamp } from "@/lib/utils";
import { sanitizeHtml } from "@/lib/sanitize";
import { ProductSlider } from "@/components/ProductSlider";
import { SuggestionChips } from "@/components/SuggestionChips";
import type { ChatMessageUI, ProductCardDTO } from "@/types/chat.types";

export interface MessageBubbleProps {
  message: ChatMessageUI;
  onSelectProduct?: (productId: string, productName: string) => void;
  onSelectSuggestion?: (message: string) => void;
  onCompareProducts?: (products: ProductCardDTO[]) => void;
}

export const MessageBubble = memo(function MessageBubble({ message, onSelectProduct, onSelectSuggestion, onCompareProducts }: MessageBubbleProps) {
  const isUser = message.role === "user";

  return (
    <motion.div
      role="article"
      aria-label={isUser ? "Your message" : "Assistant message"}
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.25, ease: "easeOut" }}
      className={cn("flex w-full gap-3 px-6 py-2", isUser ? "flex-row-reverse" : "flex-row")}
    >
      {/* Avatar */}
      <div
        className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full text-[9px] font-mono uppercase tracking-wider"
        style={
          isUser
            ? { background: "#1D9E75", color: "#000" }
            : { background: "#111116", border: "1px solid rgba(29,158,117,0.3)", color: "#1D9E75" }
        }
      >
        {isUser ? "U" : "Vy"}
      </div>

      {/* Bubble + extras */}
      <div className={cn("flex max-w-[80%] flex-col gap-2", isUser ? "items-end" : "items-start")}>
        {/* Text bubble */}
        <div
          className="px-4 py-2.5 text-[13px] leading-[1.75]"
          style={
            isUser
              ? {
                  background: "linear-gradient(135deg, #1D9E75, #0F6E56)",
                  borderRadius: "16px 16px 4px 16px",
                  color: "#fff",
                  fontWeight: 400,
                }
              : {
                  background: "#111116",
                  border: "1px solid rgba(255,255,255,0.07)",
                  borderRadius: "16px 16px 16px 4px",
                  color: "rgba(255,255,255,0.82)",
                  fontWeight: 300,
                }
          }
        >
          {message.answerHtml ? (
            <div
              className="prose prose-sm max-w-none"
              style={{ color: "rgba(255, 255, 255, 1)" }}
              dangerouslySetInnerHTML={{ __html: sanitizeHtml(message.answerHtml) }}
            />
          ) : (
            <>
              {message.content || null}
              {!isUser && !message.streamDone && <span className="streaming-cursor" style={{ minHeight: 14 }} />}
            </>
          )}
        </div>

        {/* Product slider */}
        {!isUser && message.citedProducts && message.citedProducts.length > 0 && onSelectProduct && (
          <ProductSlider products={message.citedProducts} onSelectProduct={onSelectProduct} onCompareProducts={onCompareProducts} />
        )}

        {/* Suggestion chips */}
        {!isUser && message.suggestions && message.suggestions.length > 0 && onSelectSuggestion && (
          <SuggestionChips suggestions={message.suggestions} onSelectSuggestion={onSelectSuggestion} />
        )}

        {/* Timestamp */}
        <span
          className="font-mono text-[9px] uppercase tracking-widest"
          style={{ color: "rgba(255,255,255,0.2)", letterSpacing: "1px" }}
        >
          {formatTimestamp(message.timestamp)}
        </span>
      </div>
    </motion.div>
  );
});
