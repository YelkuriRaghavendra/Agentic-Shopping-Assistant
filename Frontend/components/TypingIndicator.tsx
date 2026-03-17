"use client";

import { motion } from "framer-motion";
import { Bot } from "lucide-react";

const DOT_VARIANTS = {
  initial: { y: 0 },
  animate: { y: -6 },
};

const TRANSITION_BASE = {
  duration: 0.4,
  repeat: Infinity,
  repeatType: "reverse" as const,
  ease: "easeInOut",
};

export function TypingIndicator() {
  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: 8 }}
      transition={{ duration: 0.2 }}
      className="flex items-center gap-3 px-4 py-2"
    >
      {/* Bot avatar */}
      <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-violet-500 to-indigo-600 text-sm shadow-lg">
        <Bot className="h-4 w-4 text-white" />
      </div>

      {/* Dots bubble */}
      <div className="flex items-center gap-1.5 rounded-2xl rounded-tl-sm bg-[hsl(var(--card))] px-4 py-3 shadow-md">
        {[0, 1, 2].map((i) => (
          <motion.span
            key={i}
            className="block h-2 w-2 rounded-full bg-violet-400"
            variants={DOT_VARIANTS}
            initial="initial"
            animate="animate"
            transition={{ ...TRANSITION_BASE, delay: i * 0.15 }}
          />
        ))}
      </div>
    </motion.div>
  );
}
