// Feature: frontend-chat-integration, Property 9: answer_html is rendered in MessageBubble

/**
 * Property 9: answer_html is rendered in MessageBubble
 *
 * For any answer_html string, MessageBubble renders the sanitized HTML via
 * dangerouslySetInnerHTML. The rendered innerHTML of the prose container must
 * equal sanitizeHtml(answer_html).
 *
 * **Validates: Requirements 5.2, 9.1**
 */

import React from "react";
import { render } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import * as fc from "fast-check";
import { MessageBubble } from "@/components/MessageBubble";
import { sanitizeHtml } from "@/lib/sanitize";
import type { ChatMessageUI } from "@/types/chat.types";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function makeBotMessage(answerHtml: string): ChatMessageUI {
  return {
    id: "msg-bot-1",
    role: "bot",
    content: "fallback content",
    answerHtml,
    timestamp: new Date("2024-01-01T00:00:00Z"),
    streamDone: true,
  };
}

// ---------------------------------------------------------------------------
// Arbitraries
// ---------------------------------------------------------------------------

// Generate a variety of HTML-like strings including plain text, tags, and mixed content.
// Only non-empty strings are generated because MessageBubble only renders the HTML path
// when answerHtml is truthy (non-empty). An empty string falls through to message.content.
const answerHtmlArb = fc.oneof(
  // Plain text strings (non-empty)
  fc.string({ minLength: 1, maxLength: 200 }),
  // Simple HTML tags that are in the allowed list
  fc.string({ minLength: 1, maxLength: 50 }).map((s) => `<p>${s}</p>`),
  fc.string({ minLength: 1, maxLength: 50 }).map((s) => `<b>${s}</b>`),
  fc.string({ minLength: 1, maxLength: 50 }).map((s) => `<em>${s}</em>`),
  // Potentially dangerous tags that should be stripped
  fc.string({ minLength: 1, maxLength: 50 }).map((s) => `<script>${s}</script>`),
  fc.string({ minLength: 1, maxLength: 50 }).map((s) => `<img src="x" onerror="${s}">`),
  // Nested allowed tags
  fc.string({ minLength: 1, maxLength: 30 }).map((s) => `<ul><li>${s}</li></ul>`),
);

// ---------------------------------------------------------------------------
// Property test
// ---------------------------------------------------------------------------

describe("Property 9: answer_html is rendered in MessageBubble", () => {
  it(
    "rendered innerHTML equals sanitizeHtml(answer_html) for any answer_html string",
    () => {
      fc.assert(
        fc.property(answerHtmlArb, (answerHtml) => {
          const message = makeBotMessage(answerHtml);
          const { container } = render(<MessageBubble message={message} />);

          // The prose div is the container for dangerouslySetInnerHTML
          const proseDiv = container.querySelector(".prose");
          expect(proseDiv).not.toBeNull();

          // To compare correctly, we must account for DOM serialization: the browser
          // encodes certain characters (e.g. "&" → "&amp;") when reading innerHTML.
          // We derive the expected value by setting sanitizeHtml's output into a
          // temporary element and reading its innerHTML — the same path the component takes.
          const tmp = document.createElement("div");
          tmp.innerHTML = sanitizeHtml(answerHtml);
          const expectedHtml = tmp.innerHTML;

          expect(proseDiv!.innerHTML).toBe(expectedHtml);
        }),
        { numRuns: 100 }
      );
    }
  );
});
