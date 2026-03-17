# Implementation Plan

- [x] 1. Write bug condition exploration test
  - **Property 1: Bug Condition** - No Emoji Icons or Raw Form Elements in UI
  - **CRITICAL**: This test MUST FAIL on unfixed code - failure confirms the bug exists
  - **DO NOT attempt to fix the test or the code when it fails**
  - **NOTE**: This test encodes the expected behavior - it will validate the fix when it passes after implementation
  - **GOAL**: Surface counterexamples that demonstrate emoji are present in rendered output
  - **Scoped PBT Approach**: Scope the property to the concrete failing cases for each affected component
  - Write tests that render `ChatMessage` (bot role) and assert the rendered output does NOT contain `🤖`
  - Write tests that render `ChatMessage` (user role) and assert the rendered output does NOT contain `🧑`
  - Write tests that render `ChatMessage` with products and assert the rendered output does NOT contain `🛍️`
  - Write tests that render `TypingIndicator` and assert the rendered output does NOT contain `🤖`
  - Write tests that render `ChatInput` and assert no raw `<input>` element exists (only shadcn/ui-wrapped)
  - Write tests that call `sendChatMessage({ message: "shoes", conversationId: "test" })` and assert the response `content` contains no emoji characters
  - Run all tests on UNFIXED code
  - **EXPECTED OUTCOME**: Tests FAIL (this is correct - it proves the bug exists)
  - Document counterexamples found (e.g., "ChatMessage bot avatar renders 🤖 instead of Bot icon")
  - Mark task complete when tests are written, run, and failures are documented
  - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7, 1.8, 1.9_

- [x] 2. Write preservation property tests (BEFORE implementing fix)
  - **Property 2: Preservation** - Chat Functionality Unchanged
  - **IMPORTANT**: Follow observation-first methodology
  - Observe: `ChatMessage` with a user message renders the correct violet bubble on unfixed code
  - Observe: `ChatMessage` with products renders product name, price, star rating, and badge on unfixed code
  - Observe: `ChatInput` calls `onSend` when Enter is pressed on unfixed code
  - Observe: `ChatInput` calls `onSend` when send button is clicked on unfixed code
  - Observe: `ChatInput` does NOT call `onSend` when `disabled=true` on unfixed code
  - Observe: `TypingIndicator` renders three animated dot spans on unfixed code
  - Write property-based tests: for any `ChatMessage` with role="user", the bubble has the user gradient class
  - Write property-based tests: for any `ChatMessage` with products array of length N, N product cards render
  - Write property-based tests: for any non-empty input value, Enter key triggers `onSend` exactly once
  - Verify all preservation tests PASS on UNFIXED code
  - **EXPECTED OUTCOME**: Tests PASS (this confirms baseline behavior to preserve)
  - Mark task complete when tests are written, run, and passing on unfixed code
  - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7, 3.8_

- [x] 3. Fix emoji icons and raw form elements

  - [x] 3.1 Fix ChatMessage component
    - Import `Bot`, `User`, and `ShoppingBag` from `lucide-react` (alongside existing `Star`)
    - Replace `{isUser ? "🧑" : "🤖"}` with `{isUser ? <User className="h-4 w-4 text-white" /> : <Bot className="h-4 w-4 text-white" />}`
    - Replace the `text-3xl` product placeholder div containing `🛍️` with `<ShoppingBag className="h-8 w-8 text-white/40" />`
    - _Bug_Condition: isBugCondition(element) where element is an emoji avatar or placeholder in ChatMessage_
    - _Expected_Behavior: Lucide icons Bot, User, ShoppingBag render in place of emoji characters_
    - _Preservation: Bubble styles, product card layout, Star rating icon, Framer Motion animations unchanged_
    - _Requirements: 2.1, 2.2, 2.3, 3.1, 3.2, 3.3_

  - [x] 3.2 Fix TypingIndicator component
    - Import `Bot` from `lucide-react`
    - Replace `🤖` avatar content with `<Bot className="h-4 w-4 text-white" />`
    - _Bug_Condition: isBugCondition(element) where element is the 🤖 emoji in TypingIndicator_
    - _Expected_Behavior: Bot Lucide icon renders in the avatar circle_
    - _Preservation: Three-dot bounce animation and bubble styling unchanged_
    - _Requirements: 2.4, 3.6_

  - [x] 3.3 Fix ChatInput component
    - Import `Input` from `@/components/ui/input` and `Button` from `@/components/ui/button`
    - Replace the raw `<input>` element with shadcn/ui `<Input>`, preserving all props: `value`, `onChange`, `onKeyDown`, `disabled`, `placeholder`, `aria-label`, and existing className styles
    - Replace `motion.button` with a `<Button>` component wrapped in a `<motion.div>` (or use `Button asChild` with `motion.button` as child), preserving `whileHover`, `whileTap`, `disabled` logic, and the `SendHorizonal` icon
    - _Bug_Condition: isBugCondition(element) where element is a raw <input> or <button> in ChatInput_
    - _Expected_Behavior: shadcn/ui Input and Button components render instead of raw HTML elements_
    - _Preservation: Enter-key send, button-click send, disabled state, SendHorizonal icon, animations unchanged_
    - _Requirements: 2.5, 2.6, 3.4, 3.5, 3.7_

  - [x] 3.4 Fix chatService response strings
    - Remove `👟` from the shoes template response string
    - Remove `🎧` from the headphones template response string
    - Remove `💻` from the laptops template response string
    - Remove `⌚` from the watches template response string
    - Remove `🛍️`, `🔍`, `✨`, `🎯` from all four fallback response strings
    - _Bug_Condition: isBugCondition(element) where element is a service response string containing emoji_
    - _Expected_Behavior: All response strings are clean text with no emoji characters_
    - _Preservation: Response text content, product data, and category matching logic unchanged_
    - _Requirements: 2.7, 2.8, 2.9_

  - [x] 3.5 Verify bug condition exploration test now passes
    - **Property 1: Expected Behavior** - No Emoji Icons or Raw Form Elements in UI
    - **IMPORTANT**: Re-run the SAME tests from task 1 - do NOT write new tests
    - The tests from task 1 encode the expected behavior
    - When these tests pass, it confirms the expected behavior is satisfied
    - Run all bug condition exploration tests from step 1
    - **EXPECTED OUTCOME**: Tests PASS (confirms bug is fixed)
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 2.7, 2.8, 2.9_

  - [x] 3.6 Verify preservation tests still pass
    - **Property 2: Preservation** - Chat Functionality Unchanged
    - **IMPORTANT**: Re-run the SAME tests from task 2 - do NOT write new tests
    - Run all preservation property tests from step 2
    - **EXPECTED OUTCOME**: Tests PASS (confirms no regressions)
    - Confirm all chat functionality, animations, and disabled states are intact after fix

- [x] 4. Checkpoint - Ensure all tests pass
  - Run the full test suite and confirm all tests pass
  - Visually verify in the browser: no emoji visible as avatars or placeholders, shadcn/ui Input and Button render correctly in ChatInput, product cards display the ShoppingBag icon placeholder
  - Ask the user if any questions arise
