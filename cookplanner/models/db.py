"""
Database setup and connection management for the cookbook meal planner.
Uses SQLite for simple, file-based storage.
"""

import sqlite3
from pathlib import Path
from typing import Optional
from contextlib import contextmanager

from cookplanner.config import Config


class Database:
    """Database connection and schema management."""

    def __init__(self, db_path: Optional[Path] = None):
        """
        Initialize database connection.

        Args:
            db_path: Path to the SQLite database file. If None, uses config default.
        """
        self.db_path = db_path or Config.get_db_path()

    @contextmanager
    def get_connection(self):
        """
        Context manager for database connections.
        Ensures connections are properly closed.
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row  # Enable dict-like access to rows
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def init_db(self):
        """Initialize the database schema."""
        # Ensure data directory exists
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        with self.get_connection() as conn:
            cursor = conn.cursor()

            # Recipes table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS recipes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title_jp TEXT NOT NULL,
                    title_en TEXT NOT NULL,
                    summary_en TEXT,
                    servings INTEGER DEFAULT 2,
                    tags_json TEXT,
                    source_file TEXT,
                    drive_file_id TEXT,
                    page_number INTEGER,
                    recipe_index INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Ingredients table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS ingredients (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    recipe_id INTEGER NOT NULL,
                    name_jp TEXT NOT NULL,
                    name_en TEXT NOT NULL,
                    quantity TEXT,
                    unit TEXT,
                    category TEXT,
                    sauce_reference TEXT,
                    FOREIGN KEY (recipe_id) REFERENCES recipes (id) ON DELETE CASCADE
                )
            """)

            # Instructions table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS instructions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    recipe_id INTEGER NOT NULL,
                    step_number INTEGER NOT NULL,
                    text_jp TEXT NOT NULL,
                    text_en TEXT NOT NULL,
                    FOREIGN KEY (recipe_id) REFERENCES recipes (id) ON DELETE CASCADE
                )
            """)

            # Sync files table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS sync_files (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    drive_file_id TEXT UNIQUE NOT NULL,
                    local_path TEXT NOT NULL,
                    last_modified TEXT NOT NULL,
                    sync_status TEXT NOT NULL,
                    file_type TEXT NOT NULL,
                    error_message TEXT,
                    synced_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Create indexes for better query performance
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_recipes_title_en
                ON recipes(title_en)
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_recipes_source
                ON recipes(source_file, page_number, recipe_index)
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_ingredients_recipe
                ON ingredients(recipe_id)
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_instructions_recipe
                ON instructions(recipe_id)
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_sync_files_drive_id
                ON sync_files(drive_file_id)
            """)

            conn.commit()

    def drop_all_tables(self):
        """Drop all tables. Use with caution!"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DROP TABLE IF EXISTS instructions")
            cursor.execute("DROP TABLE IF EXISTS ingredients")
            cursor.execute("DROP TABLE IF EXISTS recipes")
            cursor.execute("DROP TABLE IF EXISTS sync_files")
            conn.commit()

    def reset_db(self):
        """Drop all tables and reinitialize. Use with caution!"""
        self.drop_all_tables()
        self.init_db()


# Global database instance
db = Database()


def init_database(db_path: Optional[Path] = None):
    """
    Initialize the database schema.

    Args:
        db_path: Optional path to database file. Uses config default if not provided.
    """
    database = Database(db_path)
    database.init_db()
    return database


def get_db() -> Database:
    """Get the global database instance."""
    return db
