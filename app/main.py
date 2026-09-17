import os

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.chat import router as chat_router
from app.api.auth import router as auth_router

load_dotenv()

app = FastAPI(title="BrightCart Support API")

FRONTEND_ORIGIN = os.getenv("FRONTEND_ORIGIN", "http://localhost:8501")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[FRONTEND_ORIGIN],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(chat_router)
app.include_router(auth_router)


@app.get("/health")
def health():
    return {"status": "ok"}