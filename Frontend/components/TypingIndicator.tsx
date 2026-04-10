"use client";

import { motion } from "framer-motion";

interface TypingIndicatorProps {
  variant?: "default" | "product-search" | "analysis";
}

export function TypingIndicator({ variant = "product-search" }: TypingIndicatorProps) {
  const isAnalysis = variant === "analysis";
  const dotColor = isAnalysis ? "#8B5CF6" : "#1D9E75";

  const bouncingVariants = {
    animate: (i: number) => ({
      y: [0, -12, 0],
      transition: {
        duration: 0.6,
        repeat: Infinity,
        delay: i * 0.1,
        ease: "easeInOut",
      },
    }),
  };

  return (
    <>
      {/* Bouncing dots only - no wrapper, no avatar */}
      <div className="flex items-center gap-1">
        {[0, 1, 2].map((i) => (
          <motion.span
            key={i}
            custom={i}
            animate="animate"
            variants={bouncingVariants}
            className="block h-2 w-2 rounded-full"
            style={{ background: dotColor }}
          />
        ))}
      </div>
    </>
  );
}
