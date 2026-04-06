/**
 * Bug Condition Exploration Tests — Property 1
 *
 * These tests MUST FAIL on unfixed code.
 * Failure confirms the bug exists. They encode the expected (fixed) behavior
 * and will pass once the fix is applied.
 *
 * Validates: Requirements 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7, 1.8, 1.9
 */

import React from "react";
import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import { ChatMessage } from "@/components/ChatMessage";
import { TypingIndicator } from "@/components/TypingIndicator";
import { ChatInput } from "@/components/ChatInput";
import type { ChatMessageUI } from "@/types/chat.types";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function makeBotMessage(overrides: Partial<ChatMessageUI> = {}): ChatMessageUI {
  return {
    id: "msg-bot-1",
    role: "bot",
    content: "Hello, how can I help you?",
    timestamp: new Date("2024-01-01T00:00:00Z"),
    ...overrides,
  };
}

function makeUserMessage(overrides: Partial<ChatMessageUI> = {}): ChatMessageUI {
  return {
    id: "msg-user-1",
    role: "user",
    content: "I need some shoes",
    timestamp: new Date("2024-01-01T00:00:00Z"),
    ...overrides,
  };
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("Bug Condition: No emoji icons or raw form elements in UI", () => {
  it("1.1 ChatMessage (bot role) does NOT render 🤖 emoji", () => {
    const { container } = render(<ChatMessage message={makeBotMessage()} />);
    expect(container.textContent).not.toContain("🤖");
  });

  it("1.2 ChatMessage (user role) does NOT render 🧑 emoji", () => {
    const { container } = render(<ChatMessage message={makeUserMessage()} />);
    expect(container.textContent).not.toContain("🧑");
  });

  it("1.3 ChatMessage renders without product cards", () => {
    const { container } = render(
      <ChatMessage message={makeBotMessage()} />
    );
    expect(container.textContent).not.toContain("🛍️");
  });

  it("1.4 TypingIndicator does NOT render 🤖 emoji", () => {
    const { container } = render(<TypingIndicator />);
    expect(container.textContent).not.toContain("🤖");
  });

  it("1.5 ChatInput does NOT contain a raw <input> element", () => {
    const { container } = render(<ChatInput onSend={() => {}} />);
    // A raw visible <input> should not be a direct child of the flex wrapper div.
    // The hidden file input (aria-hidden, class="hidden") is acceptable.
    // Only non-hidden direct div > input children are disallowed.
    const directInputChildren = container.querySelectorAll("div > input");
    const visibleDirectInputs = Array.from(directInputChildren).filter(
      (el) => !el.classList.contains("hidden") && el.getAttribute("aria-hidden") !== "true"
    );
    expect(visibleDirectInputs).toHaveLength(0);
  });
});
