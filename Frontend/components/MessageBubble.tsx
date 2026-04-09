"use client";

import { memo } from "react";
import { motion } from "framer-motion";
import { cn, formatTimestamp } from "@/lib/utils";
import { sanitizeHtml } from "@/lib/sanitize";
import { marked } from "marked";
import { ProductSlider } from "@/components/ProductSlider";

/** Convert markdown or raw HTML content to sanitized HTML */
function renderContent(text: string): string {
  // Replace literal \n with actual newlines (backend sometimes sends escaped)
  let cleaned = text.replace(/\\n/g, "\n");

  // If it already contains HTML tags, sanitize and return
  if (/<\/?(?:table|tr|td|th|ul|ol|li|p|br|div|strong|em|a)\b/i.test(cleaned)) {
    return sanitizeHtml(cleaned);
  }
  // Convert markdown to HTML, then sanitize
  const html = marked.parse(cleaned, { async: false, breaks: true }) as string;
  return sanitizeHtml(html);
}
import { SuggestionChips } from "@/components/SuggestionChips";
import { OrderConfirmationCard } from "@/components/OrderConfirmationCard";
import { PaymentSetupCard } from "@/components/cards/PaymentSetupCard";
import { AddressFormCard } from "@/components/cards/AddressFormCard";
import type { ChatMessageUI, ProductCardDTO } from "@/types/chat.types";

export interface MessageBubbleProps {
  message: ChatMessageUI;
  onSelectProduct?: (productId: string, productName: string) => void;
  onSelectSuggestion?: (message: string) => void;
  onCompareProducts?: (products: ProductCardDTO[]) => void;
  onCheckoutAction?: (action: string, payload: Record<string, unknown>) => void;
}

export const MessageBubble = memo(function MessageBubble({ message, onSelectProduct, onSelectSuggestion, onCompareProducts, onCheckoutAction }: MessageBubbleProps) {
  const isUser = message.role === "user";

  return (
    <motion.div
      role="article"
      aria-label={isUser ? "Your message" : "Assistant message"}
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.25, ease: "easeOut" }}
      className="flex w-full flex-col px-6 py-2 gap-2"
    >
      {/* Avatar + bubble row */}
      <div className={cn("flex w-full gap-3", isUser ? "flex-row-reverse" : "flex-row")}>
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
          {/* Uploaded image */}
          {isUser && message.imageBase64 && (
            <img
              src={message.imageBase64}
              alt="Uploaded outfit"
              className="rounded-lg mb-2"
              style={{ maxWidth: 240, maxHeight: 240, objectFit: "cover" }}
            />
          )}
          {!isUser && message.streamDone && message.content ? (
            <div
              className="prose prose-sm max-w-none"
              style={{ color: "rgba(255, 255, 255, 1)" }}
              suppressHydrationWarning
              dangerouslySetInnerHTML={{
                __html: message.answerHtml
                  ? sanitizeHtml(message.answerHtml.replace(/\\n/g, "\n"))
                  : renderContent(message.content),
              }}
            />
          ) : (
            <>
              {message.content?.replace(/\\n/g, "\n") || null}
              {!isUser && !message.streamDone && <span className="streaming-cursor" style={{ minHeight: 14 }} />}
            </>
          )}
        </div>

        {/* Order Confirmation Card */}
        {!isUser && message.orderConfirmation && (
          <OrderConfirmationCard order={message.orderConfirmation} />
        )}

        {/* Inline Payment Setup Card */}
        {!isUser && message.setupIntentSecret && onCheckoutAction && (
          <PaymentSetupCard
            clientSecret={message.setupIntentSecret}
            onComplete={(pm) => onCheckoutAction("payment_setup_complete", { payment_method: pm })}
            onError={(reason) => onCheckoutAction("payment_setup_failed", { reason })}
          />
        )}

        {/* Inline Address Form Card */}
        {!isUser && message.addressFormData && onCheckoutAction && (
          <AddressFormCard
            prefilled={message.addressFormData}
            onSubmit={(addr) => onCheckoutAction("address_submitted", addr)}
          />
        )}

        {/* Suggestion chips */}
        {!isUser && !message.checkoutData && message.suggestions && message.suggestions.length > 0 && onSelectSuggestion && (
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
      </div>{/* end avatar+bubble row */}

      {/* Product slider — full width below the bubble row */}
      {!isUser && message.citedProducts && message.citedProducts.length > 0 && onSelectProduct && (
        <div className="pl-10">
          <ProductSlider products={message.citedProducts} onSelectProduct={onSelectProduct} onCompareProducts={onCompareProducts} />
        </div>
      )}
    </motion.div>
  );
});
