# Requirements Document

## Introduction

This feature integrates the existing Next.js frontend chat UI with the Python FastAPI backend. The current frontend uses entirely mock/static data. The goal is to replace all mock logic with real API calls, introduce customer identity management via localStorage, add session history browsing via a sidebar, and deliver a clean, modular codebase using custom hooks and reusable components.

The backend exposes a REST API under `/api/v1/chat` that handles customer creation, session management, and AI-powered chat responses (including `answer_html` for rich formatted output). The frontend must communicate with these endpoints seamlessly.

---

## Glossary

- **Chat_App**: The Next.js frontend application.
- **API**: The Python FastAPI backend located in the `backend/` folder.
- **Customer**: A user identity tracked by the backend, identified by a UUID (`customer_id`).
- **Session**: A conversation session tracked by the backend, identified by a UUID (`session_id`). A session has a `status` of either `active` or `ended`.
- **LocalStorage**: The browser's `localStorage` API used to persist `customer_id` between page loads.
- **UserDialog**: A modal dialog component that collects the user's name and email on first visit.
- **SessionSidebar**: A sidebar component that lists the customer's past and current chat sessions.
- **ChatWindow**: The main chat interface component displaying messages for the active session.
- **MessageBubble**: A component that renders a single chat message, supporting HTML content via `answer_html`.
- **ChatInput**: The text input component for composing and sending messages.
- **useCustomer**: A custom React hook managing customer identity state and API interactions.
- **useChat**: A custom React hook managing message state and the send-message API interaction.
- **useSessions**: A custom React hook managing session list state and API interactions.
- **Config**: The `config.ts` module that centralises all API endpoint URLs and environment variables.
- **answer_html**: The HTML-formatted string field in the `ChatResponse` DTO returned by `POST /api/v1/chat`.

---

## Requirements

### Requirement 1: Configuration Management

**User Story:** As a developer, I want all API endpoints and environment variables centralised in a single config module, so that changing the backend URL requires editing only one file.

#### Acceptance Criteria

1. THE Config SHALL export an `apiBaseUrl` value read from the `NEXT_PUBLIC_API_BASE_URL` environment variable, defaulting to `http://localhost:8000`.
2. THE Config SHALL export a constant `API_PREFIX` with the value `/api/v1`.
3. THE Config SHALL export a typed `endpoints` object that composes `apiBaseUrl` and `API_PREFIX` to produce fully-qualified URLs for every backend route used by the Chat_App.
4. WHEN the `NEXT_PUBLIC_API_BASE_URL` environment variable is absent, THE Config SHALL use `http://localhost:8000` as the base URL without throwing an error.

---

### Requirement 2: Real HTTP Client

**User Story:** As a developer, I want the HTTP client to make real `fetch` calls to the backend, so that the Chat_App communicates with live data instead of mock responses.

#### Acceptance Criteria

1. THE HTTP_Client SHALL implement `get<T>` and `post<T>` methods that call the browser `fetch` API with the correct method, headers, and body.
2. WHEN a response has an HTTP status outside the 200–299 range, THE HTTP_Client SHALL throw an error containing the HTTP status code and response body.
3. THE HTTP_Client SHALL set the `Content-Type: application/json` header on all `POST` requests.
4. THE HTTP_Client SHALL deserialise the response body as JSON and return it as the typed result.

---

### Requirement 3: Customer Identity — First Visit

**User Story:** As a new visitor, I want the Chat_App to create a guest customer record for me automatically, so that my conversation history is persisted across page reloads.

#### Acceptance Criteria

1. WHEN a user sends their first message and `localStorage` does not contain a `customer_id`, THE Chat_App SHALL display the UserDialog to collect the user's name and email before sending the message.
2. WHEN the user submits the UserDialog, THE useCustomer hook SHALL call `POST /api/v1/chat/customers` with the provided name and email.
3. WHEN `POST /api/v1/chat/customers` returns a `CustomerResponse`, THE useCustomer hook SHALL persist the returned `id` as `customer_id` in `localStorage`.
4. WHEN `POST /api/v1/chat/customers` returns a `CustomerResponse`, THE useCustomer hook SHALL store the customer record in component state so downstream hooks can access it without re-fetching.
5. IF `POST /api/v1/chat/customers` returns an error, THEN THE Chat_App SHALL display an inline error message inside the UserDialog and allow the user to retry.

---

### Requirement 4: Customer Identity — Returning Visit

**User Story:** As a returning visitor, I want the Chat_App to validate my stored customer identity on load, so that I can resume my conversation history without re-entering my details.

#### Acceptance Criteria

1. WHEN the Chat_App mounts and `localStorage` contains a `customer_id`, THE useCustomer hook SHALL call `GET /api/v1/chat/customers/{customer_id}` to validate the stored identity.
2. WHEN `GET /api/v1/chat/customers/{customer_id}` returns a 404 status, THE useCustomer hook SHALL remove `customer_id` from `localStorage` and treat the user as a new visitor.
3. WHEN `GET /api/v1/chat/customers/{customer_id}` returns a valid `CustomerResponse`, THE useCustomer hook SHALL store the customer record in state and proceed without showing the UserDialog.
4. WHILE the customer validation request is in-flight, THE Chat_App SHALL disable the ChatInput to prevent premature message submission.

---

### Requirement 5: Send Message

**User Story:** As a customer, I want to send a chat message and receive a formatted AI response, so that I can get product recommendations and assistance.

#### Acceptance Criteria

1. WHEN the user submits a message, THE useChat hook SHALL call `POST /api/v1/chat` with the `message`, `customer_id`, and `session_id` fields.
2. WHEN `POST /api/v1/chat` returns a `ChatResponse`, THE useChat hook SHALL render the `answer_html` field inside the MessageBubble using `dangerouslySetInnerHTML` (sanitised).
3. WHEN `POST /api/v1/chat` returns a `ChatResponse`, THE useChat hook SHALL update the active `session_id` in state with the `session_id` from the response.
4. WHILE a message request is in-flight, THE ChatInput SHALL be disabled and display a typing indicator.
5. IF `POST /api/v1/chat` returns an error, THEN THE useChat hook SHALL display an error message in the chat as a bot message without crashing the Chat_App.
6. WHEN the active session has a `status` of `ended`, THE ChatInput SHALL be disabled and THE useChat hook SHALL not call `POST /api/v1/chat`.

---

### Requirement 6: Session History Sidebar

**User Story:** As a returning customer, I want to see my past chat sessions in a sidebar, so that I can review previous conversations.

#### Acceptance Criteria

1. WHEN a valid `customer_id` is available, THE useSessions hook SHALL call `GET /api/v1/chat/customers/{customerId}/sessions` to fetch the session list.
2. THE SessionSidebar SHALL render one entry per session returned by the API, displaying the session start date and status.
3. WHEN the user clicks a session entry in the SessionSidebar, THE Chat_App SHALL load the messages for that session by calling `GET /api/v1/chat/sessions/{session_id}/messages`.
4. WHEN a selected session has a `status` of `ended`, THE ChatInput SHALL be disabled with a placeholder text indicating the session has ended.
5. WHEN a selected session has a `status` of `ended`, THE useChat hook SHALL not submit any message to `POST /api/v1/chat`.
6. WHILE the session list is loading, THE SessionSidebar SHALL display a loading skeleton in place of session entries.

---

### Requirement 7: Remove All Mock Data

**User Story:** As a developer, I want all static and mock data removed from the codebase, so that the Chat_App only operates on real backend data.

#### Acceptance Criteria

1. THE Chat_App SHALL contain no mock product catalogs, mock response templates, or hardcoded fallback response strings in production code.
2. THE chatService SHALL not contain any `randomDelay`, `generateId`-based mock response logic after the integration is complete.
3. THE httpClient SHALL not contain any `MockHttpClient` implementation after the integration is complete.
4. THE Chat_App SHALL remove the `ProductSuggestion` type and all product card rendering logic, as product data is now embedded in `answer_html` returned by the API.

---

### Requirement 8: Component Architecture

**User Story:** As a developer, I want a clean, modular component structure with custom hooks, so that the codebase is maintainable and each concern is isolated.

#### Acceptance Criteria

1. THE Chat_App SHALL expose a `useCustomer` hook that encapsulates all customer identity logic (localStorage read/write, API calls, state).
2. THE Chat_App SHALL expose a `useChat` hook that encapsulates all message sending logic (API call, message list state, typing indicator state).
3. THE Chat_App SHALL expose a `useSessions` hook that encapsulates all session list fetching and selection logic.
4. THE Chat_App SHALL provide a `ChatWindow` component that composes `MessageBubble`, `ChatInput`, and `TypingIndicator` without containing API call logic directly.
5. THE Chat_App SHALL provide a `SessionSidebar` component that renders the session list and delegates click events to the `useSessions` hook.
6. THE Chat_App SHALL provide a `UserDialog` component that renders the name/email form and delegates submission to the `useCustomer` hook.
7. THE Chat_App SHALL provide a `MessageBubble` component that accepts an `answer_html` string prop and renders it safely.

---

### Requirement 9: HTML Response Rendering

**User Story:** As a customer, I want bot responses to render rich formatted content (links, product chips, bold text), so that the chat feels interactive and informative.

#### Acceptance Criteria

1. WHEN the `answer_html` field is present in a `ChatResponse`, THE MessageBubble SHALL render it as HTML using a sanitised inner HTML approach.
2. THE MessageBubble SHALL sanitise `answer_html` before rendering to prevent cross-site scripting (XSS) attacks.
3. WHEN the `answer_html` field is absent or empty, THE MessageBubble SHALL fall back to rendering the plain `answer` text field.
4. THE MessageBubble SHALL apply Tailwind CSS prose styles to the rendered HTML so that links, lists, and headings are visually consistent with the chat theme.

---

### Requirement 10: Parser / Serialiser Round-Trip (API Contract)

**User Story:** As a developer, I want the TypeScript API types to accurately reflect the backend DTOs, so that serialisation and deserialisation are reliable.

#### Acceptance Criteria

1. THE Chat_App SHALL define TypeScript interfaces for `ChatRequest`, `ChatResponse`, `CustomerCreateRequest`, `CustomerResponse`, `SessionResponse`, and `MessageResponse` that match the backend Pydantic DTOs field-for-field.
2. FOR ALL valid `ChatRequest` objects, serialising to JSON and deserialising back SHALL produce an equivalent object (round-trip property).
3. FOR ALL valid `ChatResponse` objects received from the API, deserialising the JSON body SHALL produce a typed `ChatResponse` without runtime errors.
4. WHEN the API returns a field not present in the TypeScript interface, THE Chat_App SHALL not throw a runtime error (unknown fields are ignored).
