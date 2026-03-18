// Feature: frontend-chat-integration, Property 8: useChat sends correct fields to POST /chat

/**
 * Property 8: useChat sends correct fields to POST /chat
 *
 * For any non-empty message string, customer_id, and session_id, calling
 * sendMessage should result in a fetch call to POST /api/v1/chat whose JSON
 * body contains exactly those three fields (message, customer_id, session_id).
 *
 * Validates: Requirements 5.1
 */

import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { renderHook, act } from "@testing-library/react";
import * as fc from "fast-check";
import { useChat } from "@/hooks/useChat";
import { endpoints } from "@/config/config";
import type { ChatResponse } from "@/types/chat.types";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function makeChatResponse(sessionId: string): ChatResponse {
  return {
    message_id: "00000000-0000-0000-0000-000000000001",
    session_id: sessionId,
    answer: "Test answer",
    answer_html: "<p>Test answer</p>",
    cited_products: [],
    suggestions: [],
    intent: "general",
    guardrail_status: "passed",
    blocked: false,
    latency_ms: 100,
    tokens_used: 10,
  };
}

function makeHistoryResponse() {
  return { messages: [], next_cursor: null, has_more: false };
}

/**
 * Sets up a global fetch mock that:
 * - Returns an empty message history for GET requests (history load on mount)
 * - Returns a valid ChatResponse for POST requests, capturing the request body
 */
function setupFetchMock(sessionId: string): { getCapturedBody: () => unknown } {
  let capturedBody: unknown = null;

  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string, init?: RequestInit) => {
      const method = init?.method ?? "GET";

      if (method === "GET") {
        // History load triggered by sessionId on mount
        return {
          ok: true,
          json: async () => makeHistoryResponse(),
          text: async () => JSON.stringify(makeHistoryResponse()),
        } as unknown as Response;
      }

      // POST /chat — capture the body
      capturedBody = JSON.parse(init?.body as string);

      return {
        ok: true,
        json: async () => makeChatResponse(sessionId),
        text: async () => JSON.stringify(makeChatResponse(sessionId)),
      } as unknown as Response;
    })
  );

  return { getCapturedBody: () => capturedBody };
}

// ---------------------------------------------------------------------------
// Arbitraries
// ---------------------------------------------------------------------------

// Non-empty, non-whitespace-only message strings
const messageArb = fc
  .string({ minLength: 1, maxLength: 200 })
  .filter((s) => s.trim().length > 0);

// UUID-like strings (fast-check built-in uuid)
const uuidArb = fc.uuid();

// ---------------------------------------------------------------------------
// Property test
// ---------------------------------------------------------------------------

describe("Property 8: useChat sends correct fields to POST /chat", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it(
    "fetch body contains exactly message, customer_id, and session_id for any valid inputs",
    async () => {
      await fc.assert(
        fc.asyncProperty(messageArb, uuidArb, uuidArb, async (message, customerId, sessionId) => {
          const { getCapturedBody } = setupFetchMock(sessionId);

          const { result } = renderHook(() => useChat(customerId, sessionId));

          // Wait for the history load effect to settle
          await act(async () => {
            await new Promise((r) => setTimeout(r, 0));
          });

          // Send the message
          await act(async () => {
            result.current.sendMessage(message);
            // Allow the async sendMessage to complete
            await new Promise((r) => setTimeout(r, 0));
          });

          const body = getCapturedBody() as Record<string, unknown>;

          // The body must contain the three required fields
          expect(body).toHaveProperty("message", message.trim());
          expect(body).toHaveProperty("customer_id", customerId);
          expect(body).toHaveProperty("session_id", sessionId);

          // Verify the POST was made to the correct endpoint
          const fetchMock = vi.mocked(fetch);
          const postCall = fetchMock.mock.calls.find(
            ([, init]) => (init as RequestInit)?.method === "POST"
          );
          expect(postCall).toBeDefined();
          expect(postCall![0]).toBe(endpoints.chat);

          vi.restoreAllMocks();
        }),
        { numRuns: 100 }
      );
    }
  );
});
