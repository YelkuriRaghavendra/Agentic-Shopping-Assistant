# Bugfix Requirements Document

## Introduction

The ShopBot AI chat UI uses raw emoji characters (🤖, 🧑, 🛍️, 👟, 🎧, etc.) as avatars and
product image placeholders, and uses raw HTML `<input>` and `<button>` elements instead of the
project's established shadcn/ui component library. This creates visual inconsistency, poor
accessibility, and a non-production-grade appearance. The fix replaces all emoji icons with
proper Lucide React icons and all raw form elements with shadcn/ui `Input` and `Button`
components.

## Bug Analysis

### Current Behavior (Defect)

1.1 WHEN the ChatMessage component renders a bot message THEN the system displays a 🤖 emoji as the bot avatar instead of a Lucide React icon

1.2 WHEN the ChatMessage component renders a user message THEN the system displays a 🧑 emoji as the user avatar instead of a Lucide React icon

1.3 WHEN the ChatMessage component renders a product card THEN the system displays a 🛍️ emoji as the product image placeholder instead of a Lucide React icon

1.4 WHEN the TypingIndicator component renders THEN the system displays a 🤖 emoji as the bot avatar instead of a Lucide React icon

1.5 WHEN the ChatInput component renders THEN the system uses a raw HTML `<input>` element instead of the shadcn/ui `Input` component

1.6 WHEN the ChatInput component renders THEN the system uses a raw HTML `<button>` element (via `motion.button`) without the shadcn/ui `Button` component

1.7 WHEN the chatService generates a response for shoes THEN the system includes a 👟 emoji in the response text

1.8 WHEN the chatService generates a response for headphones THEN the system includes a 🎧 emoji in the response text

1.9 WHEN the chatService generates fallback responses THEN the system includes 🛍️, 🔍, ✨, and 🎯 emojis in the response text

### Expected Behavior (Correct)

2.1 WHEN the ChatMessage component renders a bot message THEN the system SHALL display a `Bot` Lucide React icon inside the avatar circle

2.2 WHEN the ChatMessage component renders a user message THEN the system SHALL display a `User` Lucide React icon inside the avatar circle

2.3 WHEN the ChatMessage component renders a product card THEN the system SHALL display a `ShoppingBag` Lucide React icon as the product image placeholder

2.4 WHEN the TypingIndicator component renders THEN the system SHALL display a `Bot` Lucide React icon inside the avatar circle

2.5 WHEN the ChatInput component renders THEN the system SHALL use the shadcn/ui `Input` component for the text field

2.6 WHEN the ChatInput component renders THEN the system SHALL use the shadcn/ui `Button` component (with `asChild` or wrapping `motion.div`) for the send button

2.7 WHEN the chatService generates a response for shoes THEN the system SHALL return clean text without emoji characters

2.8 WHEN the chatService generates a response for headphones THEN the system SHALL return clean text without emoji characters

2.9 WHEN the chatService generates fallback responses THEN the system SHALL return clean text without emoji characters

### Unchanged Behavior (Regression Prevention)

3.1 WHEN a user sends a message THEN the system SHALL CONTINUE TO display the message in the chat with the correct user bubble styling

3.2 WHEN the bot responds THEN the system SHALL CONTINUE TO display the response in the chat with the correct bot bubble styling

3.3 WHEN the bot returns product suggestions THEN the system SHALL CONTINUE TO render product cards with name, price, rating, and badge

3.4 WHEN the user presses Enter in the input field THEN the system SHALL CONTINUE TO send the message

3.5 WHEN the send button is clicked THEN the system SHALL CONTINUE TO submit the message

3.6 WHEN the assistant is typing THEN the system SHALL CONTINUE TO show the animated typing indicator with three bouncing dots

3.7 WHEN the input is disabled THEN the system SHALL CONTINUE TO prevent submission and show the disabled placeholder text

3.8 WHEN the ChatWindow header renders THEN the system SHALL CONTINUE TO display the `Bot` Lucide icon and `Sparkles` icon already present in the header (these are already correct)
