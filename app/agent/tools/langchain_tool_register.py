from langchain_core.tools import tool
from langchain_core.runnables import RunnableConfig
from typing import Optional
from app.core.db.base import SessionLocal

from app.agent.tools.order_tools import (
    get_order_details as _get_order_details,
    get_user_orders as _get_user_orders,
    place_order as _place_order,
    cancel_order_item as _cancel_order_item,
    modify_order as _modify_order,
)

from app.agent.tools.product_tools import get_ordered_products, search_products
from app.utils.imptools import get_product_info


# Order tools

@tool
def get_order_details_tool(
    order_id: int,
    config: RunnableConfig
) -> dict:

    """Get full details of a specific order for a user, including ordered products, total amount, creation time, and status. Returns the order details or an error message."""

    user_id = config["configurable"]["user_id"]

    db = SessionLocal()
    try:
        return _get_order_details(db, user_id, order_id)
    finally:
        db.close()


@tool
def get_user_orders_tool(
    config: RunnableConfig
) -> list:

    """Get a summary of all orders belonging to a user, including order ID, total amount, status, and creation time. Returns a list of orders or a message/error when no orders are found."""

    user_id = config["configurable"]["user_id"]

    db = SessionLocal()
    try:
        return _get_user_orders(db, user_id)
    finally:
        db.close()


@tool
def place_order_tool(
    product_id: int,
    quantity: int,
    config: RunnableConfig
) -> dict:

    """Place a new order for a user and product after checking stock availability. Returns a success message with the new order ID or an error when the order cannot be placed."""

    user_id = config["configurable"]["user_id"]

    db = SessionLocal()
    try:
        return _place_order(db, user_id, product_id, quantity)
    finally:
        db.close()


@tool
def cancel_order_item_tool(
    order_id: int,
    config: RunnableConfig
) -> dict:

    """Cancel an order for a user and restore the stock of all products in that order. Returns a success message or an error message when the order cannot be cancelled."""

    user_id = config["configurable"]["user_id"]

    db = SessionLocal()
    try:
        return _cancel_order_item(db, user_id, order_id)
    finally:
        db.close()


from typing import List

from pydantic import BaseModel


class OrderItemInput(BaseModel):

    product_id: int
    quantity: int


@tool
def modify_order_tool(
    order_id: int,
    new_items: List[OrderItemInput],
    config: RunnableConfig
) -> dict:

    """Modify a placed order by cancelling the existing order and placing new order(s) with the specified product IDs and quantities. Returns the new order details/results or an error message."""

    user_id = config["configurable"]["user_id"]

    db = SessionLocal()
    try:
        items_as_dicts = [item.model_dump() for item in new_items]
        return _modify_order(db, user_id, order_id, items_as_dicts)
    finally:
        db.close()


# Product tools

@tool
def get_ordered_products_tool(order_id: int) -> list:

    """Get all products included in a specific order, including product ID, product name, quantity, purchase price, and order item ID. Returns a list of ordered product details or an error message."""

    db = SessionLocal()
    try:
        return get_ordered_products(db, order_id)
    finally:
        db.close()


@tool
def search_products_tool(keyword: Optional[str]=None, category:Optional[str]=None) -> dict:

    """Search products by name keyword and/or category. Returns matching products with their ID, name, price, category, and stock availability."""

    db = SessionLocal()
    try:
        return search_products(db, keyword, category)
    finally:
        db.close()


@tool
def get_product_info_tool(product_id: int) -> dict:

    """Fetches all the information for a product from the database"""

    db = SessionLocal()
    try:
        return get_product_info(db, product_id)
    finally:
        db.close()


# Return tools

from app.agent.tools.return_tools import (
    create_return,
    get_return_details,
    list_user_returns
)


@tool
def create_return_tool(
    order_id: int,
    order_item_id: int,
    reason: str,
    config: RunnableConfig
) -> dict:

    """Create a return request for a specific order item belonging to the user. Returns a success message with the newly created return ID or an error message if the order or item is invalid."""

    user_id = config["configurable"]["user_id"]

    db = SessionLocal()
    try:
        return create_return(db, user_id, order_id, order_item_id, reason)
    finally:
        db.close()


@tool
def get_return_details_tool(
    return_id: int,
    config: RunnableConfig
) -> dict:

    """Get the details of a specific return belonging to the user, including return ID, order ID, order item ID, reason, status, and creation time. Returns the return details or an error message if the return is not found or does not belong to the user."""

    user_id = config["configurable"]["user_id"]

    db = SessionLocal()
    try:
        return get_return_details(db, user_id, return_id)
    finally:
        db.close()


@tool
def list_user_returns_tool(
    config: RunnableConfig
) -> dict:

    """Get a summary of all return requests belonging to the user, including return ID, order ID, status, and creation time. Returns a list of returns or an error message."""

    user_id = config["configurable"]["user_id"]

    db = SessionLocal()
    try:
        return list_user_returns(db, user_id)
    finally:
        db.close()


# Coupon tools

from app.agent.tools.coupon_tools import (
    get_active_coupons,
    validate_coupon,
    create_coupon
)


@tool
def get_active_coupons_tool() -> dict:

    """Get all currently active and non-expired coupons available in the system. Returns coupon codes along with their discount percentage or amount and validity date."""

    db = SessionLocal()
    try:
        return get_active_coupons(db)
    finally:
        db.close()


@tool
def validate_coupon_tool(code: str) -> dict:

    """Check whether a coupon code exists, is active, and has not expired. Returns the coupon's discount details and validity date if valid, otherwise returns an error message explaining why it cannot be used."""

    db = SessionLocal()
    try:
        return validate_coupon(db, code)
    finally:
        db.close()


@tool
def create_coupon_tool(
    discount_amount: float,
    valid_days: int = 30,
    config: RunnableConfig = None
) -> dict:

    """Create a new refund coupon for a user with a fixed discount amount and specified validity period. Returns the generated coupon code, discount amount, and expiry date."""

    user_id = config["configurable"]["user_id"]

    db = SessionLocal()
    try:
        return create_coupon(db, user_id, discount_amount, valid_days)
    finally:
        db.close()


# Rag Tool

from app.agent.tools.Rag_tool import retrieve_policy_info

from embeddings import pc, vector_store


@tool
def retrieve_policy_info_tool(query: str, k: int = 3) -> dict:

    """
    Retrieve relevant company policy information (returns, refunds, shipping, cancellation, coupons, app FAQ)

    for a customer question. Use this whenever a user asks about company policies, procedures, or general platform questions.
    """

    try:
        return retrieve_policy_info(query, k)
    except Exception as e:
        return {"error":str(e)}

@tool
def escalate_to_supervisor():
    """Call this if the user's request is outside order-handling scope (returns, products, general policy, etc.) and needs a different specialist."""
    return "Escalating to supervisor"