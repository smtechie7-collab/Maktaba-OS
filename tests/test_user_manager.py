"""
Tests for user management and authentication.
"""

import pytest
import sqlite3
from datetime import datetime

from infrastructure.auth.user_manager import UserManager, User, PasswordHasher


@pytest.fixture
def db_connection():
    """Create an in-memory database for testing."""
    conn = sqlite3.connect(':memory:')
    # Create the user management schema
    schema_sql = """
    CREATE TABLE Users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT NOT NULL UNIQUE,
        email TEXT UNIQUE,
        display_name TEXT,
        password_hash TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        last_login TIMESTAMP,
        is_active INTEGER DEFAULT 1
    );

    CREATE TABLE Roles (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL UNIQUE,
        description TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE UserRoles (
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

    CREATE TABLE Permissions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL UNIQUE,
        description TEXT,
        resource_type TEXT NOT NULL,
        action TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE RolePermissions (
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

    CREATE TABLE Books (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        author TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        created_by INTEGER,
        is_active INTEGER DEFAULT 1,
        is_public INTEGER DEFAULT 0,
        FOREIGN KEY (created_by) REFERENCES Users(id)
    );

    CREATE TABLE BookOwnership (
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

    CREATE TABLE AuditLog (
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
    INSERT INTO Roles (name, description) VALUES
    ('admin', 'Full system access'),
    ('author', 'Can create and edit books'),
    ('reviewer', 'Can review and comment on books'),
    ('viewer', 'Read-only access to shared books');

    -- Insert default permissions
    INSERT INTO Permissions (name, description, resource_type, action) VALUES
    ('book.create', 'Create new books', 'book', 'create'),
    ('book.read', 'Read book metadata', 'book', 'read'),
    ('book.write', 'Edit book content', 'book', 'write'),
    ('book.delete', 'Delete books', 'book', 'delete'),
    ('book.share', 'Share books with others', 'book', 'share'),
    ('document.lock', 'Lock documents for editing', 'document', 'lock'),
    ('user.manage', 'Manage user accounts', 'user', 'manage'),
    ('role.assign', 'Assign roles to users', 'role', 'assign');

    -- Assign permissions to default roles
    INSERT INTO RolePermissions (role_id, permission_id)
    SELECT r.id, p.id FROM Roles r, Permissions p
    WHERE (r.name = 'admin' AND p.name IN ('book.create', 'book.read', 'book.write', 'book.delete', 'book.share', 'document.lock', 'user.manage', 'role.assign'))
       OR (r.name = 'author' AND p.name IN ('book.create', 'book.read', 'book.write', 'book.share', 'document.lock'))
       OR (r.name = 'reviewer' AND p.name IN ('book.read', 'document.lock'))
       OR (r.name = 'viewer' AND p.name IN ('book.read'));
    """
    conn.executescript(schema_sql)
    conn.row_factory = sqlite3.Row
    yield conn
    conn.close()


@pytest.fixture
def user_manager(db_connection):
    """Create a UserManager instance for testing."""
    return UserManager(db_connection)


class TestPasswordHasher:
    """Test password hashing functionality."""

    def test_hash_and_verify_password(self):
        """Test that passwords can be hashed and verified."""
        password = "test_password_123"

        # Hash the password
        hashed = PasswordHasher.hash_password(password)

        # Verify it matches
        assert PasswordHasher.verify_password(password, hashed)

        # Verify wrong password fails
        assert not PasswordHasher.verify_password("wrong_password", hashed)

    def test_different_salts(self):
        """Test that different hashes are generated for the same password."""
        password = "same_password"
        hash1 = PasswordHasher.hash_password(password)
        hash2 = PasswordHasher.hash_password(password)

        # Should be different due to random salt
        assert hash1 != hash2

        # But both should verify correctly
        assert PasswordHasher.verify_password(password, hash1)
        assert PasswordHasher.verify_password(password, hash2)


class TestUserManager:
    """Test user management functionality."""

    def test_create_user(self, user_manager):
        """Test creating a new user."""
        user = user_manager.create_user(
            username="testuser",
            password="testpass123",
            email="test@example.com",
            display_name="Test User"
        )

        assert user.id is not None
        assert user.username == "testuser"
        assert user.email == "test@example.com"
        assert user.display_name == "Test User"
        assert user.is_active == True

    def test_create_duplicate_username(self, user_manager):
        """Test that duplicate usernames are rejected."""
        user_manager.create_user("testuser", "pass1")

        with pytest.raises(ValueError, match="Username 'testuser' already exists"):
            user_manager.create_user("testuser", "pass2")

    def test_authenticate_user(self, user_manager):
        """Test user authentication."""
        # Create user
        user_manager.create_user("authuser", "correct_password")

        # Successful authentication
        user = user_manager.authenticate_user("authuser", "correct_password")
        assert user is not None
        assert user.username == "authuser"

        # Failed authentication - wrong password
        user = user_manager.authenticate_user("authuser", "wrong_password")
        assert user is None

        # Failed authentication - non-existent user
        user = user_manager.authenticate_user("nonexistent", "password")
        assert user is None

    def test_get_user_by_username(self, user_manager):
        """Test retrieving user by username."""
        created_user = user_manager.create_user("getuser", "password")

        retrieved_user = user_manager.get_user_by_username("getuser")
        assert retrieved_user is not None
        assert retrieved_user.id == created_user.id
        assert retrieved_user.username == "getuser"

    def test_get_user_by_id(self, user_manager):
        """Test retrieving user by ID."""
        created_user = user_manager.create_user("getuserbyid", "password")

        retrieved_user = user_manager.get_user_by_id(created_user.id)
        assert retrieved_user is not None
        assert retrieved_user.username == "getuserbyid"

    def test_update_user(self, user_manager):
        """Test updating user information."""
        user = user_manager.create_user("updateuser", "password", email="old@example.com")

        # Update email and display name
        success = user_manager.update_user(
            user.id,
            email="new@example.com",
            display_name="Updated Name"
        )

        assert success

        # Verify changes
        updated_user = user_manager.get_user_by_id(user.id)
        assert updated_user.email == "new@example.com"
        assert updated_user.display_name == "Updated Name"

    def test_change_password(self, user_manager):
        """Test password changing."""
        user = user_manager.create_user("changepass", "old_password")

        # Change password
        success = user_manager.change_password(user.id, "old_password", "new_password")
        assert success

        # Verify old password no longer works
        authenticated = user_manager.authenticate_user("changepass", "old_password")
        assert authenticated is None

        # Verify new password works
        authenticated = user_manager.authenticate_user("changepass", "new_password")
        assert authenticated is not None

    def test_change_password_wrong_old(self, user_manager):
        """Test password change with wrong old password."""
        user = user_manager.create_user("changepasswrong", "old_password")

        success = user_manager.change_password(user.id, "wrong_old", "new_password")
        assert not success

    def test_assign_and_revoke_roles(self, user_manager):
        """Test role assignment and revocation."""
        user = user_manager.create_user("roleuser", "password")
        admin_role = user_manager.get_role_by_name("admin")
        author_role = user_manager.get_role_by_name("author")

        # Assign admin role
        success = user_manager.assign_role(user.id, admin_role.id, user.id)
        assert success

        # Check user has admin role
        roles = user_manager.get_user_roles(user.id)
        role_names = [r.name for r in roles]
        assert "admin" in role_names

        # Revoke admin role
        success = user_manager.revoke_role(user.id, admin_role.id, user.id)
        assert success

        # Check admin role is removed
        roles = user_manager.get_user_roles(user.id)
        role_names = [r.name for r in roles]
        assert "admin" not in role_names

    def test_has_permission(self, user_manager):
        """Test permission checking."""
        user = user_manager.create_user("permuser", "password")
        author_role = user_manager.get_role_by_name("author")

        user_manager.assign_role(user.id, author_role.id, user.id)

        # Author should have book.create permission
        assert user_manager.has_permission(user.id, "book", "create")
        assert user_manager.has_permission(user.id, "book", "read")
        assert user_manager.has_permission(user.id, "book", "write")

        # Author should not have user.manage permission
        assert not user_manager.has_permission(user.id, "user", "manage")

    def test_get_user_permissions(self, user_manager):
        """Test getting all user permissions."""
        user = user_manager.create_user("permuser2", "password")
        author_role = user_manager.get_role_by_name("author")

        user_manager.assign_role(user.id, author_role.id, user.id)

        permissions = user_manager.get_user_permissions(user.id)
        permission_names = [p.name for p in permissions]

        # Should include author permissions
        assert "book.create" in permission_names
        assert "book.read" in permission_names
        assert "book.write" in permission_names
        assert "book.share" in permission_names

        # Should not include admin-only permissions
        assert "user.manage" not in permission_names

    def test_book_access_control(self, user_manager, db_connection):
        """Test book access control."""
        # Create users
        owner = user_manager.create_user("bookowner", "password")
        viewer = user_manager.create_user("bookviewer", "password")

        # Create a book in the database
        cursor = db_connection.cursor()
        cursor.execute("INSERT INTO Books (title, created_by) VALUES (?, ?)", ("Test Book", owner.id))
        book_id = cursor.lastrowid

        # Create ownership record for the owner
        cursor.execute("""
            INSERT INTO BookOwnership (book_id, user_id, ownership_type, granted_by)
            VALUES (?, ?, 'owner', ?)
        """, (book_id, owner.id, owner.id))

        db_connection.commit()

        # Grant viewer access
        success = user_manager.grant_book_access(book_id, viewer.id, "viewer", owner.id)
        assert success

        # Check access
        assert user_manager.can_access_book(owner.id, book_id, "write")  # Owner can write
        assert user_manager.can_access_book(viewer.id, book_id, "read")  # Viewer can read
        assert not user_manager.can_access_book(viewer.id, book_id, "write")  # Viewer cannot write

        # Revoke access
        success = user_manager.revoke_book_access(book_id, viewer.id, owner.id)
        assert success

        # Viewer should no longer have access
        assert not user_manager.can_access_book(viewer.id, book_id, "read")