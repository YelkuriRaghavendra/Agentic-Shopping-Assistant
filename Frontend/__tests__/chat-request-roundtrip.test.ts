// Feature: frontend-chat-integration, Property 15: ChatRequest round-trip serialisation

/**
 * Property 15: ChatRequest round-trip serialisation
 *
 * For any valid ChatRequest object, JSON.parse(JSON.stringify(req)) must
 * deep-equal the original. This confirms all fields are JSON-serialisable
 * and no data is lost through the serialisation boundary.
 *
 * Validates: Requirements 10.2
 */

import { describe, it, expect } from "vitest";
import * as fc from "fast-check";
import type { ChatRequest, Channel } from "@/types/chat.types";

// ---------------------------------------------------------------------------
// Arbitraries
// ---------------------------------------------------------------------------

const channelArb = fc.constantFrom<Channel>("web", "mobile", "whatsapp", "sdk");

const filtersArb = fc.option(
  fc.dictionary(
    fc.string({ minLength: 1, maxLength: 20 }),
    fc.oneof(fc.string(), fc.integer(), fc.boolean(), fc.constant(null))
  ),
  { nil: undefined }
);

const chatRequestArb: fc.Arbitrary<ChatRequest> = fc.record(
  {
    message: fc.string({ minLength: 0, maxLength: 500 }),
    customer_id: fc.option(fc.uuid(), { nil: undefined }),
    session_id: fc.option(fc.uuid(), { nil: undefined }),
    channel: fc.option(channelArb, { nil: undefined }),
    filters: filtersArb,
  },
  { requiredKeys: ["message"] }
);

// ---------------------------------------------------------------------------
// Property test
// ---------------------------------------------------------------------------

describe("Property 15: ChatRequest round-trip serialisation", () => {
  it("JSON.parse(JSON.stringify(req)) deep-equals the original for any ChatRequest", () => {
    fc.assert(
      fc.property(chatRequestArb, (req) => {
        const roundTripped = JSON.parse(JSON.stringify(req)) as ChatRequest;
        expect(roundTripped).toEqual(req);
      }),
      { numRuns: 100 }
    );
  });

  it("required field `message` survives round-trip for edge-case strings", () => {
    const edgeCases: string[] = [
      "",
      " ",
      "hello world",
      "unicode: 你好 🎉",
      'quotes: "double" and \'single\'',
      "newlines:\n\ttabs",
      "null byte: \u0000",
      "<script>alert(1)</script>",
    ];

    edgeCases.forEach((msg) => {
      const req: ChatRequest = { message: msg };
      const roundTripped = JSON.parse(JSON.stringify(req)) as ChatRequest;
      expect(roundTripped.message).toBe(msg);
    });
  });
});
