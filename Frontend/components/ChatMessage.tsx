"use client";

import { motion } from "framer-motion";
import { Bot, ShoppingBag, Star, User } from "lucide-react";
import { cn, formatTimestamp } from "@/lib/utils";
import type { ChatMessage as ChatMessageType } from "@/types/chat.types";

interface ChatMessageProps {
  message: ChatMessageType;
}

export function ChatMessage({ message }: ChatMessageProps) {
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
        {isUser ? <User className="h-4 w-4 text-white" /> : <Bot className="h-4 w-4 text-white" />}
      </div>

      {/* Bubble + products */}
      <div
        className={cn(
          "flex max-w-[75%] flex-col gap-3",
          isUser ? "items-end" : "items-start"
        )}
      >
        {/* Text bubble */}
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
          {message.content}
        </motion.div>

        {/* Product cards */}
        {message.products && message.products.length > 0 && (
          <motion.div
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.35, delay: 0.1 }}
            className="flex flex-wrap gap-2"
          >
            {message.products.map((product) => (
              <motion.div
                key={product.id}
                whileHover={{ scale: 1.03, y: -2 }}
                transition={{ duration: 0.2 }}
                className="relative flex w-36 cursor-pointer flex-col gap-1.5 rounded-xl border border-white/10 bg-[hsl(var(--card))] p-3 shadow-lg transition-shadow hover:shadow-violet-500/20"
              >
                {/* Badge */}
                {product.badge && (
                  <span className="absolute right-2 top-2 rounded-full bg-violet-600 px-1.5 py-0.5 text-[10px] font-semibold text-white">
                    {product.badge}
                  </span>
                )}

                {/* Product image placeholder */}
                <div className="flex h-16 w-full items-center justify-center rounded-lg bg-white/5">
                  <ShoppingBag className="h-8 w-8 text-white/40" />
                </div>

                <p className="line-clamp-2 text-xs font-medium text-[hsl(var(--card-foreground))]">
                  {product.name}
                </p>

                <div className="flex items-center gap-1">
                  <Star className="h-3 w-3 fill-amber-400 text-amber-400" />
                  <span className="text-[11px] text-muted-foreground">
                    {product.rating}
                  </span>
                </div>

                <p className="text-sm font-bold text-violet-400">
                  {product.price}
                </p>
              </motion.div>
            ))}
          </motion.div>
        )}

        {/* Timestamp */}
        <span className="text-[11px] text-muted-foreground">
          {formatTimestamp(message.timestamp)}
        </span>
      </div>
    </motion.div>
  );
}
