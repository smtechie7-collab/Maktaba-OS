SCHEMA_VERSION = 1

# Simplified schema aligning with the Document-First constitution.
# The entire document is a single JSON blob, making the DB a "dumb" storage layer.
SCHEMA_SQL = """
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

-- Metadata for discoverability without loading the whole document
CREATE TABLE IF NOT EXISTS Books (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    author TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_active INTEGER DEFAULT 1
);

-- The single source of truth for a book's content
CREATE TABLE IF NOT EXISTS Documents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    book_id INTEGER NOT NULL UNIQUE,
    content_json TEXT NOT NULL,
    version INTEGER NOT NULL DEFAULT 1,
    FOREIGN KEY (book_id) REFERENCES Books(id) ON DELETE CASCADE
);

-- Trigger to update the 'updated_at' timestamp on the Books table
CREATE TRIGGER IF NOT EXISTS update_book_timestamp
AFTER UPDATE ON Documents
FOR EACH ROW
BEGIN
    UPDATE Books SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.book_id;
END;

-- Schema versioning to manage future migrations
CREATE TABLE IF NOT EXISTS _schema_version (
    version INTEGER PRIMARY KEY
);
"""