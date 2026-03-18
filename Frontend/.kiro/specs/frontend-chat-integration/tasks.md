# Implementation Plan: frontend-chat-integration

## Overview

Replace the mock-only Next.js chat frontend with a fully integrated implementation communicating with the FastAPI backend. Tasks are ordered so each step builds on the previous: types → config → HTTP client → hooks → components → composition → cleanup → tests.

## Tasks

- [x] 1. Install dependencies and define TypeScript types
  - [x] 1.1 Install `dompurify`, `@types/dompurify`, and `fast-check` dev dependency
    - Run `npm install dompurify` and `npm install -D @types/dompurify fast-check` inside `Frontend/`
    - Verify entries appear in `package.json`
    - _Requirements: 9.2 (DOMPurify), Testing Strategy (fast-check)_

  - [x] 1.2 Replace `types/chat.types.ts` with backend-aligned interfaces
    - Remove `ProductSuggestion`, `SendMessagePayload`, and the old `ChatResponse` / `ChatMessage` types
    - Add all types from the design: `MessageRole`, `Channel`, `GuardrailStatus`, `ChipType`, `ChatRequest`, `CustomerCreateRequest`, `SessionCreateRequest`, `FeedbackRequest`, `ProductCardDTO`, `SuggestionChip`, `ChatResponse`, `CustomerResponse`, `SessionResponse`, `MessageResponse`, `MessageHistoryResponse`, `ChatMessageUI`
    - _Requirements: 10.1_

  - [x] 1.3 Write property test for ChatRequest round-trip serialisation
    - **Property 15: ChatRequest round-trip serialisation**
    - Generate random `ChatRequest` objects with fast-check; assert `JSON.parse(JSON.stringify(req))` deep-equals original
    - Tag: `// Feature: frontend-chat-integration, Property 15: ChatRequest round-trip serialisation`
    - **Validates: Requirements 10.2**

  - [ ]* 1.4 Write property test for ChatResponse deserialisation robustness
    - **Property 16: ChatResponse deserialisation is robust**
    - Generate valid `ChatResponse` objects with extra unknown fields; assert parse succeeds and known fields are correct
    - Tag: `// Feature: frontend-chat-integration, Property 16: ChatResponse deserialisation is robust`
    - **Validates: Requirements 10.3, 10.4**

- [x] 2. Create config module
  - [x] 2.1 Create `config/config.ts` with `apiBaseUrl`, `API_PREFIX`, and `endpoints`
    - Read `NEXT_PUBLIC_API_BASE_URL` env var, default to `http://localhost:8000`
    - Export `API_PREFIX = "/api/v1"` constant
    - Export typed `endpoints` object covering: `chat`, `createCustomer`, `getCustomer(id)`, `customerSessions(id)`, `createSession`, `getSession(id)`, `endSession(id)`, `sessionMessages(id)`, `messageFeedback(id)`
    - _Requirements: 1.1, 1.2, 1.3, 1.4_

  - [ ]* 2.2 Write property test for endpoint URL composition
    - **Property 1: Endpoints always contain base URL and prefix**
    - Generate random valid base URL strings with fast-check; instantiate config with each; assert every value in `endpoints` starts with `baseUrl + "/api/v1"`
    - Tag: `// Feature: frontend-chat-integration, Property 1: Endpoints always contain base URL and prefix`
    - **Validates: Requirements 1.3**

- [x] 3. Implement real HTTP client
  - [x] 3.1 Replace `MockHttpClient` in `services/httpClient.ts` with `FetchHttpClient`
    - Implement `get<T>` using `fetch` with `GET` method; throw `HttpError` on non-2xx
    - Implement `post<T>` using `fetch` with `POST` method and `Content-Type: application/json` header; throw `HttpError` on non-2xx
    - Export `HttpError` class with `status: number` and `body: string` properties
    - Export singleton `httpClient: HttpClient`
    - _Requirements: 2.1, 2.2, 2.3, 2.4_

  - [ ]* 3.2 Write property test: HTTP client throws HttpError on non-2xx
    - **Property 2: HTTP client throws on non-2xx status**
    - Generate random status codes outside 200–299 with fast-check; mock `fetch`; assert `HttpError` thrown with correct `.status`
    - Tag: `// Feature: frontend-chat-integration, Property 2: HTTP client throws on non-2xx status`
    - **Validates: Requirements 2.2**

  - [ ]* 3.3 Write property test: POST requests include Content-Type header
    - **Property 3: HTTP client sets Content-Type on POST**
    - Generate random POST bodies with fast-check; mock `fetch`; assert `Content-Type: application/json` header is present in the captured request
    - Tag: `// Feature: frontend-chat-integration, Property 3: HTTP client sets Content-Type on POST`
    - **Validates: Requirements 2.3**

  - [ ]* 3.4 Write property test: JSON response round-trip
    - **Property 4: HTTP client deserialises JSON response**
    - Generate random JSON-serialisable objects with fast-check; mock `fetch` to return them; assert returned value deeply equals original
    - Tag: `// Feature: frontend-chat-integration, Property 4: HTTP client deserialises JSON response`
    - **Validates: Requirements 2.4**

- [x] 4. Implement `useCustomer` hook
  - [x] 4.1 Create `hooks/useCustomer.ts`
    - On mount: read `localStorage.getItem("customer_id")`; if present call `GET /api/v1/chat/customers/{id}`
    - On 200: store `CustomerResponse` in state, set `isLoading = false`
    - On 404: call `localStorage.removeItem("customer_id")`, treat as new visitor
    - Expose `createCustomer(name, email)`: call `POST /api/v1/chat/customers`; on success persist `id` to localStorage and store in state; on error set `error` string
    - Expose `dialogOpen`, `queueMessage`, `pendingMessage` for first-visit flow
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 4.1, 4.2, 4.3, 4.4_

  - [ ]* 4.2 Write property test: customer creation persists identity
    - **Property 5: Customer creation persists identity**
    - Generate random `CustomerResponse` objects with fast-check; simulate hook processing; assert `localStorage.getItem("customer_id")` equals `response.id` and state matches response
    - Tag: `// Feature: frontend-chat-integration, Property 5: Customer creation persists identity`
    - **Validates: Requirements 3.3, 3.4, 4.3**

  - [ ]* 4.3 Write property test: stale customer_id cleared on 404
    - **Property 6: Stale customer_id is cleared on 404**
    - Generate random UUID strings with fast-check; mock `GET /customers/{id}` to return 404; assert `localStorage.getItem("customer_id")` is null after hook processes response
    - Tag: `// Feature: frontend-chat-integration, Property 6: Stale customer_id is cleared on 404`
    - **Validates: Requirements 4.2**

  - [ ]* 4.4 Write property test: isLoading true while validation in-flight
    - **Property 7: Input disabled while customer validation is in-flight**
    - Mock a pending `GET /customers/{id}` request; assert `isLoading` is `true` before the promise resolves
    - Tag: `// Feature: frontend-chat-integration, Property 7: Input disabled while customer validation is in-flight`
    - **Validates: Requirements 4.4, 5.4**

- [x] 5. Implement `useChat` hook
  - [x] 5.1 Rewrite `hooks/useChat.ts` to accept `customerId` and `sessionId` parameters
    - Remove `CONVERSATION_ID`, `WELCOME_MESSAGE`, and all mock imports
    - `sendMessage(text)`: guard on `sessionEnded` and `isLoading`; append user `ChatMessageUI`; set `isTyping = true`; call `POST /api/v1/chat`; on success set `activeSessionId` and append bot `ChatMessageUI` with `answerHtml`; on error append bot error message; always clear `isTyping`
    - When `sessionId` prop changes, load history via `GET /api/v1/chat/sessions/{id}/messages` and replace `messages`
    - Expose `messages`, `sendMessage`, `isLoading`, `isTyping`, `sessionEnded`, `activeSessionId`, `error`, `bottomRef`
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 5.6, 6.3_

  - [x] 5.2 Write property test: sendMessage sends correct fields to POST /chat
    - **Property 8: useChat sends correct fields to POST /chat**
    - Generate random message strings, customer IDs, and session IDs with fast-check; assert fetch body contains exactly those three fields
    - Tag: `// Feature: frontend-chat-integration, Property 8: useChat sends correct fields to POST /chat`
    - **Validates: Requirements 5.1**

  - [ ]* 5.3 Write property test: session_id updated from response
    - **Property 10: session_id is updated from response**
    - Generate random `ChatResponse` objects with fast-check; assert `activeSessionId` in state equals `response.session_id` after processing
    - Tag: `// Feature: frontend-chat-integration, Property 10: session_id is updated from response`
    - **Validates: Requirements 5.3**

  - [ ]* 5.4 Write property test: ended session blocks sendMessage
    - **Property 11: Ended session blocks input and POST**
    - Generate sessions with `status === "ended"` with fast-check; assert `sendMessage` does not call `fetch`
    - Tag: `// Feature: frontend-chat-integration, Property 11: Ended session blocks input and POST`
    - **Validates: Requirements 5.6, 6.4, 6.5**

- [ ] 6. Implement `useSessions` hook
  - [x] 6.1 Create `hooks/useSessions.ts`
    - Accept `customerId: string | null`; when non-null call `GET /api/v1/chat/customers/{id}/sessions`
    - Expose `sessions`, `activeSessionId`, `isLoading`, `selectSession(id)`
    - `selectSession(id)` sets `activeSessionId` which triggers `useChat` to load history
    - _Requirements: 6.1, 6.2, 6.3, 6.6_

  - [x] 6.2 Write property test: session selection triggers history load
    - **Property 13: Session selection triggers message history load**
    - Generate random session IDs with fast-check; call `selectSession(id)`; assert fetch was called with URL containing that session ID
    - Tag: `// Feature: frontend-chat-integration, Property 13: Session selection triggers message history load`
    - **Validates: Requirements 6.3**

- [x] 7. Checkpoint — core logic complete
  - Ensure all non-optional tests pass; verify `useCustomer`, `useChat`, and `useSessions` compile without errors
  - Ask the user if questions arise before proceeding to components

- [x] 8. Create `lib/sanitize.ts` and `MessageBubble` component
  - [x] 8.1 Create `lib/sanitize.ts` with `sanitizeHtml` using DOMPurify
    - Allow tags: `a`, `b`, `strong`, `em`, `i`, `ul`, `ol`, `li`, `p`, `br`, `span`, `div`
    - Allow attributes: `href`, `target`, `rel`, `class`
    - Set `FORCE_BODY: true`
    - _Requirements: 9.2_

  - [ ]* 8.2 Write property test: XSS payloads stripped from answer_html
    - **Property 14: XSS payloads are stripped from answer_html**
    - Generate strings containing `<script>` tags, `onerror` attributes, and `javascript:` href values with fast-check; assert `sanitizeHtml` output contains none of those patterns
    - Tag: `// Feature: frontend-chat-integration, Property 14: XSS payloads are stripped from answer_html`
    - **Validates: Requirements 9.2**

  - [x] 8.3 Create `components/MessageBubble.tsx`
    - Accept `message: ChatMessageUI` prop
    - If `message.answerHtml` is non-empty: sanitise with `sanitizeHtml` and render via `dangerouslySetInnerHTML` with `prose prose-invert prose-sm` Tailwind classes
    - Otherwise: render `message.content` as plain text
    - Preserve avatar, bubble styling, and timestamp from existing `ChatMessage.tsx`
    - _Requirements: 8.7, 9.1, 9.3, 9.4_

  - [x] 8.4 Write property test: answer_html rendered in MessageBubble
    - **Property 9: answer_html is rendered in MessageBubble**
    - Generate random `answer_html` strings with fast-check; render `MessageBubble`; assert rendered `innerHTML` equals `sanitizeHtml(answer_html)`
    - Tag: `// Feature: frontend-chat-integration, Property 9: answer_html is rendered in MessageBubble`
    - **Validates: Requirements 5.2, 9.1**

- [x] 9. Create `SessionSidebar` component
  - [x] 9.1 Create `components/SessionSidebar.tsx`
    - Accept `SessionSidebarProps`: `sessions`, `activeSessionId`, `isLoading`, `onSelectSession`
    - When `isLoading`: render skeleton placeholders (3 animated pulse divs)
    - When not loading: render one entry per `SessionResponse` showing `started_at` date and `status` badge
    - Highlight the active session; call `onSelectSession(session.id)` on click
    - _Requirements: 6.2, 6.6, 8.5_

  - [x] 9.2 Write property test: SessionSidebar renders one entry per session
    - **Property 12: SessionSidebar renders one entry per session**
    - Generate arrays of 0–50 `SessionResponse` objects with fast-check; render `SessionSidebar`; assert rendered entry count equals array length
    - Tag: `// Feature: frontend-chat-integration, Property 12: SessionSidebar renders one entry per session`
    - **Validates: Requirements 6.2**

- [x] 10. Create `UserDialog` component
  - [x] 10.1 Create `components/UserDialog.tsx`
    - Accept `UserDialogProps`: `open`, `onSubmit(name, email): Promise<void>`, `error: string | null`
    - Render a modal overlay (conditionally shown when `open` is true) with name and email inputs
    - On submit: call `onSubmit(name, email)`; show inline error if `error` is non-null
    - Disable submit button while submission is in-flight
    - _Requirements: 3.1, 3.5, 8.6_

- [x] 11. Update `ChatWindow` component
  - [x] 11.1 Refactor `components/ChatWindow.tsx` to accept all state via props
    - Remove the internal `useChat()` call
    - Accept `ChatWindowProps`: `messages`, `sendMessage`, `isLoading`, `isTyping`, `inputDisabled`, `sessionEnded`, `bottomRef`
    - Replace `<ChatMessage>` with `<MessageBubble>`
    - Pass `disabled={inputDisabled || sessionEnded}` to `ChatInput`
    - _Requirements: 8.4_

- [x] 12. Update `ChatInput` for session-ended state
  - [x] 12.1 Update `components/ChatInput.tsx` disabled placeholder text
    - When `disabled` is true and session has ended: show placeholder `"This session has ended"`
    - Accept optional `sessionEnded?: boolean` prop to distinguish the two disabled states
    - _Requirements: 6.4_

- [x] 13. Compose `app/chat/page.tsx`
  - [x] 13.1 Rewrite `app/chat/page.tsx` to wire all hooks and components
    - Add `"use client"` directive
    - Call `useCustomer()`, `useSessions(customer.customerId)`, `useChat(customer.customerId, sessions.activeSessionId)`
    - Render `<SessionSidebar>`, `<ChatWindow>`, and `<UserDialog>` with correct props
    - Pass `inputDisabled={customer.isLoading}` to `ChatWindow`
    - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.5, 8.6_

- [x] 14. Remove all mock data
  - [x] 14.1 Delete or empty `services/chatService.ts` mock logic
    - Remove `MOCK_PRODUCTS`, `MOCK_TEMPLATES`, `FALLBACK_RESPONSES`, `detectCategory`, and `sendChatMessage` mock implementation
    - Remove `randomDelay` and `generateId` imports from `lib/utils.ts` if no longer used elsewhere
    - _Requirements: 7.1, 7.2_

  - [x] 14.2 Remove `ProductSuggestion` type and product card rendering
    - Confirm `ProductSuggestion` is no longer referenced after step 1.2
    - Remove product card JSX from `ChatMessage.tsx` (or delete the file if fully replaced by `MessageBubble`)
    - _Requirements: 7.4_

  - [x] 14.3 Confirm `MockHttpClient` is gone
    - Verify `services/httpClient.ts` exports only `FetchHttpClient`, `HttpError`, and `httpClient`
    - _Requirements: 7.3_

- [x] 15. Final checkpoint — integration complete
  - Ensure all non-optional tests pass and the app compiles with `tsc --noEmit`
  - Ask the user if questions arise before marking complete

- [x] 16. Sidebar — "New Session" button and colour polish
  - [x] 16.1 Add "New Session" button at the top of `SessionSidebar`
    - Add `onNewSession: () => void` to `SessionSidebarProps`
    - Render a full-width button at the very top of the sidebar (above the session list) using the shadcn `Button` component with `variant="outline"` and a `Plus` icon from `lucide-react`
    - Button label: "New Session"
    - Clicking it calls `onNewSession()`; the button must be visible even when `isLoading` is true
    - Remove any existing "New Session" UI from `ChatWindow` or `page.tsx` if present
    - _Requirement: sidebar is the single entry point for starting a new session_

  - [x] 16.2 Fix sidebar colour scheme
    - Replace all raw HSL CSS-variable references (`hsl(var(--card))`, `hsl(var(--muted))`, etc.) with concrete Tailwind dark-mode colours that match the rest of the app's dark violet/indigo palette
    - Sidebar background: `bg-gray-900`
    - Session entry default: `bg-gray-800 hover:bg-gray-700 text-gray-100`
    - Active session: `bg-violet-600 text-white`
    - Status badge active: `bg-emerald-500/20 text-emerald-400`
    - Status badge ended/other: `bg-gray-600/40 text-gray-400`
    - Skeleton pulse: `bg-gray-700`
    - Sidebar header border and text: `border-gray-700`, `text-gray-400`
    - _Requirement: sidebar colours must be consistent with the dark violet/indigo app theme_

  - [x] 16.3 Wire `onNewSession` in `useSessions` and `page.tsx`
    - Add `createSession(customerId): Promise<void>` to `useSessions` — calls `POST /api/v1/chat/sessions` with `{ customer_id, channel: "web" }`, prepends the returned `SessionResponse` to `sessions`, and sets it as `activeSessionId`
    - Expose `createSession` from `UseSessionsReturn`
    - In `page.tsx` pass `onNewSession={() => sessions.createSession(customer.customerId)}` to `<SessionSidebar>`

- [x] 17. Slash-command support: `/start` and `/end`
  - [x] 17.1 Detect `/start` and `/end` commands in `useChat.sendMessage`
    - Before the normal POST-to-chat flow, check if `trimmed === "/start"` or `trimmed === "/end"` (case-insensitive)
    - `/start`: call `POST /api/v1/chat/sessions` with `{ customer_id, channel: "web" }`; on success set `activeSessionId` to the new session's `id`, clear `messages`, set `sessionEnded = false`; append a system info bubble `"New session started."`; do NOT post to `/chat`
    - `/end`: call `POST /api/v1/chat/sessions/{activeSessionId}/end`; on success set `sessionEnded = true`; append a system info bubble `"Session ended."`; do NOT post to `/chat`
    - On error for either command append a bot error bubble with the failure reason
    - _Requirement: slash commands must work even when `sessionEnded` is true for `/start`_

  - [x] 17.2 Update `ChatInput` placeholder and hint for slash commands
    - When the input value starts with `/` show placeholder hint text `"Commands: /start · /end"` instead of the default placeholder
    - No other changes to `ChatInput` styling or behaviour

- [x] 18. Message history display
  - [x] 18.1 Ensure `useChat` loads history on `sessionId` change (verify & harden)
    - Confirm the existing `useEffect` in `useChat` that calls `GET /api/v1/chat/sessions/{id}/messages` fires whenever `sessionId` changes (already implemented in task 5.1 — this task is a hardening pass)
    - Map `role === "assistant"` → `"bot"` and preserve `answer_html` from `cited_products` if present in the history response
    - Show a loading skeleton (3 pulse rows) in `ChatWindow` while history is being fetched; expose `isHistoryLoading` from `useChat` and pass it as a prop to `ChatWindow`
    - _Requirement: switching sessions must immediately replace the message list with the selected session's history_

  - [x] 18.2 Build `HistorySkeleton` sub-component inside `ChatWindow`
    - Render 3 animated `div` placeholders (`animate-pulse bg-gray-700 rounded-xl`) of alternating widths to mimic user/bot bubbles while history loads
    - Shown only when `isHistoryLoading` is true; hidden once messages are available

- [x] 19. Fix `ProductCardDTO` type to match actual backend response shape
  - [x] 19.1 Update `types/chat.types.ts` — `ProductCardDTO` fields
    - Replace `citation_id`, `title`, `url`, `currency`, `image_url`, `sku`, `in_stock`, `similarity` with the actual backend fields: `productId`, `productName`, `price`, `rating`, `productImageUrl`
    - Add `citedProducts?: ProductCardDTO[]` to `ChatMessageUI`
    - _Aligns with `ProductCardDTO` in `backend/app/api/dto/chat_dto.py`_

  - [x] 19.2 Update `useChat` to map `cited_products` and `suggestions` onto `ChatMessageUI`
    - When processing a `ChatResponse`, set `citedProducts: response.cited_products` and `suggestions: response.suggestions` on the bot `ChatMessageUI` appended to `messages`
    - Expose `sendProductMessage(productId: string, productName: string)` from `useChat`:
      - Appends a user bubble with `content: productName` to `messages` (display text only)
      - Calls `POST /api/v1/chat` with `message: productId` (the raw ID is what the API receives)
      - Response handling is identical to `sendMessage`
    - _Requirements: cited_products and suggestions must be preserved on the message object for rendering_

- [x] 20. Create `ProductSlider` component
  - [x] 20.1 Create `components/ProductSlider.tsx` using shadcn Card
    - Install shadcn card component if not present: `npx shadcn@latest add card`
    - Render a horizontally scrollable container (`overflow-x-auto`, `scroll-snap-type-x mandatory`, `flex gap-3`) of product cards
    - Each card (`scroll-snap-align-start`, fixed width ~200px) shows:
      - Product image (`productImageUrl`) with `<img>` and a grey placeholder div as fallback
      - `productName` truncated to 2 lines (`line-clamp-2`)
      - Price formatted as `₹{price}` (or "N/A" if null)
      - Star rating display (filled/empty stars based on `rating`)
      - "Preview" button (`variant="outline"` shadcn Button, opens `#` for now — no URL in DTO)
    - Single-select: clicking a card toggles its selected state (highlighted border `ring-2 ring-violet-500`)
    - A "Send" button appears at the bottom-right of the slider when a card is selected; clicking it calls `onSelectProduct(product.productId, product.productName)` and clears selection
    - Props: `{ products: ProductCardDTO[]; onSelectProduct: (productId: string, productName: string) => void }`
    - _Design: ProductSlider section_

  - [x] 20.2 Integrate `ProductSlider` into `MessageBubble`
    - After the `answer_html` / plain text content, conditionally render `<ProductSlider>` when `message.citedProducts` is non-empty
    - Pass `onSelectProduct` down from `ChatWindow` → `MessageBubble` → `ProductSlider`
    - `ChatWindow` receives `sendProductMessage` from `useChat` and passes it as `onSelectProduct`
    - Update `ChatWindowProps` to include `sendProductMessage: (productId: string, productName: string) => void`
    - Update `MessageBubbleProps` to include `onSelectProduct?: (productId: string, productName: string) => void`

- [x] 21. Create `SuggestionChips` component
  - [x] 21.1 Create `components/SuggestionChips.tsx`
    - Render a wrapping flex row of pill buttons for each `SuggestionChip`
    - Each pill shows `{chip.icon} {chip.label}` using a shadcn `Button` with `variant="outline"` and `size="sm"`, rounded-full styling
    - Clicking a chip calls `onSelectSuggestion(chip.message)` and hides the entire chip row (one-shot: set local `dismissed` state to true)
    - Props: `{ suggestions: SuggestionChip[]; onSelectSuggestion: (message: string) => void }`
    - _Design: SuggestionChips section_

  - [x] 21.2 Integrate `SuggestionChips` into `MessageBubble`
    - After the `ProductSlider` (or directly after the text content if no products), conditionally render `<SuggestionChips>` when `message.suggestions` is non-empty
    - Pass `onSelectSuggestion` down from `ChatWindow` → `MessageBubble` → `SuggestionChips`
    - `ChatWindow` passes `sendMessage` as `onSelectSuggestion` (suggestion `message` field is sent as-is to the API and shown as the user bubble)
    - Update `MessageBubbleProps` to include `onSelectSuggestion?: (message: string) => void`

## Notes

- Tasks marked with `*` are optional and can be skipped for a faster MVP
- Property tests use fast-check with a minimum of 100 iterations (the default)
- Each property test file should be placed in `Frontend/__tests__/` alongside existing tests
- DOMPurify runs in the browser; for SSR/test environments use `isomorphic-dompurify` or mock the module in Vitest setup
- `useChat` receives `sessionId` from `useSessions.activeSessionId`; the two hooks are coordinated in `page.tsx`
- The `httpMethods.ts` file requires no changes — it already delegates to `httpClient`
- All new components must use shadcn `Button` / `Input` primitives and `lucide-react` icons
- Slash commands (`/start`, `/end`) are intercepted before the normal chat POST — they never reach the LLM
- `ProductSlider` sends `productId` to the API but shows `productName` as the user bubble — these two values must never be swapped
- `SuggestionChips` are one-shot per bot response — they disappear after any chip is tapped or a new message is sent
