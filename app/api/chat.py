from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from langchain_core.messages import HumanMessage
from sqlalchemy.orm import Session

from app.agent.agent import agent
from app.core.db.base import SessionLocal
from app.core.db.models import User, Product, Thread
from app.agent.tools.langchain_tool_register import get_user_orders_tool
from app.agent.tools.order_tools import place_order
from app.agent.tools.product_tools import get_ordered_products
from app.core.security import get_current_user_id

router = APIRouter(prefix="/chat", tags=["chat"])
DEMO_USER_ID = 200


class ChatRequest(BaseModel):
    thread_id: str
    message: str


class DemoChatRequest(BaseModel):
    session_id: str
    message: str
    query_number: int = Field(ge=1, le=5)


def _content_to_text(content: object) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(_content_to_text(item) for item in content)
    if isinstance(content, dict):
        if "text" in content:
            return _content_to_text(content["text"])
        if "content" in content:
            return _content_to_text(content["content"])
    return ""


def format_agent_label(agent_key: str | None) -> str:
    """Format active agent field name to human-friendly display.
    Specifically: 'if active agent is return_agent so in the left sidebar for that chat it should look like return'
    """
    if not agent_key or str(agent_key).strip() in ("", "None", "not_sure"):
        return "Support"
    mapping = {
        "return_agent": "Return",
        "order_agent": "Order",
        "product_agent": "Product",
        "coupon_agent": "Coupon",
        "qa_agent": "Policy / QA",
        "not_sure": "Support",
    }
    return mapping.get(str(agent_key).strip(), str(agent_key).replace("_agent", "").title())


def _ensure_thread_exists(thread_id: str, user_id: int):
    db: Session = SessionLocal()
    try:
        existing = db.query(Thread).filter(Thread.thread_id == thread_id).first()
        if not existing:
            db.add(Thread(thread_id=thread_id, user_id=user_id))
            db.commit()
    finally:
        db.close()


def _verify_thread_owner(thread_id: str, user_id: int):
    db: Session = SessionLocal()
    try:
        thread = db.query(Thread).filter(Thread.thread_id == thread_id).first()
        if not thread or thread.user_id != user_id:
            raise HTTPException(status_code=403, detail="Not your thread")
    finally:
        db.close()


def _ensure_demo_customer() -> None:
    db: Session = SessionLocal()
    try:
        user = db.query(User).filter(User.user_id == DEMO_USER_ID).first()
        if not user:
            user = User(
                user_id=DEMO_USER_ID,
                email="recruiter-demo@brightcart.example",
                name="Recruiter Demo Customer",
            )
            db.add(user)
            db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

    existing_orders = get_user_orders_tool.invoke(
        {},
        config={"configurable": {"user_id": DEMO_USER_ID}},
    )
    if isinstance(existing_orders, list) and existing_orders:
        return

    db = SessionLocal()
    try:
        products = (
            db.query(Product)
            .filter(Product.stock > 0)
            .order_by(Product.prod_id)
            .limit(3)
            .all()
        )
        for product in products:
            place_order(db, DEMO_USER_ID, product.prod_id, 1)
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def _get_demo_ordered_products() -> list[dict]:
    _ensure_demo_customer()
    orders = get_user_orders_tool.invoke(
        {},
        config={"configurable": {"user_id": DEMO_USER_ID}},
    )
    if not isinstance(orders, list):
        return []

    db: Session = SessionLocal()
    try:
        ordered_products = []
        for order in orders:
            if order["status"].lower() == "cancelled":
                continue
            products = get_ordered_products(db, DEMO_USER_ID, order["order_id"])
            if isinstance(products, list):
                ordered_products.extend(
                    {
                        "name": product["Product_name"],
                        "quantity": product["quantity"],
                        "price": product["price"],
                    }
                    for product in products
                )
        return ordered_products
    finally:
        db.close()


# LANGFUSE INTEGRATION
from langfuse import get_client
from langfuse.langchain import CallbackHandler

langfuse = get_client()
langfuse_handler = CallbackHandler()


@router.post("/stream")
async def stream_chat(payload: ChatRequest, user_id: int = Depends(get_current_user_id)):
    _ensure_thread_exists(payload.thread_id, user_id)

    config = {
        "configurable": {
            "thread_id": payload.thread_id,
            "user_id": user_id,
        },
        "callbacks": [langfuse_handler],
    }

    def event_generator():
        result = agent.invoke(
            {"messages": HumanMessage(content=payload.message)},
            config=config,
        )

        # Update active_agent on the thread in PostgreSQL
        active_agent = result.get("active_agent")
        if active_agent:
            db_local = SessionLocal()
            try:
                t = db_local.query(Thread).filter(Thread.thread_id == payload.thread_id).first()
                if t:
                    t.active_agent = active_agent
                    db_local.commit()
            except Exception:
                db_local.rollback()
            finally:
                db_local.close()

        messages = result.get("messages", [])
        if messages and messages[-1].type == "ai" and messages[-1].content:
            content = _content_to_text(messages[-1].content)
            if content:
                yield content

    return StreamingResponse(event_generator(), media_type="text/plain")


@router.post("/demo-stream")
async def demo_stream_chat(payload: DemoChatRequest):
    _ensure_demo_customer()
    config = {
        "configurable": {
            "thread_id": f"demo-{payload.session_id}",
            "user_id": DEMO_USER_ID,
        },
        "callbacks": [langfuse_handler],
    }

    def event_generator():
        result = agent.invoke(
            {"messages": HumanMessage(content=payload.message)},
            config=config,
        )
        messages = result.get("messages", [])
        if messages and messages[-1].type == "ai" and messages[-1].content:
            content = _content_to_text(messages[-1].content)
            if content:
                yield content

    return StreamingResponse(event_generator(), media_type="text/plain")


@router.get("/demo-info")
def demo_info():
    return {
        "customer_id": DEMO_USER_ID,
        "ordered_products": _get_demo_ordered_products(),
    }


@router.get("/threads")
def list_threads(user_id: int = Depends(get_current_user_id)):
    db: Session = SessionLocal()
    try:
        threads = (
            db.query(Thread)
            .filter(Thread.user_id == user_id)
            .order_by(Thread.created_at.desc())
            .all()
        )
        thread_items = []
        for t in threads:
            tid_str = str(t.thread_id)
            agent_field = t.active_agent
            label = format_agent_label(agent_field)
            thread_items.append({
                "thread_id": tid_str,
                "active_agent": agent_field,
                "agent_name": label,
                "created_at": t.created_at.isoformat() if t.created_at else None,
            })
        return {
            "threads": thread_items,
            "thread_ids": [t["thread_id"] for t in thread_items],
        }
    finally:
        db.close()


@router.get("/threads/{thread_id}/agent")
def get_thread_agent(thread_id: str, user_id: int = Depends(get_current_user_id)):
    _verify_thread_owner(thread_id, user_id)
    db: Session = SessionLocal()
    try:
        t = db.query(Thread).filter(Thread.thread_id == thread_id).first()
        active_agent = t.active_agent if t else None
        return {
            "thread_id": thread_id,
            "active_agent": active_agent,
            "agent_name": format_agent_label(active_agent),
        }
    finally:
        db.close()


@router.get("/threads/{thread_id}/messages")
def get_thread_messages(thread_id: str, user_id: int = Depends(get_current_user_id)):
    _verify_thread_owner(thread_id, user_id)

    config = {"configurable": {"thread_id": thread_id}}
    state = agent.get_state(config=config)

    if not state or not state.values:
        return {"thread_id": thread_id, "active_agent": None, "agent_name": "Support", "messages": []}

    active_agent = state.values.get("active_agent")

    # Sync with DB if needed
    if active_agent:
        db_local = SessionLocal()
        try:
            t = db_local.query(Thread).filter(Thread.thread_id == thread_id).first()
            if t and not t.active_agent:
                t.active_agent = active_agent
                db_local.commit()
        except Exception:
            pass
        finally:
            db_local.close()

    messages = state.values.get("messages", [])
    formatted = [
        {"role": "user" if msg.type == "human" else "assistant", "content": _content_to_text(msg.content)}
        for msg in messages
    ]
    return {
        "thread_id": thread_id,
        "active_agent": active_agent,
        "agent_name": format_agent_label(active_agent),
        "messages": formatted,
    }


@router.delete("/threads/{thread_id}")
def delete_thread(thread_id: str, user_id: int = Depends(get_current_user_id)):
    _verify_thread_owner(thread_id, user_id)
    db: Session = SessionLocal()
    try:
        thread = db.query(Thread).filter(Thread.thread_id == thread_id).first()
        if thread:
            db.delete(thread)
            db.commit()
        return {"status": "success", "thread_id": thread_id}
    finally:
        db.close()
