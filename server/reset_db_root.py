import sys
import os
sys.path.append(os.getcwd())

from app.database import SessionLocal
from sqlalchemy import text

def reset_db():
    print("Resetting database...")
    db = SessionLocal()
    try:
        # Truncate tables with cascade
        db.execute(text("TRUNCATE TABLE proofs, arguments, sources, definition_extractions, definition_sources RESTART IDENTITY CASCADE;"))
        db.commit()
        print("All tables truncated successfully.")
    except Exception as e:
        print(f"Error resetting DB: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    reset_db()
