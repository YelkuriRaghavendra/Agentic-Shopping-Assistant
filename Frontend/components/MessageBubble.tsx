"use client";

import { motion } from "framer-motion";
import { Bot, User } from "lucide-react";
import { cn, formatTimestamp } from "@/lib/utils";
import { sanitizeHtml } from "@/lib/sanitize";
import { ProductSlider } from "@/components/ProductSlider";
import { SuggestionChips } from "@/components/SuggestionChips";
import type { ChatMessageUI } from "@/types/chat.types";

export interface MessageBubbleProps {
  message: ChatMessageUI;
  onSelectProduct?: (productId: string, productName: string) => void;
  onSelectSuggestion?: (message: string) => void;
}

export function MessageBubble({ message, onSelectProduct, onSelectSuggestion }: MessageBubbleProps) {
  const isUser = message.role === "user";

  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3, ease: "easeOut" }}
      className={cn(
        "flex w-full gap-3 px-4 py-1",
        isUser ? "flex-row-reverse" : "flex-row"
      )}
    >
      {/* Avatar */}
      <div
        className={cn(
          "flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-sm shadow-md",
          isUser
            ? "bg-gradient-to-br from-emerald-400 to-teal-500"
            : "bg-gradient-to-br from-violet-500 to-indigo-600"
        )}
      >
        {isUser ? (
          <User className="h-4 w-4 text-white" />
        ) : (
          <Bot className="h-4 w-4 text-white" />
        )}
      </div>

      {/* Bubble */}
      <div
        className={cn(
          "flex max-w-[75%] flex-col gap-3",
          isUser ? "items-end" : "items-start"
        )}
      >
        <motion.div
          whileHover={{ scale: 1.01 }}
          transition={{ duration: 0.15 }}
          className={cn(
            "rounded-2xl px-4 py-2.5 text-sm leading-relaxed shadow-md",
            isUser
              ? "rounded-tr-sm bg-gradient-to-br from-violet-600 to-indigo-600 text-white"
              : "rounded-tl-sm bg-[hsl(var(--card))] text-[hsl(var(--card-foreground))]"
          )}
        >
          {message.answerHtml ? (
            <div
              className="prose prose-invert prose-sm"
              dangerouslySetInnerHTML={{ __html: sanitizeHtml(message.answerHtml) }}
            />
          ) : (
            message.content
          )}
        </motion.div>

        {/* Product slider */}
        {!isUser && message.citedProducts && message.citedProducts.length > 0 && onSelectProduct && (
          <ProductSlider products={message.citedProducts} onSelectProduct={onSelectProduct} />
        )}

        {/* Suggestion chips */}
        {!isUser && message.suggestions && message.suggestions.length > 0 && onSelectSuggestion && (
          <SuggestionChips suggestions={message.suggestions} onSelectSuggestion={onSelectSuggestion} />
        )}

        {/* Timestamp */}
        <span className="text-[11px] text-muted-foreground">
          {formatTimestamp(message.timestamp)}
        </span>
      </div>
    </motion.div>
  );
}
