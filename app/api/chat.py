from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from langchain_core.messages import HumanMessage
from sqlalchemy.orm import Session

from app.agent.agent import agent
from app.core.db.base import SessionLocal
from app.core.db.models import User, Product, Order, OrderItem, Thread
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


def _ensure_demo_customer() -> list[dict]:
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
            db.flush()

        demo_order = db.query(Order).filter(Order.user_id == DEMO_USER_ID).first()
        if not demo_order:
            product_specs = [
                ("Wireless Headphones", "Bluetooth over-ear headphones", 79.99, "Electronics"),
                ("Travel Backpack", "Water-resistant everyday backpack", 49.99, "Accessories"),
                ("USB-C Charging Cable", "Durable fast-charging cable", 14.99, "Electronics"),
            ]
            products = []
            for name, description, price, category in product_specs:
                product = db.query(Product).filter(Product.name == name).first()
                if not product:
                    product = Product(
                        name=name,
                        description=description,
                        price=price,
                        stock=25,
                        category=category,
                    )
                    db.add(product)
                    db.flush()
                products.append(product)

            demo_order = Order(
                user_id=DEMO_USER_ID,
                status="placed",
                total_amount=sum(product.price for product in products),
            )
            db.add(demo_order)
            db.flush()
            for product in products:
                db.add(
                    OrderItem(
                        order_id=demo_order.order_id,
                        product_id=product.prod_id,
                        quantity=1,
                        price_at_purchase=product.price,
                    )
                )
            db.commit()
        else:
            db.commit()

        items = (
            db.query(OrderItem, Product)
            .join(Product, Product.prod_id == OrderItem.product_id)
            .filter(OrderItem.order_id == demo_order.order_id)
            .all()
        )
        return [
            {
                "name": product.name,
                "quantity": item.quantity,
                "price": item.price_at_purchase,
            }
            for item, product in items
        ]
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


#LANGFUSE INTEGRATION

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
        'callbacks':[langfuse_handler],
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
        "ordered_products": _ensure_demo_customer(),
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
        return {"thread_ids": [str(t.thread_id) for t in threads]}
    finally:
        db.close()


@router.get("/threads/{thread_id}/messages")
def get_thread_messages(thread_id: str, user_id: int = Depends(get_current_user_id)):
    _verify_thread_owner(thread_id, user_id)

    config = {"configurable": {"thread_id": thread_id}}
    state = agent.get_state(config=config)

    if not state or not state.values:
        raise HTTPException(status_code=404, detail="Thread not found")

    messages = state.values.get("messages", [])
    formatted = [
        {"role": "user" if msg.type == "human" else "assistant", "content": msg.content}
        for msg in messages
    ]
    return {"thread_id": thread_id, "messages": formatted}