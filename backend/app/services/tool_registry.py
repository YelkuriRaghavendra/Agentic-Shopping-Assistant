"""
Tool registry.

Defines all tools the LLM agent can call (OpenAI function-calling format).
Also maps tool names to execution handlers.

Adding a new capability:
  1. Add a tool definition to TOOL_DEFINITIONS
  2. Add a handler function below
  3. Register it in TOOL_HANDLERS

That's it — no changes to chat_service.py needed.
"""

import asyncio
from dataclasses import dataclass
from app.clients.rag_client import RAGClient, RetrievedChunk
from app.core.logging import get_logger

logger = get_logger(__name__)


def _deduplicate_chunks(chunks: list[RetrievedChunk], top_k: int = 5) -> list[RetrievedChunk]:
    """Remove duplicate products, keeping the highest-similarity chunk per product_id."""
    seen: set[str] = set()
    result: list[RetrievedChunk] = []
    for chunk in chunks:
        pid = chunk.product_id
        if pid and pid in seen:
            continue
        if pid:
            seen.add(pid)
        result.append(chunk)
        if len(result) >= top_k:
            break
    return result


@dataclass
class ToolResult:
    tool_name:        str
    success:          bool
    data:             dict
    retrieved_chunks: list[RetrievedChunk]
    # Human-readable summary passed as context to the LLM response generator
    summary:          str


# ─────────────────────────────────────────────────────────────────────────────
# Tool definitions (what the LLM sees)
# ─────────────────────────────────────────────────────────────────────────────

TOOL_DEFINITIONS: list[dict] = [
    {
        "type": "function",
        "function": {
            "name": "search_products",
            "description": (
                "Search for products. Use when customer wants to find or buy something. "
                "Search early — as soon as you know the category + brand OR use case."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query":     {"type": "string"},
                    "brand":     {"type": "string"},
                    "category":  {"type": "string"},
                    "use_case":  {"type": "string"},
                    "max_price": {"type": "number"},
                    "size":      {"type": "string"},
                    "color":     {"type": "string"},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "outfit_pairing",
            "description": (
                "Customer owns an item and wants matching recommendations. "
                "Use when they say 'I have a blue shirt, what pants go with it?'"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "owned_colour":    {"type": "string"},
                    "owned_category":  {"type": "string"},
                    "wanted_category": {"type": "string"},
                    "occasion":        {"type": "string"},
                    "budget":          {"type": "number"},
                    "size":            {"type": "string"},
                },
                "required": ["owned_colour", "owned_category", "wanted_category"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "gift_finder",
            "description": "Find gift recommendations. Use for 'gift for my dad' or 'birthday present'.",
            "parameters": {
                "type": "object",
                "properties": {
                    "recipient":  {"type": "string"},
                    "interests":  {"type": "string"},
                    "budget":     {"type": "number"},
                    "occasion":   {"type": "string"},
                    "gender":     {"type": "string"},
                },
                "required": ["recipient"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "compare_products",
            "description": "Compare two products side by side. Use for 'Nike vs Adidas' or 'which is better'.",
            "parameters": {
                "type": "object",
                "properties": {
                    "product_a": {"type": "string"},
                    "product_b": {"type": "string"},
                    "aspects":   {"type": "string"},
                },
                "required": ["product_a", "product_b"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "size_advice",
            "description": "Give sizing and fit advice. Use for 'do they run small?', 'I have wide feet'.",
            "parameters": {
                "type": "object",
                "properties": {
                    "brand":        {"type": "string"},
                    "foot_type":    {"type": "string"},
                    "current_size": {"type": "string"},
                    "category":     {"type": "string"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "order_lookup",
            "description": "Look up order status or tracking. Use for 'where is my order?'.",
            "parameters": {
                "type": "object",
                "properties": {
                    "order_id": {"type": "string"},
                    "email":    {"type": "string"},
                    "query":    {"type": "string"},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "return_request",
            "description": "Handle returns, refunds, exchanges. Use for 'I want to return', 'wrong size', 'damaged'.",
            "parameters": {
                "type": "object",
                "properties": {
                    "reason":    {"type": "string"},
                    "order_id":  {"type": "string"},
                    "item_name": {"type": "string"},
                    "exchange":  {"type": "boolean"},
                },
                "required": ["reason"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "policy_faq",
            "description": "Answer policy questions: shipping time, return window, payment, warranty.",
            "parameters": {
                "type": "object",
                "properties": {
                    "topic": {"type": "string"},
                    "query": {"type": "string"},
                },
                "required": ["topic"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "stock_check",
            "description": "Check if a specific item is in stock. Use for 'do you have this in size 10?'.",
            "parameters": {
                "type": "object",
                "properties": {
                    "product_name": {"type": "string"},
                    "size":         {"type": "string"},
                    "color":        {"type": "string"},
                },
                "required": ["product_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "escalate_to_human",
            "description": "Escalate to human agent. Use when customer is very frustrated or requests a person.",
            "parameters": {
                "type": "object",
                "properties": {
                    "reason":  {"type": "string"},
                    "urgency": {"type": "string", "enum": ["low", "medium", "high"]},
                    "summary": {"type": "string"},
                },
                "required": ["reason"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "clarify_question",
            "description": (
                "Ask ONE clarifying question when the request is so vague no useful search is possible. "
                "Only use when truly necessary — prefer searching early."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "question": {"type": "string"},
                },
                "required": ["question"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "direct_answer",
            "description": "Answer directly without tool use. Use for greetings and simple factual answers.",
            "parameters": {
                "type": "object",
                "properties": {
                    "content": {"type": "string"},
                },
                "required": ["content"],
            },
        },
    },
]


# ─────────────────────────────────────────────────────────────────────────────
# Tool handlers
# ─────────────────────────────────────────────────────────────────────────────

class ToolRegistry:

    def __init__(self, rag_client: RAGClient):
        self._rag = rag_client

    async def execute(self, tool_name: str, args: dict) -> ToolResult:
        """Route to the correct handler."""
        handler = getattr(self, f"_handle_{tool_name}", None)
        if not handler:
            return ToolResult(
                tool_name=tool_name,
                success=False,
                data={},
                retrieved_chunks=[],
                summary=f"Unknown tool: {tool_name}",
            )
        try:
            return await handler(args)
        except Exception as exc:
            logger.error("tool_registry.handler_error", tool=tool_name, error=str(exc))
            return ToolResult(
                tool_name=tool_name,
                success=False,
                data={"error": str(exc)},
                retrieved_chunks=[],
                summary=f"Tool failed: {exc}",
            )

    async def _handle_search_products(self, args: dict) -> ToolResult:
        query = args.get("query", "")
        if args.get("color"):
            query = f"{args['color']} {query}"
        filters: dict = {}
        if args.get("brand"):
            filters["brand"] = args["brand"]
        if args.get("max_price"):
            filters["max_price"] = args["max_price"]
        if args.get("category"):
            filters["doc_type"] = "product"
        chunks = await self._rag.retrieve(query=query, filters=filters)
        chunks = _deduplicate_chunks(chunks)
        summary = (
            f"Found {len(chunks)} products for: {query}"
            if chunks
            else f"No products found for: {query}. Tell the customer honestly that nothing matched their search."
        )
        return ToolResult(
            tool_name="search_products",
            success=True,
            data={"query": query, "result_count": len(chunks)},
            retrieved_chunks=chunks,
            summary=summary,
        )

    async def _handle_outfit_pairing(self, args: dict) -> ToolResult:
        from app.services.style_advisor_service import StyleAdvisorService
        advisor = StyleAdvisorService()
        result = advisor.get_outfit_recommendation(
            owned_colour=args.get("owned_colour", ""),
            owned_category=args.get("owned_category", ""),
            wanted_category=args.get("wanted_category", ""),
        )
        filters: dict = {"doc_type": "product", "in_stock": True}
        if args.get("budget"):
            filters["max_price"] = args["budget"]
        chunks = await self._rag.retrieve(query=result.search_query, filters=filters)
        chunks = _deduplicate_chunks(chunks)
        return ToolResult(
            tool_name="outfit_pairing",
            success=True,
            data={
                "owned_item": f"{args.get('owned_colour')} {args.get('owned_category')}",
                "explanation": result.explanation,
                "style_tip": result.style_tip,
                "recommended_colours": result.recommended_colours,
            },
            retrieved_chunks=chunks,
            summary=(
                f"{result.explanation} Found {len(chunks)} matching items."
                if chunks
                else f"{result.explanation} No products found. Tell the customer honestly that nothing matched."
            ),
        )

    async def _handle_gift_finder(self, args: dict) -> ToolResult:
        recipient = args.get("recipient", "someone")
        query = f"gift for {recipient}"
        if args.get("interests"):
            query = f"{args['interests']} {query}"
        filters: dict = {"doc_type": "product", "in_stock": True}
        if args.get("budget"):
            filters["max_price"] = args["budget"]
        chunks = await self._rag.retrieve(query=query, filters=filters)
        chunks = _deduplicate_chunks(chunks)
        return ToolResult(
            tool_name="gift_finder",
            success=True,
            data={"recipient": recipient, "budget": args.get("budget")},
            retrieved_chunks=chunks,
            summary=(
                f"Gift ideas for {recipient}. Found {len(chunks)} options."
                if chunks
                else f"No gift options found for {recipient}. Tell the customer honestly that nothing matched."
            ),
        )

    async def _handle_compare_products(self, args: dict) -> ToolResult:
        a = args.get("product_a", "")
        b = args.get("product_b", "")
        chunks_a, chunks_b = await asyncio.gather(
            self._rag.retrieve(query=a, filters={"doc_type": "product"}),
            self._rag.retrieve(query=b, filters={"doc_type": "product"}),
        )
        chunks_a = _deduplicate_chunks(chunks_a, top_k=2)
        chunks_b = _deduplicate_chunks(chunks_b, top_k=2)
        all_chunks = chunks_a[:2] + chunks_b[:2]
        summary = (
            f"Comparing {a} vs {b}."
            if all_chunks
            else f"No products found for comparison of {a} vs {b}. Tell the customer honestly that neither product was found."
        )
        return ToolResult(
            tool_name="compare_products",
            success=True,
            data={"product_a": a, "product_b": b},
            retrieved_chunks=all_chunks,
            summary=summary,
        )

    async def _handle_size_advice(self, args: dict) -> ToolResult:
        from app.services.style_advisor_service import StyleAdvisorService
        advisor = StyleAdvisorService()
        advice = advisor.get_size_advice(
            brand=args.get("brand"),
            foot_type=args.get("foot_type"),
            current_size=args.get("current_size"),
        )
        chunks: list[RetrievedChunk] = []
        if args.get("brand"):
            chunks = await self._rag.retrieve(
                query=f"{args['brand']} {args.get('category', 'shoes')}",
                filters={"brand": args["brand"], "doc_type": "product"},
                top_k=3,
            )
            chunks = _deduplicate_chunks(chunks, top_k=3)
        return ToolResult(
            tool_name="size_advice",
            success=True,
            data={"advice": advice},
            retrieved_chunks=chunks,
            summary=advice,
        )

    async def _handle_order_lookup(self, args: dict) -> ToolResult:
        order_id = args.get("order_id")
        if order_id:
            msg = (
                f"Order #{order_id} is in transit. "
                "For real-time tracking, check your confirmation email "
                "or visit our orders page."
            )
        else:
            msg = (
                "To look up your order I'll need your order number — "
                "you can find it in your confirmation email. "
                "Or log into your account to view all orders."
            )
        return ToolResult(
            tool_name="order_lookup",
            success=True,
            data={"message": msg},
            retrieved_chunks=[],
            summary=msg,
        )

    async def _handle_return_request(self, args: dict) -> ToolResult:
        reason = args.get("reason", "")
        exchange = args.get("exchange", False)
        action = "exchange" if exchange else "return/refund"
        policy_chunks = await self._rag.retrieve(
            query="return policy refund exchange",
            filters={"doc_type": "policy"},
            top_k=2,
        )
        policy_chunks = _deduplicate_chunks(policy_chunks, top_k=2)
        return ToolResult(
            tool_name="return_request",
            success=True,
            data={"reason": reason, "action": action},
            retrieved_chunks=policy_chunks,
            summary=f"Customer wants to {action}. Reason: {reason}.",
        )

    async def _handle_policy_faq(self, args: dict) -> ToolResult:
        topic = args.get("topic", "")
        query = f"{topic} {args.get('query', topic)}"
        chunks = await self._rag.retrieve(
            query=query,
            filters={"doc_type": "policy"},
            top_k=3,
        )
        chunks = _deduplicate_chunks(chunks, top_k=3)
        return ToolResult(
            tool_name="policy_faq",
            success=True,
            data={"topic": topic},
            retrieved_chunks=chunks,
            summary=(
                f"Policy FAQ for: {topic}. Found {len(chunks)} docs."
                if chunks
                else f"No policy documents found for: {topic}. Tell the customer honestly that no information was found."
            ),
        )

    async def _handle_stock_check(self, args: dict) -> ToolResult:
        name  = args.get("product_name", "")
        query = name
        if args.get("color"):
            query = f"{args['color']} {query}"
        if args.get("size"):
            query = f"{query} size {args['size']}"
        chunks = await self._rag.retrieve(
            query=query,
            filters={"doc_type": "product", "in_stock": True},
            top_k=3,
        )
        chunks = _deduplicate_chunks(chunks, top_k=3)
        return ToolResult(
            tool_name="stock_check",
            success=True,
            data={"product": name, "in_stock_count": len(chunks)},
            retrieved_chunks=chunks,
            summary=(
                f"Stock check for {name}. {len(chunks)} available."
                if chunks
                else f"No stock found for {name}. Tell the customer honestly that the item appears unavailable."
            ),
        )

    async def _handle_escalate_to_human(self, args: dict) -> ToolResult:
        urgency = args.get("urgency", "medium")
        if urgency == "high":
            msg = (
                "I understand this is urgent. I'm flagging this to our priority "
                "support team right now. You'll hear back within 30 minutes. "
                "For immediate help, call us on 1-800-XXX-XXXX."
            )
        else:
            msg = (
                "I'm connecting you with one of our customer service agents. "
                "You'll receive a response within 2 hours via email. "
                "I've shared a summary of our conversation with the team."
            )
        return ToolResult(
            tool_name="escalate_to_human",
            success=True,
            data={"urgency": urgency, "escalation_message": msg},
            retrieved_chunks=[],
            summary=msg,
        )

    async def _handle_clarify_question(self, args: dict) -> ToolResult:
        question = args.get("question", "")
        return ToolResult(
            tool_name="clarify_question",
            success=True,
            data={"question": question},
            retrieved_chunks=[],
            summary=question,
        )

    async def _handle_direct_answer(self, args: dict) -> ToolResult:
        content = args.get("content", "")
        return ToolResult(
            tool_name="direct_answer",
            success=True,
            data={"content": content},
            retrieved_chunks=[],
            summary=content,
        )
