// Feature: frontend-chat-integration, Property 12: SessionSidebar renders one entry per session

/**
 * Property 12: SessionSidebar renders one entry per session
 *
 * For any array of SessionResponse objects, SessionSidebar renders exactly
 * one clickable entry per session in the array.
 *
 * **Validates: Requirements 6.1**
 */

import React from "react";
import { render, cleanup } from "@testing-library/react";
import { describe, it, afterEach, expect } from "vitest";
import * as fc from "fast-check";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { SessionSidebar } from "@/components/SessionSidebar";
import type { SessionResponse } from "@/types/chat.types";

// ---------------------------------------------------------------------------
// Arbitraries
// ---------------------------------------------------------------------------

// Use integer timestamps to avoid fast-check generating invalid Date objects during shrinking
const MIN_TS = new Date("2020-01-01").getTime();
const MAX_TS = new Date("2030-01-01").getTime();

const isoDateArb: fc.Arbitrary<string> = fc
  .integer({ min: MIN_TS, max: MAX_TS })
  .map((ts) => new Date(ts).toISOString());

const sessionArb: fc.Arbitrary<SessionResponse> = fc.record({
  session_id: fc.uuid(),
  customer_id: fc.option(fc.uuid(), { nil: null }),
  channel: fc.constantFrom("web", "mobile", "whatsapp", "sdk"),
  status: fc.constantFrom("active", "ended"),
  message_count: fc.nat({ max: 500 }),
  total_tokens: fc.nat({ max: 100000 }),
  started_at: isoDateArb,
  ended_at: fc.option(isoDateArb, { nil: null }),
});

const sessionsArb: fc.Arbitrary<SessionResponse[]> = fc.array(sessionArb, {
  minLength: 0,
  maxLength: 50,
});

// ---------------------------------------------------------------------------
// Property test
// ---------------------------------------------------------------------------

describe("Property 12: SessionSidebar renders one entry per session", () => {
  afterEach(() => {
    cleanup();
  });

  it(
    "number of rendered session entries equals the sessions array length",
    () => {
      fc.assert(
        fc.property(sessionsArb, (sessions) => {
          const queryClient = new QueryClient();
          const { queryAllByTestId } = render(
            <QueryClientProvider client={queryClient}>
              <SessionSidebar
                sessions={sessions}
                activeSessionId={null}
                isLoading={false}
                onSelectSession={() => {}}
                onNewSession={() => {}}
              />
            </QueryClientProvider>
          );

          const entries = queryAllByTestId("session-entry");
          expect(entries).toHaveLength(sessions.length);

          cleanup();
        }),
        { numRuns: 100 }
      );
    }
  );
});
