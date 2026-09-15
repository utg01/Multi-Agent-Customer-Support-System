from fastapi import APIRouter
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.db.base import SessionLocal  
from app.core.db.models import User  

router = APIRouter(prefix="/auth", tags=["auth"])


class GoogleSyncRequest(BaseModel):
    email: str
    google_sub: str
    name: str | None = None


@router.post("/google-sync")
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
        return {"user_id": user.user_id}
    finally:
        db.close()