"""
Migration script to update flashcards table from old SM-2 schema to new FSRS schema.

This script will:
1. Add new FSRS columns (stability, difficulty, scheduled_days, last_review, lapses, step)
2. Convert existing card states from string to integer
3. Migrate existing ease_factor to difficulty
4. Remove old columns (ease_factor, interval)

Run this script once to migrate existing data.
"""

import sqlite3
import os
from datetime import datetime

# Database path
DB_PATH = os.path.join(os.path.dirname(__file__), "app", "eps_bot.db")

def migrate_flashcards_to_fsrs():
    """Migrate flashcards table to FSRS schema."""

    print(f"[{datetime.now()}] Starting FSRS migration...")
    print(f"Database: {DB_PATH}")

    if not os.path.exists(DB_PATH):
        print("Database not found! Creating fresh database with FSRS schema...")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:
        # Check current schema
        cursor.execute("PRAGMA table_info(flashcards)")
        columns = {row[1]: row[2] for row in cursor.fetchall()}
        print(f"Current columns: {list(columns.keys())}")

        # Step 1: Add new FSRS columns if they don't exist
        new_columns = {
            'stability': 'INTEGER DEFAULT 0',
            'difficulty': 'INTEGER DEFAULT 0',
            'scheduled_days': 'INTEGER DEFAULT 0',
            'last_review': 'TIMESTAMP',
            'lapses': 'INTEGER DEFAULT 0',
            'step': 'INTEGER DEFAULT 0'
        }

        for col_name, col_type in new_columns.items():
            if col_name not in columns:
                print(f"Adding column: {col_name}")
                cursor.execute(f"ALTER TABLE flashcards ADD COLUMN {col_name} {col_type}")

        conn.commit()

        # Step 2: Convert existing string states to integers
        # Old: 'new', 'learning', 'review', 'relearning'
        # New: 0, 1, 2, 3

        # Check if state column is string type
        cursor.execute("SELECT DISTINCT state FROM flashcards LIMIT 10")
        sample_states = cursor.fetchall()
        print(f"Sample states: {sample_states}")

        if sample_states and isinstance(sample_states[0][0], str):
            print("Converting state strings to integers...")

            # Create a temporary column for the new state
            cursor.execute("ALTER TABLE flashcards ADD COLUMN state_new INTEGER DEFAULT 0")

            # Map old states to new
            cursor.execute("""
                UPDATE flashcards SET state_new = CASE
                    WHEN state = 'new' THEN 0
                    WHEN state = 'learning' THEN 1
                    WHEN state = 'review' THEN 2
                    WHEN state = 'relearning' THEN 3
                    ELSE 0
                END
            """)

            conn.commit()

            # We can't drop the old column in SQLite easily, so we'll create a new table
            print("Recreating table with new schema...")

            cursor.execute("""
                CREATE TABLE flashcards_new (
                    id INTEGER PRIMARY KEY,
                    argument_id INTEGER REFERENCES arguments(id),
                    front TEXT,
                    back TEXT,
                    state INTEGER DEFAULT 0,
                    stability INTEGER DEFAULT 0,
                    difficulty INTEGER DEFAULT 0,
                    scheduled_days INTEGER DEFAULT 0,
                    due_date TIMESTAMP,
                    last_review TIMESTAMP,
                    reps INTEGER DEFAULT 0,
                    lapses INTEGER DEFAULT 0,
                    step INTEGER DEFAULT 0
                )
            """)

            # Copy data
            cursor.execute("""
                INSERT INTO flashcards_new (id, argument_id, front, back, state, stability, difficulty, scheduled_days, due_date, last_review, reps, lapses, step)
                SELECT
                    id,
                    argument_id,
                    front,
                    back,
                    state_new,
                    COALESCE(stability, 0),
                    CASE
                        WHEN ease_factor IS NOT NULL THEN (ease_factor - 100) * 10 / 15
                        ELSE 0
                    END,
                    COALESCE(interval, 0),
                    due_date,
                    last_review,
                    COALESCE(reps, 0),
                    COALESCE(lapses, 0),
                    COALESCE(step, 0)
                FROM flashcards
            """)

            # Drop old table and rename new one
            cursor.execute("DROP TABLE flashcards")
            cursor.execute("ALTER TABLE flashcards_new RENAME TO flashcards")

            # Recreate index
            cursor.execute("CREATE INDEX IF NOT EXISTS ix_flashcards_id ON flashcards (id)")

            conn.commit()
            print("Table recreated successfully!")

        else:
            # State is already integer, just migrate ease_factor to difficulty
            print("State column is already integer format.")

            # Check if we need to migrate ease_factor
            if 'ease_factor' in columns and 'difficulty' in columns:
                print("Migrating ease_factor to difficulty...")
                # ease_factor was 130-400 (representing 1.3-4.0)
                # difficulty should be 100-1000 (representing 1.0-10.0)
                # Inverse relationship: higher ease = lower difficulty
                cursor.execute("""
                    UPDATE flashcards
                    SET difficulty = CASE
                        WHEN ease_factor IS NOT NULL AND ease_factor > 0
                        THEN MAX(100, MIN(1000, (400 - ease_factor) * 10 / 3 + 500))
                        ELSE 500
                    END
                    WHERE difficulty = 0 OR difficulty IS NULL
                """)
                conn.commit()

        # Step 3: Set default values for any null fields
        print("Setting default values for null fields...")

        cursor.execute("""
            UPDATE flashcards
            SET
                stability = COALESCE(stability, 0),
                difficulty = COALESCE(difficulty, 500),
                scheduled_days = COALESCE(scheduled_days, 0),
                reps = COALESCE(reps, 0),
                lapses = COALESCE(lapses, 0),
                step = COALESCE(step, 0)
        """)

        conn.commit()

        # Step 4: Verify migration
        cursor.execute("SELECT COUNT(*) FROM flashcards")
        total = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM flashcards WHERE state IN (0, 1, 2, 3)")
        valid_states = cursor.fetchone()[0]

        print(f"\nMigration complete!")
        print(f"Total flashcards: {total}")
        print(f"Cards with valid state: {valid_states}")

        # Show final schema
        cursor.execute("PRAGMA table_info(flashcards)")
        final_columns = cursor.fetchall()
        print("\nFinal schema:")
        for col in final_columns:
            print(f"  {col[1]}: {col[2]}")

    except Exception as e:
        print(f"Migration error: {e}")
        conn.rollback()
        raise
    finally:
        conn.close()

if __name__ == "__main__":
    migrate_flashcards_to_fsrs()
