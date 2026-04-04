# Vikrai -- The Commerce AI

An agentic shopping assistant that combines conversational AI, hybrid RAG search, and real-time checkout to deliver a complete in-chat commerce experience.

---

## Key Features

- **Conversational Shopping** -- natural-language product discovery and purchase flow inside a chat interface
- **Photo Upload** -- upload an image and get visually similar product recommendations
- **3-Way Hybrid RAG** -- vector search, metadata filtering, and LLM reranking for high-precision product retrieval
- **Agentic Tool Calling** -- the LLM autonomously selects tools (search, style advice, cart, checkout) based on user intent
- **Session Memory** -- multi-turn context with slot extraction (budget, size, color) persisted across messages
- **Stripe Checkout** -- end-to-end payment processing with polling-based confirmation
- **Product Comparison** -- side-by-side feature and price comparison generated from catalog data
- **Outfit Matching** -- style-aware recommendations that coordinate across product categories

---

## Architecture

```
+-----------+       +------------------+       +---------------+
|           |  HTTP |                  |  HTTP |               |
|  Next.js  +-------> FastAPI Backend  +-------> RAG Service   |
|  Frontend |       |  (Orchestrator)  |       | (pgvector)    |
|  :4001    |       |  :8000           |       | :8001         |
+-----------+       +--------+---------+       +---------------+
                             |
                             | HTTP
                             v
                    +--------+---------+
                    | Checkout/Order   |
                    | Service (NestJS) |
                    | :3001            |
                    +------------------+
```

---

## Tech Stack

| Layer     | Technology                        | Purpose                              |
|-----------|-----------------------------------|--------------------------------------|
| Frontend  | Next.js 14, React 18, TailwindCSS | Chat UI, product cards, checkout     |
| Backend   | FastAPI, Python 3.12              | Orchestrator, agentic tool dispatch  |
| RAG       | FastAPI, pgvector, OpenAI         | Embedding, vector search, reranking  |
| Commerce  | NestJS, Stripe                    | Orders, payments, merchant config    |
| LLM       | GPT-4o (Azure OpenAI)             | Chat completion, intent extraction   |
| Database  | PostgreSQL (Aurora)               | Sessions, orders, vector store       |

---

## Quick Start

### Prerequisites

- Node.js >= 18
- Python >= 3.12
- PostgreSQL with pgvector extension
- OpenAI or Azure OpenAI API key

### 1. Clone and configure environment

```bash
git clone <repo-url>
cd Agentic-Shopping-Assistant
```

Copy the `.env.example` file in each service directory to `.env` and fill in your values. See the Environment Variables section below.

### 2. Start each service

**Frontend** (port 4001):

```bash
cd Frontend && npm install && npm run dev
```

**Backend** (port 8000):

```bash
cd backend && pip install -r requirements.txt && uvicorn app.main:app --reload --port 8000
```

**RAG Service** (port 8001):

```bash
cd rag-service && make install && make dev
```

**Checkout/Order Service** (port 3001):

```bash
cd checkout-order-service && npm install && npm run start:dev
```

---

## Environment Variables

Each service requires a `.env` file. Example templates are provided:

| Service                | Example File                            |
|------------------------|-----------------------------------------|
| Frontend               | `Frontend/.env.example`                 |
| Backend                | `backend/.env.example`                  |
| RAG Service            | `rag-service/.env.example`              |
| Checkout/Order Service | `checkout-order-service/.env.example`   |

Copy each `.env.example` to `.env` and replace placeholder values with your actual credentials.

---

## Documentation

Additional design documents and API specs are available in the `docs/` folder.

---

## License

MIT
