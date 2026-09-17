from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from langchain_core.messages import HumanMessage, AIMessageChunk
from sqlalchemy.orm import Session

from app.agent.agent import agent
from app.core.db.base import SessionLocal
from app.core.db.models import Thread
from app.core.security import get_current_user_id

router = APIRouter(prefix="/chat", tags=["chat"])


class ChatRequest(BaseModel):
    thread_id: str
    message: str


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


@router.post("/stream")
async def stream_chat(payload: ChatRequest, user_id: int = Depends(get_current_user_id)):
    _ensure_thread_exists(payload.thread_id, user_id)

    config = {
        "configurable": {
            "thread_id": payload.thread_id,
            "user_id": user_id,
        }
    }

    def event_generator():
        yielded_any = False

        for namespace, (message_chunk, metadata) in agent.stream(
            {"messages": HumanMessage(content=payload.message)},
            config=config,
            stream_mode="messages",
            subgraphs=True,
        ):
            if isinstance(message_chunk, AIMessageChunk) and message_chunk.content:
                yielded_any = True
                yield message_chunk.content

        if not yielded_any:
            state = agent.get_state(config=config)
            messages = state.values.get("messages", [])
            if messages and messages[-1].type == "ai" and messages[-1].content:
                yield messages[-1].content

    return StreamingResponse(event_generator(), media_type="text/plain")


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