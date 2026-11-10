import json
import base64
import os
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.db.base import SessionLocal  
from app.core.db.models import User  
from app.core.security import require_internal_caller, create_session_token, get_current_user_id

router = APIRouter(prefix="/auth", tags=["auth"])


class GoogleSyncRequest(BaseModel):
    email: str
    google_sub: str
    name: str | None = None


class GoogleLoginRequest(BaseModel):
    credential: str | None = None
    email: str | None = None
    google_sub: str | None = None
    name: str | None = None


def _parse_jwt_payload_unverified(token: str) -> dict:
    """Extract claims from a JWT token without external network calls (for email/sub extraction)."""
    parts = token.split(".")
    if len(parts) < 2:
        raise ValueError("Invalid JWT format")
    payload_b64 = parts[1]
    # Add padding if needed
    remainder = len(payload_b64) % 4
    if remainder > 0:
        payload_b64 += "=" * (4 - remainder)
    decoded_bytes = base64.urlsafe_b64decode(payload_b64)
    return json.loads(decoded_bytes.decode("utf-8"))


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
            user.name = payload.name or user.name or "Customer"
        else:
            user = User(
                email=payload.email,
                google_sub_id=payload.google_sub,
                name=payload.name or "Customer",
            )
            db.add(user)

        db.commit()
        db.refresh(user)

        session_token = create_session_token(user.user_id)
        return {"session_token": session_token}
    finally:
        db.close()


@router.post("/google-login")
def google_login(payload: GoogleLoginRequest):
    """Direct Google authentication endpoint for the web frontend."""
    email = payload.email
    google_sub = payload.google_sub
    name = payload.name

    # If raw Google credential was sent
    if payload.credential:
        try:
            claims = _parse_jwt_payload_unverified(payload.credential)
            email = claims.get("email") or email
            google_sub = str(claims.get("sub")) if claims.get("sub") else google_sub
            name = claims.get("name") or claims.get("given_name") or name
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Invalid Google credential: {str(e)}")

    if not email:
        raise HTTPException(status_code=400, detail="Email is required for Google login")

    google_sub = google_sub or f"google_{email.replace('@', '_').replace('.', '_')}"
    name = name or email.split("@")[0].capitalize()

    db: Session = SessionLocal()
    try:
        user = (
            db.query(User)
            .filter((User.google_sub_id == google_sub) | (User.email == email))
            .first()
        )

        if user:
            if google_sub:
                user.google_sub_id = google_sub
            if name:
                user.name = name
        else:
            user = User(
                email=email,
                google_sub_id=google_sub,
                name=name,
            )
            db.add(user)

        db.commit()
        db.refresh(user)

        session_token = create_session_token(user.user_id)
        return {
            "session_token": session_token,
            "user": {
                "user_id": user.user_id,
                "email": user.email,
                "name": user.name,
            }
        }
    finally:
        db.close()


@router.get("/me")
def get_me(user_id: int = Depends(get_current_user_id)):
    db: Session = SessionLocal()
    try:
        user = db.query(User).filter(User.user_id == user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        return {
            "user_id": user.user_id,
            "email": user.email,
            "name": user.name,
        }
    finally:
        db.close()
