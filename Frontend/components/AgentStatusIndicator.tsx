"use client";

import { motion, AnimatePresence } from "framer-motion";

interface AgentStatusProps {
  status: string | null;
  agent: string | null;
}

const AGENT_LABELS: Record<string, string> = {
  shopping: "Shopping Assistant",
  style_advisor: "Style Advisor",
  gift_finder: "Gift Finder",
  support: "Support Agent",
  checkout: "Checkout Assistant",
};

export default function AgentStatusIndicator({ status, agent }: AgentStatusProps) {
  if (!status) return null;

  const label = agent ? AGENT_LABELS[agent] || agent : "Assistant";

  return (
    <AnimatePresence>
      <motion.div
        initial={{ opacity: 0, y: 5 }}
        animate={{ opacity: 1, y: 0 }}
        exit={{ opacity: 0 }}
        className="flex items-center gap-2 px-4 py-1 text-xs text-gray-400"
      >
        <span className="inline-block w-2 h-2 rounded-full bg-teal-400 animate-pulse" />
        <span>{label}: {status}</span>
      </motion.div>
    </AnimatePresence>
  );
}
