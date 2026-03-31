// Feature: frontend-chat-integration, Property 8: useChat sends correct fields to POST /chat

/**
 * Property 8: useChat sends correct fields to POST /chat
 *
 * For any non-empty message string, customer_id, and session_id, calling
 * sendMessage should result in a fetch call to POST /api/v1/chat/stream whose JSON
 * body contains exactly those three fields (message, customer_id, session_id).
 *
 * Validates: Requirements 5.1
 */

import React from "react";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { renderHook, act } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import * as fc from "fast-check";
import { useChat } from "@/hooks/useChat";
import { endpoints } from "@/config/config";

function createWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return function Wrapper({ children }: { children: React.ReactNode }) {
    return React.createElement(QueryClientProvider, { client: queryClient }, children);
  };
}

function makeHistoryResponse() {
  return { messages: [], next_cursor: null, has_more: false };
}

function makeStreamBody(sessionId: string): ReadableStream<Uint8Array> {
  const doneEvent =
    "data: " +
    JSON.stringify({
      type: "done",
      message_id: "00000000-0000-0000-0000-000000000001",
      session_id: sessionId,
      answer: "Test answer",
      answer_html: "<p>Test answer</p>",
      cited_products: [],
      suggestions: [],
    }) +
    "\n\n";
  const encoder = new TextEncoder();
  return new ReadableStream({
    start(controller) {
      controller.enqueue(encoder.encode(doneEvent));
      controller.close();
    },
  });
}

function setupFetchMock(sessionId: string): { getCapturedBody: () => unknown } {
  let capturedBody: unknown = null;

  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string, init?: RequestInit) => {
      const method = init?.method ?? "GET";

      if (method === "GET") {
        return {
          ok: true,
          json: async () => makeHistoryResponse(),
          text: async () => JSON.stringify(makeHistoryResponse()),
        } as unknown as Response;
      }

      capturedBody = JSON.parse(init?.body as string);

      return {
        ok: true,
        body: makeStreamBody(sessionId),
        json: async () => ({}),
        text: async () => "",
      } as unknown as Response;
    })
  );

  return { getCapturedBody: () => capturedBody };
}

const messageArb = fc
  .string({ minLength: 1, maxLength: 200 })
  .filter((s) => s.trim().length > 0);

const uuidArb = fc.uuid();

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

          const { result } = renderHook(() => useChat(customerId, sessionId), {
            wrapper: createWrapper(),
          });

          await act(async () => {
            await new Promise((r) => setTimeout(r, 0));
          });

          await act(async () => {
            result.current.sendMessage(message);
            await new Promise((r) => setTimeout(r, 20));
          });

          const body = getCapturedBody() as Record<string, unknown>;

          expect(body).toHaveProperty("message", message.trim());
          expect(body).toHaveProperty("customer_id", customerId);
          expect(body).toHaveProperty("session_id", sessionId);

          const fetchMock = vi.mocked(fetch);
          const postCall = fetchMock.mock.calls.find(
            ([, init]) => (init as RequestInit)?.method === "POST"
          );
          expect(postCall).toBeDefined();
          expect(postCall![0]).toBe(endpoints.chatStream);

          vi.restoreAllMocks();
        }),
        { numRuns: 20 }
      );
    },
    30000
  );
});
