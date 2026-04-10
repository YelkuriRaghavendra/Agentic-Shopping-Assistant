"""Support agent tools: order_lookup, order_history, return_request, policy_faq, escalate."""

from langchain_core.tools import tool

from app.clients.rag_client import RAGClient
from app.config.loader import search_config


def _format_chunks(chunks) -> str:
    if not chunks:
        return "No information found."
    lines = []
    for i, chunk in enumerate(chunks):
        lines.append(f"[Ref {i+1}] {chunk.product_id}\n{chunk.content}")
    return "\n\n---\n\n".join(lines)


def create_order_lookup_tool():
    @tool
    async def order_lookup(query: str, order_id: str = "") -> str:
        """Look up order status or tracking."""
        if order_id:
            return f"Order #{order_id} is in transit. For real-time tracking, check your confirmation email or visit our orders page."
        return "To look up your order I'll need your order number — you can find it in your confirmation email."

    return order_lookup


def create_order_history_tool(rag_client: RAGClient):
    sc = search_config()
    top_k = sc["per_tool"]["order_history_lookup"]["top_k"]

    @tool
    async def order_history_lookup(query: str, customer_id: str) -> str:
        """Search past orders. Requires customer_id for scoping."""
        if not customer_id:
            return "Could not retrieve order history: customer not identified."
        chunks = await rag_client.retrieve(
            query=query,
            filters={"document_type": "ORDER", "customer_id": customer_id},
            top_k=top_k,
        )
        if not chunks:
            return "No past orders found matching your query."
        return f"Found {len(chunks)} order(s).\n\n{_format_chunks(chunks)}"

    return order_history_lookup


def create_return_request_tool(rag_client: RAGClient):
    sc = search_config()
    top_k = sc["per_tool"]["return_request"]["top_k"]

    @tool
    async def return_request(
        reason: str, order_id: str = "", item_name: str = "", exchange: bool = False
    ) -> str:
        """Handle returns, refunds, exchanges."""
        action = "exchange" if exchange else "return/refund"
        chunks = await rag_client.retrieve(
            query="return policy refund exchange", filters={"doc_type": "policy"}, top_k=top_k
        )
        policy_text = _format_chunks(chunks) if chunks else "No policy documents found."
        return f"Customer wants to {action}. Reason: {reason}.\n\nPolicy info:\n{policy_text}"

    return return_request


def create_policy_faq_tool(rag_client: RAGClient):
    sc = search_config()
    top_k = sc["per_tool"]["policy_faq"]["top_k"]

    @tool
    async def policy_faq(topic: str, query: str = "") -> str:
        """Answer policy questions: shipping, returns, warranty, payment."""
        search_query = f"{topic} {query or topic}"
        chunks = await rag_client.retrieve(
            query=search_query, filters={"doc_type": "policy"}, top_k=top_k
        )
        if not chunks:
            return f"No policy information found for: {topic}."
        return f"Policy FAQ for {topic}:\n\n{_format_chunks(chunks)}"

    return policy_faq


def create_escalate_tool():
    @tool
    async def escalate_to_human(reason: str, urgency: str = "medium", summary: str = "") -> str:
        """Escalate to human agent when customer is frustrated or requests a person."""
        if urgency == "high":
            return "I understand this is urgent. I'm flagging this to our priority support team right now. You'll hear back within 30 minutes."
        return "I'm connecting you with one of our customer service agents. You'll receive a response within 2 hours via email."

    return escalate_to_human
