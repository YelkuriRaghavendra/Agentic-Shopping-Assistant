"""Checkout agent — cart, address, payment, order placement. Supports multi-tool loop."""

from pathlib import Path

from langchain_core.language_models import BaseChatModel
from langgraph.prebuilt import create_react_agent

from app.agent.tools.checkout_tools import (
    create_exit_checkout_tool,
    create_place_order_tool,
    create_request_address_form_tool,
    create_request_payment_setup_tool,
    create_save_address_tool,
    create_update_cart_tool,
)
from app.clients.commerce_client import CommerceClient
from app.core.logging import get_logger
from app.db.repositories import CustomerRepository

logger = get_logger(__name__)
_PROMPT_PATH = Path(__file__).parent.parent.parent / "config" / "agent_prompts" / "checkout.md"


def create_checkout_agent(
    llm: BaseChatModel,
    commerce: CommerceClient,
    customer_repo: CustomerRepository,
    stripe_service,
    customer_id: str | None = None,
    checkout_session_id: str | None = None,
):
    tools = [
        create_place_order_tool(commerce, customer_id),
        create_save_address_tool(customer_repo, customer_id),
        create_request_payment_setup_tool(stripe_service, customer_id),
        create_request_address_form_tool(),
        create_update_cart_tool(commerce, checkout_session_id),
        create_exit_checkout_tool(),
    ]
    prompt = _PROMPT_PATH.read_text(encoding="utf-8")
    agent = create_react_agent(model=llm, tools=tools, prompt=prompt)
    logger.info("checkout_agent.created")
    return agent
