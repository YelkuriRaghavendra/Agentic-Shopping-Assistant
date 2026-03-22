"use client";

import { motion } from "framer-motion";

export function TypingIndicator() {
  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: 8 }}
      transition={{ duration: 0.2 }}
      className="flex items-center gap-3 px-6 py-2"
    >
      {/* Avatar */}
      <div
        className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full font-mono text-[9px] uppercase"
        style={{ background: "#111116", border: "1px solid rgba(29,158,117,0.3)", color: "#1D9E75" }}
      >
        Vy
      </div>

      {/* Dots bubble */}
      <div
        className="flex items-center gap-1.5 px-4 py-3"
        style={{
          background: "#111116",
          border: "1px solid rgba(255,255,255,0.07)",
          borderRadius: "16px 16px 16px 4px",
        }}
      >
        {[0, 1, 2].map((i) => (
          <span
            key={i}
            className="block h-1.5 w-1.5 rounded-full animate-tdot"
            style={{
              background: "#1D9E75",
              animationDelay: `${i * 0.15}s`,
            }}
          />
        ))}
      </div>
    </motion.div>
  );
}
