import sqlite3
import logging
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
            # Check current schema version
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='_schema_version'")
            has_version_table = cursor.fetchone() is not None

            if not has_version_table:
                # Brand new database - create everything
                conn.executescript(SCHEMA_SQL)
                cursor.execute("INSERT INTO _schema_version (version) VALUES (?)", (SCHEMA_VERSION,))
            else:
                cursor.execute("SELECT version FROM _schema_version")
                version_row = cursor.fetchone()
                current_version = version_row['version'] if version_row else 0

                if current_version < SCHEMA_VERSION:
                    self._migrate_schema(conn, current_version, SCHEMA_VERSION)
                    cursor.execute("UPDATE _schema_version SET version = ?", (SCHEMA_VERSION,))
                elif current_version > SCHEMA_VERSION:
                    raise RuntimeError(f"Database schema version {current_version} is newer than supported version {SCHEMA_VERSION}")

            conn.commit()

    def _migrate_schema(self, conn: sqlite3.Connection, from_version: int, to_version: int):
        """Migrate database schema from one version to another."""
        logger = logging.getLogger(__name__)

        if from_version == 1 and to_version == 2:
            logger.info("Migrating database from version 1 to 2 (adding multi-user support)")

            # Add new tables for multi-user support
            migration_sql = """
            -- User accounts for multi-user support
            CREATE TABLE IF NOT EXISTS Users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                email TEXT UNIQUE,
                display_name TEXT,
                password_hash TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_login TIMESTAMP,
                is_active INTEGER DEFAULT 1
            );

            -- Roles for RBAC (Role-Based Access Control)
            CREATE TABLE IF NOT EXISTS Roles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                description TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            -- User-Role assignments
            CREATE TABLE IF NOT EXISTS UserRoles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                role_id INTEGER NOT NULL,
                assigned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                assigned_by INTEGER,
                FOREIGN KEY (user_id) REFERENCES Users(id) ON DELETE CASCADE,
                FOREIGN KEY (role_id) REFERENCES Roles(id) ON DELETE CASCADE,
                FOREIGN KEY (assigned_by) REFERENCES Users(id),
                UNIQUE(user_id, role_id)
            );

            -- Permissions for granular access control
            CREATE TABLE IF NOT EXISTS Permissions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                description TEXT,
                resource_type TEXT NOT NULL,
                action TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            -- Role-Permission assignments
            CREATE TABLE IF NOT EXISTS RolePermissions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                role_id INTEGER NOT NULL,
                permission_id INTEGER NOT NULL,
                granted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                granted_by INTEGER,
                FOREIGN KEY (role_id) REFERENCES Roles(id) ON DELETE CASCADE,
                FOREIGN KEY (permission_id) REFERENCES Permissions(id) ON DELETE CASCADE,
                FOREIGN KEY (granted_by) REFERENCES Users(id),
                UNIQUE(role_id, permission_id)
            );

            -- Book ownership and sharing
            CREATE TABLE IF NOT EXISTS BookOwnership (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                book_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                ownership_type TEXT NOT NULL,
                granted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                granted_by INTEGER NOT NULL,
                FOREIGN KEY (book_id) REFERENCES Books(id) ON DELETE CASCADE,
                FOREIGN KEY (user_id) REFERENCES Users(id) ON DELETE CASCADE,
                FOREIGN KEY (granted_by) REFERENCES Users(id),
                UNIQUE(book_id, user_id)
            );

            -- Add new columns to existing tables (check if they exist first)
            -- Note: SQLite doesn't support IF NOT EXISTS for ALTER TABLE, so we check manually

            -- Document locking for collaborative editing
            CREATE TABLE IF NOT EXISTS DocumentLocks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                document_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                lock_type TEXT NOT NULL,
                locked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                expires_at TIMESTAMP,
                FOREIGN KEY (document_id) REFERENCES Documents(id) ON DELETE CASCADE,
                FOREIGN KEY (user_id) REFERENCES Users(id) ON DELETE CASCADE,
                UNIQUE(document_id, user_id)
            );

            -- Audit log for compliance and tracking
            CREATE TABLE IF NOT EXISTS AuditLog (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                action TEXT NOT NULL,
                resource_type TEXT NOT NULL,
                resource_id INTEGER,
                details TEXT,
                ip_address TEXT,
                user_agent TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES Users(id)
            );

            -- Insert default roles
            INSERT OR IGNORE INTO Roles (name, description) VALUES
            ('admin', 'Full system access'),
            ('author', 'Can create and edit books'),
            ('reviewer', 'Can review and comment on books'),
            ('viewer', 'Read-only access to shared books');

            -- Insert default permissions
            INSERT OR IGNORE INTO Permissions (name, description, resource_type, action) VALUES
            ('book.create', 'Create new books', 'book', 'create'),
            ('book.read', 'Read book metadata', 'book', 'read'),
            ('book.write', 'Edit book content', 'book', 'write'),
            ('book.delete', 'Delete books', 'book', 'delete'),
            ('book.share', 'Share books with others', 'book', 'share'),
            ('document.lock', 'Lock documents for editing', 'document', 'lock'),
            ('user.manage', 'Manage user accounts', 'user', 'manage'),
            ('role.assign', 'Assign roles to users', 'role', 'assign');

            -- Assign permissions to default roles
            INSERT OR IGNORE INTO RolePermissions (role_id, permission_id)
            SELECT r.id, p.id FROM Roles r, Permissions p
            WHERE (r.name = 'admin' AND p.name IN ('book.create', 'book.read', 'book.write', 'book.delete', 'book.share', 'document.lock', 'user.manage', 'role.assign'))
               OR (r.name = 'author' AND p.name IN ('book.create', 'book.read', 'book.write', 'book.share', 'document.lock'))
               OR (r.name = 'reviewer' AND p.name IN ('book.read', 'document.lock'))
               OR (r.name = 'viewer' AND p.name IN ('book.read'));
            """

            conn.executescript(migration_sql)
            logger.info("Database migration to version 2 completed successfully")
        else:
            raise RuntimeError(f"No migration path available from version {from_version} to {to_version}")

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

    # User Management Methods

    def create_book_for_user(self, title: str, author: Optional[str] = None, created_by: Optional[int] = None) -> int:
        """
        Creates a new book metadata entry with user ownership.
        Returns the new book's ID.
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("INSERT INTO Books (title, author, created_by) VALUES (?, ?, ?)", (title, author, created_by))
            book_id = cursor.lastrowid

            empty_doc = DocumentEngine.create_empty_document()
            doc_json = DocumentEngine.export_to_json(empty_doc)

            cursor.execute(
                "INSERT INTO Documents (book_id, content_json) VALUES (?, ?)",
                (book_id, doc_json)
            )

            # Grant ownership to the creator
            if created_by:
                cursor.execute("""
                    INSERT INTO BookOwnership (book_id, user_id, ownership_type, granted_by)
                    VALUES (?, ?, 'owner', ?)
                """, (book_id, created_by, created_by))

            conn.commit()
            return book_id

    def list_books_for_user(self, user_id: int) -> List[Dict[str, Any]]:
        """Lists all books accessible to a user."""
        with self._get_connection() as conn:
            # Get books owned by user or shared with user
            books = conn.execute("""
                SELECT DISTINCT b.id, b.title, b.author, b.created_at, b.updated_at,
                       bo.ownership_type, b.is_public
                FROM Books b
                LEFT JOIN BookOwnership bo ON b.id = bo.book_id AND bo.user_id = ?
                WHERE b.is_active = 1
                AND (bo.user_id IS NOT NULL OR b.is_public = 1 OR b.created_by = ?)
                ORDER BY b.updated_at DESC
            """, (user_id, user_id)).fetchall()
            return [dict(book) for book in books]

    def can_user_access_book(self, user_id: int, book_id: int, action: str = 'read') -> bool:
        """Check if a user can perform an action on a book."""
        with self._get_connection() as conn:
            # Check ownership/sharing
            row = conn.execute("""
                SELECT ownership_type FROM BookOwnership
                WHERE book_id = ? AND user_id = ?
            """, (book_id, user_id)).fetchone()

            if row:
                ownership_type = row[0]
                if ownership_type == 'owner':
                    return True
                elif ownership_type == 'editor' and action in ['read', 'write']:
                    return True
                elif ownership_type == 'viewer' and action == 'read':
                    return True

            # Check if book is public
            row = conn.execute("""
                SELECT is_public, created_by FROM Books WHERE id = ?
            """, (book_id,)).fetchone()

            if row and (row[0] or row[1] == user_id):  # Public or created by user
                return action == 'read'

            return False

    def save_document_with_user(self, book_id: int, document: DocumentRoot, user_id: int) -> bool:
        """
        Saves a document with user tracking.
        """
        if not self.can_user_access_book(user_id, book_id, 'write'):
            return False

        doc_json = DocumentEngine.export_to_json(document)

        with self._get_connection() as conn:
            cursor = conn.execute(
                "UPDATE Documents SET content_json = ?, version = version + 1, last_modified_by = ?, last_modified_at = CURRENT_TIMESTAMP WHERE book_id = ?",
                (doc_json, user_id, book_id)
            )
            conn.commit()
            return cursor.rowcount == 1

    def share_book(self, book_id: int, target_user_id: int, ownership_type: str, granted_by: int) -> bool:
        """Share a book with another user."""
        if not self.can_user_access_book(granted_by, book_id, 'share'):
            return False

        try:
            with self._get_connection() as conn:
                conn.execute("""
                    INSERT INTO BookOwnership (book_id, user_id, ownership_type, granted_by)
                    VALUES (?, ?, ?, ?)
                """, (book_id, target_user_id, ownership_type, granted_by))
                conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False  # Already shared

    def lock_document(self, document_id: int, user_id: int, lock_type: str = 'exclusive') -> bool:
        """Lock a document for editing."""
        try:
            with self._get_connection() as conn:
                conn.execute("""
                    INSERT INTO DocumentLocks (document_id, user_id, lock_type)
                    VALUES (?, ?, ?)
                """, (document_id, user_id, lock_type))
                conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False  # Already locked

    def unlock_document(self, document_id: int, user_id: int) -> bool:
        """Unlock a document."""
        with self._get_connection() as conn:
            cursor = conn.execute("""
                DELETE FROM DocumentLocks WHERE document_id = ? AND user_id = ?
            """, (document_id, user_id))
            conn.commit()
            return cursor.rowcount > 0

    def is_document_locked(self, document_id: int) -> Optional[Dict[str, Any]]:
        """Check if a document is locked and by whom."""
        with self._get_connection() as conn:
            row = conn.execute("""
                SELECT dl.user_id, dl.lock_type, dl.locked_at, u.username
                FROM DocumentLocks dl
                JOIN Users u ON dl.user_id = u.id
                WHERE dl.document_id = ?
            """, (document_id,)).fetchone()

            if row:
                return {
                    'user_id': row[0],
                    'lock_type': row[1],
                    'locked_at': row[2],
                    'username': row[3]
                }
            return None
