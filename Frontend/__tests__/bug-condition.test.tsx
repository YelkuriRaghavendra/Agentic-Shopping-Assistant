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
import { sendChatMessage } from "@/services/chatService";
import type { ChatMessage as ChatMessageType } from "@/types/chat.types";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function makeBotMessage(overrides: Partial<ChatMessageType> = {}): ChatMessageType {
  return {
    id: "msg-bot-1",
    role: "bot",
    content: "Hello, how can I help you?",
    timestamp: new Date("2024-01-01T00:00:00Z"),
    ...overrides,
  };
}

function makeUserMessage(overrides: Partial<ChatMessageType> = {}): ChatMessageType {
  return {
    id: "msg-user-1",
    role: "user",
    content: "I need some shoes",
    timestamp: new Date("2024-01-01T00:00:00Z"),
    ...overrides,
  };
}

const MOCK_PRODUCTS: ChatMessageType["products"] = [
  {
    id: "p1",
    name: "Nike Air Max",
    price: "$129.99",
    image: "https://example.com/img.png",
    rating: 4.8,
    badge: "Best Seller",
  },
];

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

  it("1.3 ChatMessage with products does NOT render 🛍️ emoji", () => {
    const { container } = render(
      <ChatMessage message={makeBotMessage({ products: MOCK_PRODUCTS })} />
    );
    expect(container.textContent).not.toContain("🛍️");
  });

  it("1.4 TypingIndicator does NOT render 🤖 emoji", () => {
    const { container } = render(<TypingIndicator />);
    expect(container.textContent).not.toContain("🤖");
  });

  it("1.5 ChatInput does NOT contain a raw <input> element", () => {
    const { container } = render(<ChatInput onSend={() => {}} />);
    // A raw <input> should not exist — only a shadcn/ui-wrapped one
    const rawInputs = container.querySelectorAll("input");
    // shadcn/ui Input renders an <input> internally, but it should NOT be a
    // direct child of the container (it will be wrapped). On unfixed code the
    // raw <input> is a direct child of the flex wrapper div.
    const directInputChild = container.querySelector("div > input");
    expect(directInputChild).toBeNull();
  });

  it("1.6 sendChatMessage response for 'shoes' contains no emoji characters", async () => {
    const response = await sendChatMessage({ message: "shoes", conversationId: "test" });
    // Regex matches any emoji / Unicode pictograph
    const emojiRegex = /\p{Emoji_Presentation}|\p{Extended_Pictographic}/gu;
    expect(response.content).not.toMatch(emojiRegex);
  });
});
