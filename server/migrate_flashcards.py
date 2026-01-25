from sqlalchemy import create_engine, text
from dotenv import load_dotenv
import os

load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")

def migrate():
    engine = create_engine(DATABASE_URL)
    with engine.connect() as conn:
        print("Creating flashcards table...")
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS flashcards (
                id SERIAL PRIMARY KEY,
                argument_id INTEGER REFERENCES arguments(id),
                front TEXT,
                back TEXT,
                interval INTEGER DEFAULT 0,
                ease_factor INTEGER DEFAULT 250,
                reps INTEGER DEFAULT 0,
                due_date TIMESTAMP WITHOUT TIME ZONE DEFAULT (now() AT TIME ZONE 'utc'),
                state VARCHAR DEFAULT 'new'
            );
        """))
        conn.commit()
        print("Migration complete.")

if __name__ == "__main__":
    migrate()
