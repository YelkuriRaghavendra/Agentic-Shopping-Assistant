"use client";

import { useState } from "react";
import type { SuggestionChip } from "@/types/chat.types";
import { chipStyle, chipHoverStyle } from "@/lib/theme";

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
          style={chipStyle}
          onMouseEnter={(e) => Object.assign((e.currentTarget as HTMLButtonElement).style, chipHoverStyle)}
          onMouseLeave={(e) => Object.assign((e.currentTarget as HTMLButtonElement).style, { background: chipStyle.background, border: chipStyle.border })}
        >
          {chip.icon && <span className="mr-1">{chip.icon}</span>}
          {chip.label}
        </button>
      ))}
    </div>
  );
}
