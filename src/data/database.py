import sqlite3
import json
import os
import sys
from pathlib import Path
from typing import Dict, Any, List, Optional, Callable

# Add root to path for imports
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
from src.core.paths import database_path
from src.utils.logger import setup_logger

logger = setup_logger("Database")

class DatabaseManager:
    CURRENT_SCHEMA_VERSION = 2

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = str(Path(db_path).expanduser().resolve()) if db_path else str(database_path())
        self._init_db()

    def _get_connection(self):
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.db_path, timeout=5.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA busy_timeout=5000")
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        return conn

    def _init_db(self):
        """Initialize the database and apply versioned migrations."""
        logger.info(f"Initializing database at {self.db_path}")
        with self._get_connection() as conn:
            self._ensure_migration_table(conn)
            self._run_migrations(conn)
            conn.commit()

    def _ensure_migration_table(self, conn: sqlite3.Connection) -> None:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

    def _schema_version(self, conn: sqlite3.Connection) -> int:
        row = conn.execute("SELECT COALESCE(MAX(version), 0) AS version FROM schema_migrations").fetchone()
        return int(row["version"] if row else 0)

    def _run_migrations(self, conn: sqlite3.Connection) -> None:
        migrations: List[tuple[int, str, Callable[[sqlite3.Connection], None]]] = [
            (1, "initial_schema", self._migration_001_initial_schema),
            (2, "add_chapter_type", self._migration_002_add_chapter_type),
        ]
        current_version = self._schema_version(conn)

        for version, name, migration in migrations:
            if version <= current_version:
                continue
            logger.info(f"Applying database migration {version}: {name}")
            migration(conn)
            conn.execute(
                "INSERT INTO schema_migrations (version, name) VALUES (?, ?)",
                (version, name),
            )

    def _migration_001_initial_schema(self, conn: sqlite3.Connection) -> None:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS Books (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                author TEXT,
                language TEXT DEFAULT 'en',
                metadata JSON,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS Chapters (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                book_id INTEGER,
                title TEXT NOT NULL,
                sequence_number INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (book_id) REFERENCES Books (id) ON DELETE CASCADE
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS Content_Blocks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chapter_id INTEGER,
                content_type TEXT DEFAULT 'text',
                content_data JSON NOT NULL,
                version INTEGER DEFAULT 1,
                is_active BOOLEAN DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (chapter_id) REFERENCES Chapters (id) ON DELETE CASCADE
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS Footnotes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                block_id INTEGER,
                marker TEXT,
                content JSON NOT NULL,
                FOREIGN KEY (block_id) REFERENCES Content_Blocks (id) ON DELETE CASCADE
            )
        """)

    def _migration_002_add_chapter_type(self, conn: sqlite3.Connection) -> None:
        columns = {
            row["name"]
            for row in conn.execute("PRAGMA table_info(Chapters)").fetchall()
        }
        if "chapter_type" not in columns:
            conn.execute("ALTER TABLE Chapters ADD COLUMN chapter_type TEXT DEFAULT 'Content Chapter'")

    def add_book(self, title: str, author: str = None, language: str = 'en', metadata: Dict = None) -> int:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO Books (title, author, language, metadata) VALUES (?, ?, ?, ?)",
                (title, author, language, json.dumps(metadata) if metadata else None)
            )
            return cursor.lastrowid

    def add_chapter(self, book_id: int, title: str, sequence: int, chapter_type: str = 'Content Chapter') -> int:
        """Add a chapter with its specific anatomy type."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO Chapters (book_id, title, sequence_number, chapter_type) VALUES (?, ?, ?, ?)",
                (book_id, title, sequence, chapter_type)
            )
            return cursor.lastrowid

    def add_content_block(self, chapter_id: int, content_data: Dict[str, Any], content_type: str = 'text') -> int:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO Content_Blocks (chapter_id, content_type, content_data) VALUES (?, ?, ?)",
                (chapter_id, content_type, json.dumps(content_data))
            )
            return cursor.lastrowid

    def add_footnote(self, block_id: int, content: Dict[str, Any], marker: str = None) -> int:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO Footnotes (block_id, marker, content) VALUES (?, ?, ?)",
                (block_id, marker, json.dumps(content))
            )
            return cursor.lastrowid

    def get_book_content(self, book_id: int) -> List[Dict[str, Any]]:
        """Fetch all chapters and content, optimized. LEFT JOIN ensures empty chapters (like Covers) are loaded too."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            query = '''
                SELECT c.id as chapter_id, c.title as chapter_title, c.chapter_type,
                       cb.id as block_id, cb.content_data, cb.content_type
                FROM Chapters c
                LEFT JOIN Content_Blocks cb ON c.id = cb.chapter_id AND cb.is_active = 1
                WHERE c.book_id = ?
                ORDER BY c.sequence_number ASC, cb.id ASC
            '''
            cursor.execute(query, (book_id,))
            blocks = [dict(row) for row in cursor.fetchall()]
            
            if not blocks: return []

            # Attach footnotes
            valid_block_ids = [b['block_id'] for b in blocks if b['block_id'] is not None]
            if valid_block_ids:
                placeholders = ', '.join(['?'] * len(valid_block_ids))
                fn_query = f"SELECT block_id, marker, content FROM Footnotes WHERE block_id IN ({placeholders})"
                cursor.execute(fn_query, valid_block_ids)
                
                footnotes_map = {}
                for fn in cursor.fetchall():
                    bid = fn['block_id']
                    if bid not in footnotes_map: footnotes_map[bid] = []
                    footnotes_map[bid].append({"marker": fn['marker'], "content": json.loads(fn['content'])})
                
                for block in blocks:
                    if block['block_id']:
                        block['footnotes'] = footnotes_map.get(block['block_id'], [])
                    else:
                        block['footnotes'] = []
            else:
                for block in blocks: block['footnotes'] = []
                
            return blocks
