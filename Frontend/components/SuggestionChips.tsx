"use client";

import { useState } from "react";
import type { SuggestionChip } from "@/types/chat.types";

export interface SuggestionChipsProps {
  suggestions: SuggestionChip[];
  onSelectSuggestion: (message: string) => void;
}

export function SuggestionChips({ suggestions, onSelectSuggestion }: SuggestionChipsProps) {
  const [dismissed, setDismissed] = useState(false);

  if (dismissed || suggestions.length === 0) return null;

  function handleClick(chip: SuggestionChip) {
    setDismissed(true);
    onSelectSuggestion(chip.message);
  }

  return (
    <div className="flex flex-wrap gap-2 mt-1">
      {suggestions.map((chip, i) => (
        <button
          key={i}
          onClick={() => handleClick(chip)}
          className="font-mono text-[9px] uppercase tracking-widest px-3.5 py-1.5 transition-all duration-150"
          style={{
            border: "1px solid rgba(29,158,117,0.3)",
            background: "rgba(29,158,117,0.05)",
            color: "rgba(29,158,117,0.8)",
            borderRadius: "20px",
            letterSpacing: "1.5px",
          }}
          onMouseEnter={(e) => {
            (e.currentTarget as HTMLButtonElement).style.background = "rgba(29,158,117,0.12)";
            (e.currentTarget as HTMLButtonElement).style.borderColor = "rgba(93,202,165,0.6)";
          }}
          onMouseLeave={(e) => {
            (e.currentTarget as HTMLButtonElement).style.background = "rgba(29,158,117,0.05)";
            (e.currentTarget as HTMLButtonElement).style.borderColor = "rgba(29,158,117,0.3)";
          }}
        >
          {chip.icon && <span className="mr-1">{chip.icon}</span>}
          {chip.label}
        </button>
      ))}
    </div>
  );
}
