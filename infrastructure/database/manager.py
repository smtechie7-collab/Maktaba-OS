import sqlite3
from pathlib import Path
from typing import List, Dict, Any, Optional

from core.schema.document import DocumentRoot
from core.engine.document_engine import DocumentEngine
from core.schema.schema import SCHEMA_SQL, SCHEMA_VERSION

class DatabaseManager:
    """
    Manages the SQLite database connection and operations.
    Complies with Law 1: Acts as a dumb storage layer for serialized Document Models.
    """
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        with self._get_connection() as conn:
            conn.executescript(SCHEMA_SQL)
            
            # Check and set schema version
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='_schema_version'")
            if cursor.fetchone() is None:
                 # For brand new DBs
                conn.executescript(SCHEMA_SQL) # Ensure all tables are there
                cursor.execute("INSERT INTO _schema_version (version) VALUES (?)", (SCHEMA_VERSION,))
            else:
                cursor.execute("SELECT version FROM _schema_version")
                version_row = cursor.fetchone()
                if version_row is None:
                    cursor.execute("INSERT INTO _schema_version (version) VALUES (?)", (SCHEMA_VERSION,))
                elif version_row['version'] < SCHEMA_VERSION:
                    # Here you would place migration logic for future schema changes
                    cursor.execute("UPDATE _schema_version SET version = ?", (SCHEMA_VERSION,))
            conn.commit()

    def create_book(self, title: str, author: Optional[str] = None) -> int:
        """
        Creates a new book metadata entry and an associated empty document.
        Returns the new book's ID.
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("INSERT INTO Books (title, author) VALUES (?, ?)", (title, author))
            book_id = cursor.lastrowid
            
            empty_doc = DocumentEngine.create_empty_document()
            doc_json = DocumentEngine.export_to_json(empty_doc)
            
            cursor.execute(
                "INSERT INTO Documents (book_id, content_json) VALUES (?, ?)",
                (book_id, doc_json)
            )
            conn.commit()
            return book_id

    def save_document(self, book_id: int, document: DocumentRoot) -> bool:
        """
        Saves a validated DocumentRoot object to the database, overwriting the existing one.
        This is the primary method for persisting content.
        """
        doc_json = DocumentEngine.export_to_json(document)
        
        with self._get_connection() as conn:
            cursor = conn.execute(
                "UPDATE Documents SET content_json = ?, version = version + 1 WHERE book_id = ?",
                (doc_json, book_id)
            )
            conn.commit()
            return cursor.rowcount == 1

    def get_document_version(self, book_id: int) -> Optional[int]:
        """Return the current persisted document version for a book."""
        with self._get_connection() as conn:
            row = conn.execute(
                "SELECT version FROM Documents WHERE book_id = ?",
                (book_id,),
            ).fetchone()
            return row["version"] if row else None

    def load_document(self, book_id: int) -> Optional[DocumentRoot]:
        """Loads a document from the database and validates it into a DocumentRoot object."""
        with self._get_connection() as conn:
            # Check if book is active
            book_row = conn.execute("SELECT id FROM Books WHERE id = ? AND is_active = 1", (book_id,)).fetchone()
            if not book_row:
                return None
            row = conn.execute("SELECT content_json FROM Documents WHERE book_id = ?", (book_id,)).fetchone()
            if row and row['content_json']:
                return DocumentEngine.load_from_json(row['content_json'])
        return None

    def list_books(self) -> List[Dict[str, Any]]:
        """Lists all books' metadata for display in a UI."""
        with self._get_connection() as conn:
            books = conn.execute("SELECT id, title, author, created_at, updated_at FROM Books WHERE is_active = 1 ORDER BY updated_at DESC").fetchall()
            return [dict(book) for book in books]

    def delete_book(self, book_id: int):
        """Marks a book as inactive (soft delete)."""
        with self._get_connection() as conn:
            conn.execute("UPDATE Books SET is_active = 0 WHERE id = ?", (book_id,))
            conn.commit()
