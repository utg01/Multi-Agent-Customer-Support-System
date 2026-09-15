from app.core.db.base import Base, engine
from app.core.db import models  # noqa: F401 - registers all models

if __name__ == "__main__":
    print("Creating tables...")
    Base.metadata.create_all(bind=engine)
    print("Done. Check Supabase dashboard -> Table Editor to confirm.")