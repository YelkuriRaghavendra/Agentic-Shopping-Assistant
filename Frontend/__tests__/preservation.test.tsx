/**
 * Preservation Property Tests — Property 2
 *
 * These tests MUST PASS on unfixed code.
 * They confirm baseline chat functionality that must be preserved after the fix.
 *
 * Validates: Requirements 3.1, 3.2, 3.4, 3.5, 3.6, 3.7, 3.8
 */

import React from "react";
import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import { ChatMessage } from "@/components/ChatMessage";
import { ChatInput } from "@/components/ChatInput";
import { TypingIndicator } from "@/components/TypingIndicator";
import type { ChatMessageUI } from "@/types/chat.types";

// ---------------------------------------------------------------------------
// Helpers / generators
// ---------------------------------------------------------------------------

function makeMessage(
  role: "user" | "bot",
  overrides: Partial<ChatMessageUI> = {}
): ChatMessageUI {
  return {
    id: "msg-1",
    role,
    content: "Hello world",
    timestamp: new Date("2024-01-01T00:00:00Z"),
    ...overrides,
  };
}

// A set of varied user message contents for property-style iteration
const USER_CONTENTS = [
  "Hello",
  "I need shoes",
  "Show me headphones",
  "What laptops do you have?",
  "a",
  "1234567890",
  "Special chars: !@#$%",
];

// Non-empty input strings for Enter-key property
const NON_EMPTY_INPUTS = ["hello", "shoes", "  trimmed  ", "a", "1", "test message"];

// ---------------------------------------------------------------------------
// Observation tests (concrete baseline)
// ---------------------------------------------------------------------------

describe("Preservation: Observation baseline on unfixed code", () => {
  it("3.1 ChatMessage (user) renders the violet gradient bubble", () => {
    const { container } = render(<ChatMessage message={makeMessage("user")} />);
    // The user bubble has from-violet-600 to-indigo-600 gradient classes
    const bubble = container.querySelector(".from-violet-600");
    expect(bubble).not.toBeNull();
  });

  it("3.2 ChatMessage (bot) renders the card-background bubble", () => {
    const { container } = render(<ChatMessage message={makeMessage("bot")} />);
    // Bot bubble uses bg-[hsl(var(--card))]
    const bubble = container.querySelector(".rounded-tl-sm");
    expect(bubble).not.toBeNull();
  });

  it("3.4 ChatInput calls onSend when Enter is pressed", () => {
    const onSend = vi.fn();
    render(<ChatInput onSend={onSend} />);
    const input = screen.getByRole("textbox");
    fireEvent.change(input, { target: { value: "hello" } });
    fireEvent.keyDown(input, { key: "Enter", code: "Enter" });
    expect(onSend).toHaveBeenCalledTimes(1);
    expect(onSend).toHaveBeenCalledWith("hello");
  });

  it("3.5 ChatInput calls onSend when send button is clicked", () => {
    const onSend = vi.fn();
    render(<ChatInput onSend={onSend} />);
    const input = screen.getByRole("textbox");
    fireEvent.change(input, { target: { value: "click test" } });
    const button = screen.getByRole("button", { name: /send/i });
    fireEvent.click(button);
    expect(onSend).toHaveBeenCalledTimes(1);
    expect(onSend).toHaveBeenCalledWith("click test");
  });

  it("3.7 ChatInput does NOT call onSend when disabled=true", () => {
    const onSend = vi.fn();
    render(<ChatInput onSend={onSend} disabled />);
    const input = screen.getByRole("textbox");
    fireEvent.change(input, { target: { value: "blocked" } });
    fireEvent.keyDown(input, { key: "Enter", code: "Enter" });
    const button = screen.getByRole("button", { name: /send/i });
    fireEvent.click(button);
    expect(onSend).not.toHaveBeenCalled();
  });

  it("3.6 TypingIndicator renders three animated dot spans", () => {
    const { container } = render(<TypingIndicator />);
    // Three dots: h-2 w-2 rounded-full bg-violet-400
    const dots = container.querySelectorAll(".h-2.w-2.rounded-full");
    expect(dots).toHaveLength(3);
  });
});

// ---------------------------------------------------------------------------
// Property-based tests (iterate over generated inputs)
// ---------------------------------------------------------------------------

describe("Preservation Property: user bubble gradient for any user message", () => {
  /**
   * Property: For any ChatMessage with role="user", the bubble has the user gradient class.
   * Validates: Requirements 3.1
   */
  USER_CONTENTS.forEach((content) => {
    it(`user bubble has from-violet-600 class for content: "${content}"`, () => {
      const { container } = render(
        <ChatMessage message={makeMessage("user", { content })} />
      );
      const bubble = container.querySelector(".from-violet-600");
      expect(bubble).not.toBeNull();
    });
  });
});

describe("Preservation Property: Enter key triggers onSend exactly once for any non-empty input", () => {
  /**
   * Property: For any non-empty input value, Enter key triggers onSend exactly once.
   * Validates: Requirements 3.4
   */
  NON_EMPTY_INPUTS.forEach((inputValue) => {
    it(`onSend called once for input: "${inputValue}"`, () => {
      const onSend = vi.fn();
      render(<ChatInput onSend={onSend} />);
      const input = screen.getByRole("textbox");
      fireEvent.change(input, { target: { value: inputValue } });
      fireEvent.keyDown(input, { key: "Enter", code: "Enter" });
      // Only trimmed non-empty values should trigger onSend
      if (inputValue.trim().length > 0) {
        expect(onSend).toHaveBeenCalledTimes(1);
      } else {
        expect(onSend).not.toHaveBeenCalled();
      }
    });
  });
});
