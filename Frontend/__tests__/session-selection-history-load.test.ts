// Feature: frontend-chat-integration, Property 13: Session selection triggers message history load

/**
 * Property 13: Session selection triggers message history load
 *
 * For any session ID, calling selectSession(id) on useSessions sets
 * activeSessionId, which useChat uses to fetch message history from
 * GET /api/v1/chat/sessions/{id}/messages.
 *
 * We test this end-to-end by rendering useChat with a changing sessionId
 * (simulating what happens when useSessions.selectSession is called and
 * the new activeSessionId is passed down to useChat).
 *
 * Validates: Requirements 6.3
 */

import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { renderHook, act } from "@testing-library/react";
import * as fc from "fast-check";
import { useChat } from "@/hooks/useChat";
import { useSessions } from "@/hooks/useSessions";
import { API_PREFIX } from "@/config/config";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function makeHistoryResponse() {
  return { messages: [], next_cursor: null, has_more: false };
}

function makeSessionsResponse(sessionId: string) {
  return [
    {
      session_id: sessionId,
      customer_id: "cust-1",
      channel: "web",
      status: "active" as const,
      message_count: 0,
      total_tokens: 0,
      started_at: new Date().toISOString(),
      ended_at: null,
    },
  ];
}

function setupFetchMock() {
  const capturedUrls: string[] = [];

  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string) => {
      capturedUrls.push(url);
      return {
        ok: true,
        json: async () => {
          // Return sessions list for customer sessions endpoint
          if (url.includes("/sessions") && !url.match(/\/sessions\/[^/]+\/messages/)) {
            return makeSessionsResponse("any-session");
          }
          return makeHistoryResponse();
        },
        text: async () => JSON.stringify(makeHistoryResponse()),
      } as unknown as Response;
    })
  );

  return { capturedUrls };
}

// ---------------------------------------------------------------------------
// Arbitraries
// ---------------------------------------------------------------------------

const uuidArb = fc.uuid();

// ---------------------------------------------------------------------------
// Property tests
// ---------------------------------------------------------------------------

describe("Property 13: Session selection triggers message history load", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it(
    "useChat fetches session messages URL containing the session ID when sessionId changes",
    async () => {
      await fc.assert(
        fc.asyncProperty(uuidArb, uuidArb, async (customerId, sessionId) => {
          const { capturedUrls } = setupFetchMock();

          const { rerender } = renderHook(
            ({ sid }: { sid: string | null }) => useChat(customerId, sid),
            { initialProps: { sid: null as string | null } }
          );

          // Simulate selectSession: pass the new sessionId as prop (mirrors page.tsx wiring)
          await act(async () => {
            rerender({ sid: sessionId });
            await new Promise((r) => setTimeout(r, 0));
          });

          const expectedPath = `${API_PREFIX}/chat/sessions/${sessionId}/messages`;
          const historyFetchUrl = capturedUrls.find((url) => url.includes(expectedPath));

          expect(historyFetchUrl).toBeDefined();
          expect(historyFetchUrl).toContain(sessionId);

          vi.restoreAllMocks();
        }),
        { numRuns: 100 }
      );
    }
  );

  it(
    "useSessions.selectSession sets activeSessionId to the selected session ID",
    async () => {
      await fc.assert(
        fc.asyncProperty(uuidArb, uuidArb, async (customerId, sessionId) => {
          setupFetchMock();

          const { result } = renderHook(() => useSessions(customerId));

          await act(async () => {
            await new Promise((r) => setTimeout(r, 0));
          });

          await act(async () => {
            result.current.selectSession(sessionId);
          });

          expect(result.current.activeSessionId).toBe(sessionId);

          vi.restoreAllMocks();
        }),
        { numRuns: 100 }
      );
    }
  );
});
