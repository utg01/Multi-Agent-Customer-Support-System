import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
if DATABASE_URL:
    for scheme in ("postgresql+psycopg2://", "postgres+psycopg2://", "postgresql://", "postgres://"):
        if DATABASE_URL.startswith(scheme):
            DATABASE_URL = "postgresql+psycopg://" + DATABASE_URL[len(scheme):]
            break

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()