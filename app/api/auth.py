from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.db.base import SessionLocal  
from app.core.db.models import User  
from app.core.security import require_internal_caller, create_session_token

router = APIRouter(prefix="/auth", tags=["auth"])


class GoogleSyncRequest(BaseModel):
    email: str
    google_sub: str
    name: str | None = None


@router.post("/google-sync", dependencies=[Depends(require_internal_caller)])
def google_sync(payload: GoogleSyncRequest):
    db: Session = SessionLocal()
    try:
        user = (
            db.query(User)
            .filter((User.google_sub_id == payload.google_sub) | (User.email == payload.email))
            .first()
        )

        if user:
            user.google_sub_id = payload.google_sub
            user.name = payload.name
        else:
            user = User(
                email=payload.email,
                google_sub_id=payload.google_sub,
                name=payload.name,
            )
            db.add(user)

        db.commit()
        db.refresh(user)

        session_token = create_session_token(user.user_id)
        return {"session_token": session_token}
    finally:
        db.close()