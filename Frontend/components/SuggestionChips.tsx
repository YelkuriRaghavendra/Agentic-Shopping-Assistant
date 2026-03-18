"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
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
        <Button
          key={i}
          variant="outline"
          size="sm"
          className="rounded-full text-xs border-violet-500/40 text-violet-300 hover:bg-violet-500/20 hover:text-violet-100"
          onClick={() => handleClick(chip)}
        >
          {chip.icon && <span className="mr-1">{chip.icon}</span>}
          {chip.label}
        </Button>
      ))}
    </div>
  );
}
