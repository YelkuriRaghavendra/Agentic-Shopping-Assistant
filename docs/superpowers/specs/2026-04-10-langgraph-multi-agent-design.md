# LangGraph Multi-Agent Architecture + Config System

**Date:** 2026-04-10
**Status:** Draft
**Scope:** Production-grade migration of backend from custom tool-based orchestrator to LangGraph multi-agent architecture, plus extraction of all hardcoded values into a layered config system.

---

## 1. Goals

1. Replace the monolithic `ChatService` orchestrator with a LangGraph state graph of specialized agents
2. Replace single-LLM-picks-tool pattern with domain-specific agents that own their tools, prompts, and reasoning
3. Make the LLM provider swappable (OpenAI / Azure OpenAI / Anthropic) via config
4. Extract all ~160 hardcoded values across 4 services into a layered config system
5. Replace the 3-layer custom memory system with LangGraph's checkpointer
6. Support multi-tool execution within a single turn (especially for checkout)
7. Maintain identical SSE API contract with frontend (add `agent_status` event type)

---

## 2. Agent Graph Topology

```
User Message
     |
     v
+--------------+
|  Guardrails  |--blocked--> Return safe response
|    (node)    |
+--------------+
     | pass
     v
+--------------+
|  Supervisor  |  (cheap model, routing only)
|   (agent)    |
+--------------+
     |
     +-------+-------+-------+-------+
     v       v       v       v       v
+--------+ +-----+ +----+ +-------+ +--------+
|Shopping| |Style| |Gift| |Support| |Checkout|
| Agent  | |Adv. | |Find| | Agent | | Agent  |
+--------+ +-----+ +----+ +-------+ +--------+
     |       |       |       |       |
     +---+---+---+---+---+---+---+---+
         |               |
         v               v
   +----------+   +------------+
   | Citation  |   | Suggestion |   <-- parallel
   |   Node    |   |   Agent    |
   +----------+   +------------+
         |               |
         +-------+-------+
                 v
          +-----------+
          | Persister |
          |   Node    |
          +-----------+
```

---

## 3. Graph State

```python
class AgentState(TypedDict):
    # Conversation (managed by checkpointer via add_messages)
    messages: Annotated[list[AnyMessage], add_messages]

    # Routing
    current_agent: str | None
    intent: str | None

    # Shopping context (replaces sessions.context JSONB)
    slots: dict                        # {category, brand, budget, size, color, use_case}
    shown_products: list[dict]         # products shown this session

    # Customer context (replaces customers.profile JSONB + Redis cache)
    customer_id: str | None
    customer_profile: dict             # brands, sizes, people, addresses, price_sensitivity

    # Checkout context
    checkout_session_id: str | None
    checkout_state: dict               # cart items, selected address, payment status

    # Agent working memory (current turn)
    agent_response: str | None         # raw text from the domain agent
    retrieved_chunks: list[dict]       # RAG results for citation processing
    tool_results: list[dict]           # all tool executions this turn

    # Post-processing outputs
    cited_products: list[dict]
    suggestions: list[dict]
    guardrail_status: str              # "passed" | "warned" | "blocked"

    # SSE streaming metadata
    stream_events: list[dict]          # {"agent": "shopping", "status": "Searching..."}
```

---

## 4. Agent Definitions

### 4.1 Supervisor Agent

**Model:** Cheap (configurable: `agents.supervisor.model_tier`)
**Purpose:** Classify intent, extract slots, route to the right agent.
**Tools:** None — pure routing.
**Prompt source:** `config/json/agent_prompts/supervisor.md`

**Routing logic:**
- If `active_agent == "checkout"` in state and message is not off-topic -> route to Checkout Agent
- If commerce intent detected (keyword match from `config/json/commerce_intents.json`) -> route to Checkout Agent
- Otherwise classify via LLM structured output:

```json
{
  "agent": "shopping|style_advisor|gift_finder|support|checkout",
  "intent": "product_search|outfit_pairing|gift_finding|...",
  "slots": { "category": "...", "brand": "...", ... },
  "reasoning": "one sentence"
}
```

The supervisor sets `current_agent`, `intent`, and merges extracted `slots` into state.

### 4.2 Shopping Agent

**Model:** Primary (configurable: `agents.shopping.model_tier`)
**Purpose:** Product discovery, comparison, stock checks.
**Tools:**

| Tool | Source | Description |
|------|--------|-------------|
| `search_products` | `rag_client.retrieve()` | Hybrid RAG search with filters |
| `compare_products` | `rag_client.retrieve()` x N | Parallel retrieval + comparison |
| `stock_check` | `rag_client.retrieve()` | In-stock filter search |

**Multi-tool:** Can call `search_products` -> `compare_products` in one turn.
**Prompt source:** `config/json/agent_prompts/shopping.md`
**Absorbs current:** `tool_registry._handle_search_products`, `_handle_compare_products`, `_handle_stock_check`, `_enrich_query`, `_deduplicate_chunks`

### 4.3 Style Advisor Agent

**Model:** Primary
**Purpose:** Outfit matching, size recommendations, style advice, image analysis.
**Tools:**

| Tool | Source | Description |
|------|--------|-------------|
| `outfit_pairing` | `StyleAdvisorService` + RAG | Color-matched product search |
| `size_advice` | `StyleAdvisorService` + RAG | Brand-specific sizing guidance |
| `search_products` | `rag_client.retrieve()` | Find matching items |

**Vision:** Receives `image_base64` for outfit photo analysis.
**Prompt source:** `config/json/agent_prompts/style_advisor.md` (merges current `outfit-pairing/SKILL.md` + `size-fitting/SKILL.md` + `prompts.json["skills"]["stylist"]` + `prompts.json["skills"]["size_expert"]`)
**Style knowledge source:** `config/json/style_advisor.json` (color pairings, aliases, brand size notes, foot type advice — currently hardcoded in `style_advisor_service.py`)

### 4.4 Gift Finder Agent

**Model:** Primary
**Purpose:** Gift recommendations with recipient context.
**Tools:**

| Tool | Source | Description |
|------|--------|-------------|
| `gift_search` | RAG with recipient context | Budget-aware gift search |
| `search_products` | `rag_client.retrieve()` | Fallback product search |

**People context:** Reads `customer_profile.known_people` from state. Extracts new person mentions via `people_extractor` (moved from `MemoryService.extract_people_from_message`).
**Prompt source:** `config/json/agent_prompts/gift_finder.md` (merges current `gift-finding/SKILL.md` + `prompts.json["skills"]["gift_advisor"]`)

### 4.5 Support Agent

**Model:** Primary
**Purpose:** Post-purchase support — orders, returns, policies, escalation.
**Tools:**

| Tool | Source | Description |
|------|--------|-------------|
| `order_lookup` | Commerce client | Order status by ID |
| `order_history_lookup` | RAG (customer-scoped) | Semantic search over past orders |
| `return_request` | RAG (policy docs) | Handle returns/exchanges |
| `policy_faq` | RAG (policy docs) | Shipping, warranty, payment policy |
| `escalate_to_human` | Direct response | Flag for human handoff |

**Empathy detection:** If user message contains frustration signals (from `config/json/guardrails.json["frustration_signals"]`), the agent's prompt is augmented with empathy rules.
**Prompt source:** `config/json/agent_prompts/support.md` (merges current `customer-empathy/SKILL.md` + support tool prompts)

### 4.6 Checkout Agent

**Model:** Primary
**Purpose:** End-to-end checkout — cart management, address collection, payment, order placement.
**Tools:**

| Tool | Source | Description |
|------|--------|-------------|
| `place_order` | Commerce client | Charge card + create order |
| `save_address` | Customer repository | Persist address to profile |
| `request_payment_setup` | Stripe service | Create SetupIntent for card save |
| `request_address_form` | Frontend signal | Render inline address form |
| `update_cart` | Commerce client | Add/remove/update cart items |
| `exit_checkout` | State update | Return to shopping mode |

**Multi-tool loop:** Can execute multiple tools per turn. Example: "Ship to home and pay with my saved card" -> `save_address` -> `place_order` in one turn. The agent loops until it either needs user input or completes the action.
**Prompt source:** `config/json/agent_prompts/checkout.md` (current `checkout-agent.md`)
**Checkout action events:** Tools return `checkout_action` signals (`payment_setup`, `address_form`, `confirm_payment`, `order_placed`, `exit_checkout`) that are forwarded to frontend via SSE.

### 4.7 Suggestions Agent

**Model:** Cheap (configurable: `agents.suggestions.model_tier`)
**Purpose:** Generate 3-4 contextual suggestion chips.
**Tools:** None.
**Input:** Receives from state: `intent`, `slots`, `shown_products`, `agent_response`, `customer_profile`, `current_agent`
**Output:** `[{label: str, message: str}]` — max count from `config/json/agents.json["suggestions"]["max_count"]`
**Execution:** Runs in parallel with Citation Node.
**Prompt source:** `config/json/agent_prompts/suggestions.md`

---

## 5. Graph Nodes (Non-Agent)

### 5.1 Guardrails Node

**Input:** User message from state.
**Logic:**
1. Check injection patterns (from `config/json/guardrails.json["blocked_patterns"]`)
2. Check harmful content (from `config/json/guardrails.json["harmful_patterns"]`)
3. Check PII (credit card, password regexes from `config/json/guardrails.json["pii_patterns"]`)
4. If blocked: set `guardrail_status = "blocked"`, set `agent_response` to safe response from `config/json/guardrails.json["responses"]`
**Output:** Sets `guardrail_status` in state. Returns routing decision: `"blocked"` or `"pass"`.

### 5.2 Slot Extractor Node

**Runs inside:** Supervisor agent (not a separate node).
**Logic:** Extract category, use_case, brand, budget, size, color from message using keyword maps in `config/json/business_rules.json["slot_extraction"]`. Merge into `state.slots`.
**People extraction:** Detect person mentions using `config/json/business_rules.json["people_context"]`. Merge into `state.customer_profile.known_people`.

### 5.3 Citation Node

**Input:** `agent_response` + `retrieved_chunks` from state.
**Logic:** Parse `[P1]`, `[P2]` markers from agent response. Build citation map from retrieved chunks. Replace markers with product cards. Generate `answer_html`.
**Output:** Sets `cited_products` in state.
**Reuses:** Current `CitationService` logic unchanged.

### 5.4 Persister Node

**Input:** Full state after post-processing.
**Logic:**
1. Save user message to `messages` table
2. Save assistant message (with cited_products, intent, guardrail_status) to `messages` table
3. Increment session counters (turn_delta, token_delta)
4. Sync `customer_profile` changes back to `customers.profile` JSONB
5. Generate session title if `message_count == config threshold`
**Output:** Sets `message_id` for the saved assistant message.

---

## 6. LLM Provider Abstraction

### 6.1 Factory

```python
# backend/app/agent/llm_factory.py

class ModelTier(str, Enum):
    PRIMARY = "primary"      # GPT-4o / Claude Sonnet / etc
    CHEAP = "cheap"          # GPT-4o-mini / Haiku / etc
    EMBEDDING = "embedding"  # text-embedding-3-large / etc

def create_chat_model(tier: ModelTier = ModelTier.PRIMARY) -> BaseChatModel:
    """
    Returns a LangChain BaseChatModel based on config.

    Reads from config/json/llm.json:
    {
      "provider": "openai|azure_openai|anthropic",
      "models": {
        "primary": {"model": "gpt-4o", "temperature": 0.3, "max_tokens": 1024},
        "cheap": {"model": "gpt-4o-mini", "temperature": 0.3, "max_tokens": 512},
        "embedding": {"model": "text-embedding-3-large", "dimensions": 1536}
      },
      "azure": {
        "endpoint": "...",
        "api_version": "2024-02-15-preview",
        "deployments": {"primary": "gpt-4o", "cheap": "gpt-4o-mini"}
      },
      "anthropic": {
        "models": {"primary": "claude-sonnet-4-6", "cheap": "claude-haiku-4-5-20251001"}
      },
      "fallback": {
        "enabled": true,
        "tier": "cheap"
      }
    }

    Environment variables override JSON config:
      LLM_PROVIDER, LLM_PRIMARY_MODEL, LLM_CHEAP_MODEL, etc.
    """
```

### 6.2 Per-Agent Model Assignment

Each agent specifies its model tier in `config/json/agents.json`:

```json
{
  "supervisor": { "model_tier": "cheap", "max_tokens": 256 },
  "shopping":   { "model_tier": "primary", "max_tokens": 1024 },
  "style_advisor": { "model_tier": "primary", "max_tokens": 1024 },
  "gift_finder": { "model_tier": "primary", "max_tokens": 1024 },
  "support":    { "model_tier": "primary", "max_tokens": 1024 },
  "checkout":   { "model_tier": "primary", "max_tokens": 1024 },
  "suggestions": { "model_tier": "cheap", "max_tokens": 256 }
}
```

---

## 7. Layered Config System

### 7.1 Architecture

```
+----------------------------------------------+
|  Layer 3: Runtime Overrides (future)          |  DB + Redis, per-tenant, hot-reload
+----------------------------------------------+
|  Layer 2: Environment Variables               |  .env / deployment config
+----------------------------------------------+
|  Layer 1: JSON Config Files                   |  Repo, sensible defaults
+----------------------------------------------+
```

**Resolution order:** Layer 3 > Layer 2 > Layer 1.
Layer 3 is designed but not implemented in Phase 1.

### 7.2 JSON Config Files

All live under `backend/app/config/json/`:

| File | Contents | Replaces |
|------|----------|----------|
| `business_rules.json` | **EXISTS** — extend with new sections | Already used |
| `prompts.json` | **EXISTS** — keep for base prompts, inline instructions | Already used |
| `agents.json` | Agent model tiers, max_tokens, enabled/disabled | New |
| `llm.json` | Provider, model names, temperature, fallback config | `llm_client.py` hardcoded values + `config.py` LLM settings |
| `commerce_intents.json` | Keyword maps, required slots, slot prompts, purchase phrases, browse words | `chat_service.py` lines 93-156 |
| `guardrails.json` | Harmful regex, off-topic signals, shopping signals, PII patterns, blocked patterns, intent map, safe responses | `guardrails_service.py` lines 49-100 + `config.py` BLOCKED_PATTERNS + `prompts.json["guardrail_responses"]` |
| `style_advisor.json` | Color pairings, color aliases, brand size notes, foot type advice | `style_advisor_service.py` lines 14-63 |
| `suggestions.json` | Max count, label max length, budget multipliers, product name max length | `chat_service.py` scattered constants |
| `streaming.json` | Word delay, heartbeat interval, stuck request timeout | `chat_service.py` sleep values |
| `search.json` | Default top_k, per-tool top_k overrides, dedup settings | `tool_registry.py` top_k values |
| `memory.json` | History token budget, max turns, min turns, max known people, max shown products in prompt, max brands in prompt, title generation threshold | `chat_service.py` + `prompt_builder_service.py` + `memory_service.py` constants |

#### New `agents.json` example:

```json
{
  "_comment": "Agent configuration. Edit without touching Python code.",
  "supervisor": {
    "model_tier": "cheap",
    "max_tokens": 256,
    "prompt_file": "agent_prompts/supervisor.md"
  },
  "shopping": {
    "model_tier": "primary",
    "max_tokens": 1024,
    "prompt_file": "agent_prompts/shopping.md",
    "tools": ["search_products", "compare_products", "stock_check"]
  },
  "style_advisor": {
    "model_tier": "primary",
    "max_tokens": 1024,
    "prompt_file": "agent_prompts/style_advisor.md",
    "tools": ["outfit_pairing", "size_advice", "search_products"]
  },
  "gift_finder": {
    "model_tier": "primary",
    "max_tokens": 1024,
    "prompt_file": "agent_prompts/gift_finder.md",
    "tools": ["gift_search", "search_products"]
  },
  "support": {
    "model_tier": "primary",
    "max_tokens": 1024,
    "prompt_file": "agent_prompts/support.md",
    "tools": ["order_lookup", "order_history_lookup", "return_request", "policy_faq", "escalate_to_human"]
  },
  "checkout": {
    "model_tier": "primary",
    "max_tokens": 1024,
    "prompt_file": "agent_prompts/checkout.md",
    "multi_tool_loop": true,
    "max_tool_calls_per_turn": 5,
    "tools": ["place_order", "save_address", "request_payment_setup", "request_address_form", "update_cart", "exit_checkout"]
  },
  "suggestions": {
    "model_tier": "cheap",
    "max_tokens": 256,
    "prompt_file": "agent_prompts/suggestions.md",
    "max_count": 4,
    "label_max_length": 35
  }
}
```

#### New `commerce_intents.json` example:

```json
{
  "_comment": "Commerce intent classification. Edit keywords without touching Python code.",
  "intent_keywords": {
    "checkout_initiate": [
      "checkout", "check out", "place order", "place my order", "buy now",
      "proceed to checkout", "proceed to payment", "complete my purchase",
      "confirm my order", "pay for this", "buy it now", "purchase it now"
    ],
    "add_to_cart": ["add to cart", "add to my cart", "put in cart", "add this"],
    "remove_from_cart": ["remove from cart", "take out of cart", "delete from cart"],
    "view_cart": ["view cart", "show cart", "what's in my cart", "my cart"],
    "order_status": ["order status", "where is my order", "track my order"],
    "order_history": ["order history", "my orders", "past orders", "previous orders"],
    "cancel_order": ["cancel order", "cancel my order", "cancel purchase"]
  },
  "required_slots": {
    "add_to_cart": ["product_id", "quantity"],
    "remove_from_cart": ["product_id"],
    "view_cart": [],
    "checkout_initiate": [],
    "order_status": ["order_id"],
    "order_history": [],
    "cancel_order": ["order_id"]
  },
  "slot_prompts": {
    "product_id": "Which product would you like? Could you describe it or give me the product name?",
    "quantity": "How many would you like to add?",
    "order_id": "Could you share your order number? You can find it in your confirmation email.",
    "line_items": "Your cart appears to be empty. Would you like to add some items first?"
  },
  "purchase_intent_phrases": [
    "i want to buy", "i'd like to buy", "i would like to buy",
    "i want to purchase", "i'd like to purchase", "i would like to purchase",
    "i want to order", "i'd like to order", "i would like to order"
  ],
  "browse_category_words": [
    "shoes", "shoe", "sneakers", "boots", "sandals", "slippers",
    "shirts", "shirt", "pants", "jeans", "jacket", "jackets",
    "clothes", "clothing", "apparel", "dress", "dresses",
    "something", "anything", "some", "a few", "options"
  ],
  "self_signals": ["myself", "for me", "for myself", "me ", "i need", "i want", "i'm looking", "im looking", "my size"],
  "other_signals": ["someone", "someone else", "gift", "for my friend", "for my dad", "for my mom", "for my wife", "for my husband", "for my partner", "for him", "for her"]
}
```

#### New `guardrails.json` example:

```json
{
  "_comment": "Guardrail patterns and responses. Edit without touching Python code.",
  "injection_patterns": [
    "ignore previous instructions", "ignore your instructions",
    "you are now", "act as", "jailbreak", "disregard your",
    "forget your instructions", "new instructions:", "system prompt"
  ],
  "harmful_patterns": ["\\b(kill|murder|bomb|attack|weapon|exploit|hack)\\b"],
  "off_topic_signals": [
    "\\b(write|code|program|script|essay|poem|story|song)\\b",
    "\\b(math|calcul|equation|solve|formula)\\b",
    "\\b(politic|election|president|minister|government)\\b",
    "\\b(recipe|cook|ingredient|calories)\\b"
  ],
  "shopping_signals": ["\\b(buy|price|deliver|ship|order|return|shoe|sneaker|product|brand|size|cart|checkout)\\b"],
  "pii_patterns": {
    "credit_card": "\\b(?:\\d[ -]*?){13,16}\\b",
    "password": "(?i)(password|passwd|pwd)\\s*[:=]\\s*\\S+"
  },
  "frustration_signals": ["frustrated", "angry", "annoyed", "terrible", "worst", "hate", "unacceptable"],
  "intent_keywords": {
    "product_search": ["find", "looking for", "search", "show me", "any", "recommend"],
    "outfit_pairing": ["match", "pair", "goes with", "complement", "outfit", "combine"],
    "gift_finding": ["gift", "present", "birthday", "for my", "for him", "for her"],
    "size_advice": ["size", "fit", "sizing", "wide feet", "narrow", "true to size"],
    "order_lookup": ["order", "tracking", "shipped", "delivery status"],
    "return_request": ["return", "refund", "exchange", "wrong size", "damaged"],
    "policy_faq": ["policy", "shipping time", "warranty", "how long"],
    "comparison": ["compare", "vs", "versus", "better", "difference"],
    "general": ["hello", "hi", "hey", "thanks", "thank you", "bye"]
  },
  "responses": {
    "injection_blocked": "I'm here to help you with shopping and orders. What can I find for you today?",
    "harmful_blocked": "I can only help with shopping-related questions. Please contact our support team if you need further assistance.",
    "off_topic": "I'm your shopping assistant -- I can help with products, orders, returns, and more. What can I help you find?",
    "generic_blocked": "I'm here to help with shopping. How can I assist?"
  }
}
```

#### New `search.json` example:

```json
{
  "_comment": "RAG search configuration per tool. Edit without touching Python code.",
  "defaults": {
    "top_k": 5,
    "dedup_top_k": 5
  },
  "per_tool": {
    "search_products": { "top_k": 5 },
    "compare_products": { "top_k_per_product": 2 },
    "size_advice": { "top_k": 3 },
    "return_request": { "top_k": 2 },
    "policy_faq": { "top_k": 3 },
    "stock_check": { "top_k": 3 },
    "order_history_lookup": { "top_k": 5 },
    "gift_search": { "top_k": 5 },
    "outfit_pairing": { "top_k": 5 }
  }
}
```

#### New `memory.json` example:

```json
{
  "_comment": "Memory and conversation history settings.",
  "history": {
    "token_budget": 800,
    "max_turns": 6,
    "min_turns": 2
  },
  "session": {
    "title_generation_threshold": 4,
    "title_generation_max_tokens": 20,
    "title_generation_message_limit": 4
  },
  "profile": {
    "max_known_people": 10,
    "max_shown_products_in_prompt": 8,
    "max_brands_in_prompt": 3,
    "max_order_results": 5
  },
  "suggestions": {
    "max_count": 4,
    "label_max_length": 35,
    "product_name_max_length": 25,
    "budget_cheaper_multiplier": 0.5,
    "budget_higher_multiplier": 1.5
  }
}
```

### 7.3 Config Loader Changes

Extend the existing `config/loader.py`:

```python
@lru_cache(maxsize=1)
def agents_config() -> dict:
    return _load("agents.json")

@lru_cache(maxsize=1)
def llm_config() -> dict:
    return _load("llm.json")

@lru_cache(maxsize=1)
def commerce_intents() -> dict:
    return _load("commerce_intents.json")

@lru_cache(maxsize=1)
def guardrails_config() -> dict:
    return _load("guardrails.json")

@lru_cache(maxsize=1)
def style_config() -> dict:
    return _load("style_advisor.json")

@lru_cache(maxsize=1)
def search_config() -> dict:
    return _load("search.json")

@lru_cache(maxsize=1)
def memory_config() -> dict:
    return _load("memory.json")

@lru_cache(maxsize=1)
def streaming_config() -> dict:
    return _load("streaming.json")
```

### 7.4 Environment Variable Overrides

Environment variables override JSON config values. Convention: `{SECTION}_{KEY}` in uppercase.

```
# These override llm.json values
LLM_PROVIDER=anthropic
LLM_PRIMARY_MODEL=claude-sonnet-4-6
LLM_CHEAP_MODEL=claude-haiku-4-5-20251001
LLM_TEMPERATURE=0.3
LLM_MAX_TOKENS=1024

# These override search.json values
SEARCH_DEFAULT_TOP_K=5
SEARCH_MIN_SIMILARITY=0.3

# These override memory.json values
MEMORY_HISTORY_TOKEN_BUDGET=800
MEMORY_MAX_TURNS=6

# These override streaming.json values
STREAM_WORD_DELAY_MS=20
STREAM_HEARTBEAT_INTERVAL_S=5
```

The config loader resolves: `env var > json file > hardcoded default`.

---

## 8. Checkpointer (Replaces 3-Layer Memory)

### 8.1 Setup

```python
# backend/app/agent/checkpointer.py
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

async def create_checkpointer() -> AsyncPostgresSaver:
    """
    Uses the same DATABASE_URL as the chat backend.
    Creates checkpoint tables on first use.
    """
    checkpointer = AsyncPostgresSaver.from_conn_string(settings.DATABASE_URL)
    await checkpointer.setup()
    return checkpointer
```

### 8.2 Thread ID = Session ID

Each conversation session maps to a LangGraph thread:
```python
config = {"configurable": {"thread_id": str(session_id)}}
result = await graph.ainvoke(state, config)
```

The checkpointer automatically persists:
- Full message history (replaces Layer 1: turn history)
- Slots, shown_products (replaces Layer 2: session context)
- Customer profile (replaces Layer 3: customer profile)

### 8.3 Customer Profile Sync

Customer profile is loaded from DB into `AgentState.customer_profile` at the start of each turn. After the turn, the Persister Node syncs changes back to the `customers.profile` JSONB column. This ensures the profile survives session boundaries (a new session for the same customer loads the profile from DB, not from a previous thread's checkpoint).

---

## 9. SSE Streaming

### 9.1 Event Types

```
{"type": "agent_status", "agent": "shopping", "status": "Searching for Nike running shoes..."}
{"type": "agent_status", "agent": "shopping", "status": "Comparing top results..."}
{"type": "token", "content": "Here are "}
{"type": "token", "content": "the top 3 "}
{"type": "checkout_action", "action": "address_form", "data": {"prefilled": {...}}}
{"type": "done", "message_id": "...", "session_id": "...", "answer_html": "...", "cited_products": [...], "suggestions": [...], "intent": "..."}
{"type": "error", "content": "..."}
```

### 9.2 Implementation

Use `graph.astream_events(state, config, version="v2")` and map LangGraph events to SSE:

| LangGraph Event | SSE Event |
|-----------------|-----------|
| `on_chain_start` (agent node) | `agent_status` with agent name |
| `on_tool_start` | `agent_status` with tool description |
| `on_chat_model_stream` (final agent) | `token` |
| `on_chain_end` (post-processing) | `done` with full payload |

### 9.3 Heartbeats

Send SSE comment `": heartbeat\n\n"` every `streaming.heartbeat_interval_seconds` (default 5s) during non-streaming phases (tool execution, RAG search) to prevent proxy/browser timeouts.

---

## 10. New ChatService (Thin Wrapper)

```python
class ChatService:
    """
    Replaces the current 900-line orchestrator.
    Delegates all logic to the LangGraph graph.
    Only handles: rate limiting, state initialization, SSE formatting.
    """

    def __init__(self, graph: CompiledGraph, rate_limiter: RateLimiterService, ...):
        self._graph = graph
        self._rate_limiter = rate_limiter

    async def handle(self, request: ChatRequest) -> ChatResponse:
        await self._rate_limiter.check(request.customer_id)
        session = await self._resolve_session(request)
        customer_profile = await self._load_customer_profile(session.customer_id)

        input_state = {
            "messages": [HumanMessage(content=request.message)],
            "customer_id": str(session.customer_id) if session.customer_id else None,
            "customer_profile": customer_profile,
            "slots": session.context.get("slots", {}),
            "shown_products": session.context.get("shown_products", []),
            "checkout_session_id": session.context.get("checkout_session_id"),
        }

        config = {"configurable": {"thread_id": str(session.session_id)}}
        result = await self._graph.ainvoke(input_state, config)
        return self._to_chat_response(result, session)

    async def handle_stream(self, request: ChatRequest) -> AsyncIterator[str]:
        # Same setup, then:
        async for event in self._graph.astream_events(input_state, config, version="v2"):
            sse_event = self._map_to_sse(event)
            if sse_event:
                yield sse_event
```

---

## 11. Directory Structure

```
backend/app/
+-- agent/                              # REWRITTEN -- LangGraph agent system
|   +-- graph.py                        # StateGraph definition + compilation
|   +-- state.py                        # AgentState TypedDict
|   +-- llm_factory.py                  # Provider-agnostic LLM factory
|   +-- checkpointer.py                 # AsyncPostgresSaver setup
|   +-- nodes/                          # Graph nodes (non-agent)
|   |   +-- guardrails.py              # Input guardrail check
|   |   +-- citations.py               # Citation processing (reuses CitationService)
|   |   +-- persister.py               # DB persistence + profile sync
|   |   +-- output_guardrails.py       # Output guardrail check
|   +-- agents/                         # Agent node implementations
|   |   +-- supervisor.py              # Supervisor routing
|   |   +-- shopping.py                # Shopping agent + tools
|   |   +-- style_advisor.py           # Style advisor + tools
|   |   +-- gift_finder.py             # Gift finder + tools
|   |   +-- support.py                 # Support agent + tools
|   |   +-- checkout.py                # Checkout agent + tools (multi-tool loop)
|   |   +-- suggestions.py            # Suggestions agent
|   +-- tools/                          # Tool definitions per agent
|   |   +-- shopping_tools.py
|   |   +-- style_tools.py
|   |   +-- gift_tools.py
|   |   +-- support_tools.py
|   |   +-- checkout_tools.py
|   +-- prompts/                        # Kept for backward compat; actual prompts in config/json/agent_prompts/
+-- config/
|   +-- loader.py                       # EXTENDED -- new config loaders
|   +-- json/
|   |   +-- business_rules.json        # EXISTS -- extended
|   |   +-- prompts.json               # EXISTS -- kept
|   |   +-- agents.json                # NEW
|   |   +-- llm.json                   # NEW
|   |   +-- commerce_intents.json      # NEW
|   |   +-- guardrails.json            # NEW
|   |   +-- style_advisor.json         # NEW
|   |   +-- search.json                # NEW
|   |   +-- memory.json                # NEW
|   |   +-- streaming.json             # NEW
|   |   +-- agent_prompts/             # NEW -- markdown prompt files
|   |       +-- supervisor.md
|   |       +-- shopping.md
|   |       +-- style_advisor.md
|   |       +-- gift_finder.md
|   |       +-- support.md
|   |       +-- checkout.md
|   |       +-- suggestions.md
+-- services/
|   +-- chat_service.py                 # REWRITTEN -- thin graph wrapper (~100 lines)
|   +-- citation_service.py            # KEPT
|   +-- guardrails_service.py          # KEPT -- logic reused by guardrails node
|   +-- style_advisor_service.py       # KEPT -- reads from style_advisor.json now
|   +-- stripe_customer_service.py     # KEPT
|   +-- rate_limiter_service.py        # KEPT
|   +-- feature_flag_service.py        # KEPT
|   +-- memory_service.py              # REMOVED
|   +-- prompt_builder_service.py      # REMOVED
|   +-- tool_registry.py              # REMOVED
|   +-- checkout_tools.py             # REMOVED
|   +-- skills/                        # REMOVED (entire directory)
+-- clients/
|   +-- rag_client.py                  # KEPT
|   +-- commerce_client.py            # KEPT
|   +-- redis_client.py               # KEPT
|   +-- llm_client.py                 # REMOVED -- replaced by llm_factory.py
```

---

## 12. Dependencies

### New packages:

```
langgraph>=0.4
langchain-core>=0.3
langchain-openai>=0.3        # OpenAI / Azure OpenAI provider
langchain-anthropic>=0.3     # Anthropic provider
langgraph-checkpoint-postgres>=2.0
```

### Removed packages:

```
openai                       # Replaced by langchain-openai
tenacity                     # LangChain handles retries
```

---

## 13. Frontend Changes

Minimal. Only changes to SSE parser in `useChat.ts`:

### 13.1 New SSE event type

```typescript
// hooks/useChat.ts -- add case in SSE parser
case "agent_status":
  setAgentStatus({ agent: data.agent, status: data.status });
  break;
```

### 13.2 New component

```typescript
// components/AgentStatusIndicator.tsx
// Shows below TypingIndicator: "Searching for Nike running shoes..."
// Auto-hides when first token arrives
```

### 13.3 Frontend config extraction

Move hardcoded values to `Frontend/config/config.ts`:

```typescript
export const APP_CONFIG = {
  // Image upload
  imageMaxDimension: 1024,
  imageQuality: 0.75,

  // Timeouts
  stuckRequestTimeout: 30000,
  queryStaleTime: 60000,

  // Display
  sessionTitleMaxLength: 35,
  currency: { symbol: "Rs.", locale: "en-IN" },
  botName: "Vy",

  // Suggestions
  defaultChips: ["Yes -- buy it", "Show all 5", "Show the coupon"],
};
```

---

## 14. What Gets Deleted

| File/Directory | Lines | Reason |
|----------------|-------|--------|
| `services/memory_service.py` | 442 | Replaced by LangGraph checkpointer + persister node |
| `services/prompt_builder_service.py` | 199 | Each agent builds its own prompt from markdown files |
| `services/tool_registry.py` | 681 | Split across `agent/tools/*.py` |
| `services/checkout_tools.py` | 402 | Moved to `agent/tools/checkout_tools.py` |
| `services/skills/` (entire dir) | ~400 | Skills absorbed into agent prompt files |
| `clients/llm_client.py` | 448 | Replaced by `agent/llm_factory.py` |
| `agent/skill_loader.py` | ~60 | No longer needed |
| `agent/skills/` (existing dir) | ~300 | Merged into `config/json/agent_prompts/*.md` |
| `agent/commands/` | ~100 | No longer needed |
| `agent/agents/` (existing md) | ~200 | Replaced by new agent_prompts |

**Total lines removed:** ~3,200
**Total lines added (estimated):** ~2,000 (agents, tools, nodes, config JSONs)
**Net reduction:** ~1,200 lines

---

## 15. Migration Path

### Phase 1: Config extraction (no behavior change)
1. Create all new JSON config files
2. Update `loader.py` with new loaders
3. Replace hardcoded values in existing code with config reads
4. Run existing tests — everything passes, behavior identical

### Phase 2: LLM abstraction (no behavior change)
1. Add `llm_factory.py`
2. Create `llm.json` config
3. Wrap existing `LLMClient` to use LangChain models internally
4. Run existing tests — behavior identical

### Phase 3: Build agents one at a time
1. Create `state.py`, `graph.py` (skeleton)
2. Build Supervisor Agent — replaces intent classification + routing
3. Build Shopping Agent — replaces `search_products`, `compare_products`, `stock_check` tools
4. Build Style Advisor Agent — replaces `outfit_pairing`, `size_advice` tools + skills
5. Build Gift Finder Agent — replaces `gift_finder` tool + skill
6. Build Support Agent — replaces `order_lookup`, `return_request`, `policy_faq`, `escalate_to_human` tools
7. Build Checkout Agent — replaces `CheckoutToolRegistry` + checkout mode
8. Build Suggestions Agent — replaces `_build_suggestions` + `_rule_based_suggestions`
9. Build graph nodes: guardrails, citations, persister
10. Wire everything in `graph.py`

### Phase 4: Replace ChatService
1. Rewrite `ChatService` as thin wrapper
2. Update `chat_controller.py` factory function
3. Set up checkpointer
4. Run integration tests

### Phase 5: Cleanup
1. Delete removed files
2. Update imports
3. Update tests
4. Update documentation

---

## 16. Testing Strategy

### Unit tests (per agent)
- Each agent tested in isolation with mocked tools
- Verify: correct tools called, correct arguments, response format

### Integration tests (graph level)
- Full graph execution with mocked LLM + mocked RAG
- Verify: routing, state transitions, checkout multi-tool loop

### Config tests
- Verify all JSON configs parse correctly
- Verify env var overrides work
- Verify missing config falls back to defaults

### SSE tests
- Verify event format matches frontend expectations
- Verify heartbeats during tool execution
- Verify `agent_status` events are emitted

### Regression tests
- Same test inputs as current test suite
- Verify identical outputs (or better)

---

## 17. Risks and Mitigations

| Risk | Mitigation |
|------|------------|
| LangGraph adds latency (supervisor routing = extra LLM call) | Supervisor uses cheap model (~100ms). Offset by smaller per-agent prompts. |
| Checkpointer tables grow large | Add TTL-based cleanup job. Partition by month. |
| Multi-tool loop in checkout could infinite-loop | `max_tool_calls_per_turn` config (default 5). Circuit breaker. |
| Provider-agnostic abstraction leaks (tool_calling differences) | LangChain handles this. Test with all 3 providers in CI. |
| Config file sprawl (8 new JSON files) | Each file is focused. Better than 160 magic numbers scattered across Python. |
| Frontend breaks from SSE format change | Only additive change (`agent_status` event). Existing events unchanged. |
