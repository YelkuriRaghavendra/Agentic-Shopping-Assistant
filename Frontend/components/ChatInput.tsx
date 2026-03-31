"use client";

import { useState, type KeyboardEvent } from "react";
import { Input } from "@/components/ui/input";

interface ChatInputProps {
  onSend: (message: string) => void;
  disabled?: boolean;
  sessionEnded?: boolean;
}

export function ChatInput({ onSend, disabled = false, sessionEnded = false }: ChatInputProps) {
  const [value, setValue] = useState("");

  const handleSend = () => {
    if (!value.trim() || disabled) return;
    onSend(value);
    setValue("");
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const placeholder = disabled && sessionEnded
    ? "This session has ended"
    : disabled
    ? "Thinking..."
    : value.startsWith("/")
    ? "Commands: /start · /end"
    : "Ask me anything...";

  return (
    <div
      className="flex items-center gap-3 px-4 py-3 shrink-0"
      style={{ borderTop: "0.5px solid rgba(255,255,255,0.06)", background: "#0C0C0F" }}
    >
      <div className="flex flex-1 items-center gap-2 px-4 py-2.5" style={{
        background: "rgba(255,255,255,0.03)",
        border: "1px solid rgba(255,255,255,0.09)",
        borderRadius: "24px",
        transition: "border-color 0.2s ease",
      }}>
        <Input
          type="text"
          value={value}
          onChange={(e) => setValue(e.target.value)}
          onKeyDown={handleKeyDown}
          disabled={disabled}
          placeholder={placeholder}
          maxLength={2000}
          aria-label="Chat message input"
          className="flex-1 bg-transparent text-[13px] outline-none border-none ring-0 focus-visible:ring-0 focus-visible:ring-offset-0 disabled:cursor-not-allowed h-auto p-0"
          style={{
            color: "rgba(255,255,255,0.65)",
            fontFamily: "var(--font-inter)",
            fontWeight: 300,
          }}
        />
      </div>

      {/* Send button */}
      <button
        onClick={handleSend}
        disabled={disabled || !value.trim()}
        aria-label="Send message"
        className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full transition-all duration-200 disabled:cursor-not-allowed disabled:opacity-30"
        style={{
          background: value.trim() && !disabled ? "#1D9E75" : "rgba(255,255,255,0.08)",
        }}
      >
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ color: value.trim() && !disabled ? "#000" : "rgba(255,255,255,0.4)" }}>
          <line x1="22" y1="2" x2="11" y2="13" />
          <polygon points="22 2 15 22 11 13 2 9 22 2" />
        </svg>
      </button>
    </div>
  );
}
