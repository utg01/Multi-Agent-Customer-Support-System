"""
Authentication helpers.

1. /auth/google-sync ko sirf apna Streamlit server hi call kar sakta hai
   (shared secret ke through).
2. Har /chat/* call ko ek signed session token chahiye — user_id kabhi
   bhi client se accept nahi hota.
"""
import os
import time

from dotenv import load_dotenv
from fastapi import Header, HTTPException
from joserfc import jwt
from joserfc.jwk import OctKey
from joserfc.jwt import JWTClaimsRegistry
from joserfc.errors import JoseError

load_dotenv()

INTERNAL_SERVICE_SECRET = os.environ["INTERNAL_SERVICE_SECRET"]
_SESSION_KEY = OctKey.import_key(os.environ["SESSION_SECRET"])

SESSION_TTL_SECONDS = 60 * 60 * 8  # 8 hour session
_claims_registry = JWTClaimsRegistry()


def require_internal_caller(x_internal_secret: str = Header(...)) -> None:
    if x_internal_secret != INTERNAL_SERVICE_SECRET:
        raise HTTPException(status_code=403, detail="Forbidden")


def create_session_token(user_id: int) -> str:
    header = {"typ": "JWT", "alg": "HS256"}
    payload = {"user_id": user_id, "exp": int(time.time()) + SESSION_TTL_SECONDS}
    return jwt.encode(header, payload, _SESSION_KEY)


def get_current_user_id(authorization: str = Header(...)) -> int:
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token")
    token = authorization.removeprefix("Bearer ")
    try:
        decoded = jwt.decode(token, _SESSION_KEY)
        _claims_registry.validate(decoded.claims)
    except JoseError:
        raise HTTPException(status_code=401, detail="Invalid or expired session")
    return decoded.claims["user_id"]