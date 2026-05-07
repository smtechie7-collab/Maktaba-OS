SCHEMA_VERSION = 2

# Multi-user schema extending the document-first architecture.
# Maintains offline-first principles while adding collaboration foundations.
SCHEMA_SQL = """
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

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
    assigned_by INTEGER,  -- User who assigned this role
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
    resource_type TEXT NOT NULL,  -- 'book', 'document', 'user', etc.
    action TEXT NOT NULL,         -- 'read', 'write', 'delete', 'share', etc.
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
    ownership_type TEXT NOT NULL,  -- 'owner', 'editor', 'viewer'
    granted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    granted_by INTEGER NOT NULL,
    FOREIGN KEY (book_id) REFERENCES Books(id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES Users(id) ON DELETE CASCADE,
    FOREIGN KEY (granted_by) REFERENCES Users(id),
    UNIQUE(book_id, user_id)
);

-- Metadata for discoverability without loading the whole document
CREATE TABLE IF NOT EXISTS Books (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    author TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by INTEGER,  -- User who created the book
    is_active INTEGER DEFAULT 1,
    is_public INTEGER DEFAULT 0,  -- Public sharing flag
    FOREIGN KEY (created_by) REFERENCES Users(id)
);

-- The single source of truth for a book's content
CREATE TABLE IF NOT EXISTS Documents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    book_id INTEGER NOT NULL UNIQUE,
    content_json TEXT NOT NULL,
    version INTEGER NOT NULL DEFAULT 1,
    last_modified_by INTEGER,  -- User who last modified
    last_modified_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (book_id) REFERENCES Books(id) ON DELETE CASCADE,
    FOREIGN KEY (last_modified_by) REFERENCES Users(id)
);

-- Document locking for collaborative editing
CREATE TABLE IF NOT EXISTS DocumentLocks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    document_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    lock_type TEXT NOT NULL,  -- 'exclusive', 'shared'
    locked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP,  -- For temporary locks
    FOREIGN KEY (document_id) REFERENCES Documents(id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES Users(id) ON DELETE CASCADE,
    UNIQUE(document_id, user_id)
);

-- Audit log for compliance and tracking
CREATE TABLE IF NOT EXISTS AuditLog (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    action TEXT NOT NULL,  -- 'create', 'read', 'update', 'delete', 'share'
    resource_type TEXT NOT NULL,  -- 'book', 'document', 'user'
    resource_id INTEGER,
    details TEXT,  -- JSON details about the action
    ip_address TEXT,
    user_agent TEXT,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES Users(id)
);

-- Trigger to update the 'updated_at' timestamp on the Books table
CREATE TRIGGER IF NOT EXISTS update_book_timestamp
AFTER UPDATE ON Documents
FOR EACH ROW
BEGIN
    UPDATE Books SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.book_id;
END;

-- Trigger to log document modifications
CREATE TRIGGER IF NOT EXISTS audit_document_changes
AFTER UPDATE ON Documents
FOR EACH ROW
BEGIN
    INSERT INTO AuditLog (user_id, action, resource_type, resource_id, details, timestamp)
    VALUES (NEW.last_modified_by, 'update', 'document', NEW.id,
            '{"old_version": ' || OLD.version || ', "new_version": ' || NEW.version || '}',
            NEW.last_modified_at);
END;

-- Schema versioning to manage future migrations
CREATE TABLE IF NOT EXISTS _schema_version (
    version INTEGER PRIMARY KEY
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