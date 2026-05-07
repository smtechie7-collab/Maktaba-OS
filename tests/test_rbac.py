"""
Tests for granular role-based access control (RBAC).
"""

import pytest
import sqlite3
from datetime import datetime, timedelta

from infrastructure.auth.rbac import (
    GranularAccessControl, ResourceType, Action, AccessLevel, ResourcePermission
)


@pytest.fixture
def db_connection():
    """Create an in-memory database for testing."""
    conn = sqlite3.connect(':memory:')

    # Create minimal schema for testing
    conn.execute("""
        CREATE TABLE Users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            email TEXT UNIQUE,
            display_name TEXT,
            password_hash TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_login TIMESTAMP,
            is_active INTEGER DEFAULT 1
        )
    """)

    conn.execute("""
        CREATE TABLE Roles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            description TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.execute("""
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
        )
    """)

    # Insert test data
    conn.execute("INSERT INTO Users (username, password_hash) VALUES (?, ?)", ("user1", "hash1"))
    conn.execute("INSERT INTO Users (username, password_hash) VALUES (?, ?)", ("user2", "hash2"))
    conn.execute("INSERT INTO Users (username, password_hash) VALUES (?, ?)", ("admin", "hash_admin"))

    conn.commit()
    return conn


@pytest.fixture
def rbac(db_connection):
    """Create RBAC instance."""
    return GranularAccessControl(db_connection)


def test_grant_permission_to_user(rbac, db_connection):
    """Test granting permission to a user."""
    perm = rbac.grant_permission(
        resource_type="book",
        resource_id=1,
        user_id=1,
        access_level="editor",
        granted_by=2
    )

    assert perm is not None
    assert perm.resource_type == "book"
    assert perm.resource_id == 1
    assert perm.user_id == 1
    assert perm.access_level == "editor"


def test_grant_permission_to_role(rbac):
    """Test granting permission to a role."""
    # First insert a role
    rbac.db.execute("INSERT INTO Roles (name) VALUES (?)", ("author",))
    rbac.db.commit()

    role_id = rbac.db.execute("SELECT id FROM Roles WHERE name = ?", ("author",)).fetchone()[0]

    perm = rbac.grant_permission(
        resource_type="book",
        resource_id=1,
        role_id=role_id,
        access_level="viewer"
    )

    assert perm is not None
    assert perm.role_id == role_id


def test_update_permission(rbac):
    """Test updating an existing permission."""
    # Grant initial permission
    rbac.grant_permission(
        resource_type="book",
        resource_id=1,
        user_id=1,
        access_level="viewer"
    )

    # Update permission
    updated = rbac.grant_permission(
        resource_type="book",
        resource_id=1,
        user_id=1,
        access_level="editor"
    )

    assert updated.access_level == "editor"


def test_revoke_permission(rbac):
    """Test revoking a permission."""
    # Grant permission
    rbac.grant_permission(
        resource_type="book",
        resource_id=1,
        user_id=1,
        access_level="editor"
    )

    # Revoke permission
    success = rbac.revoke_permission(
        resource_type="book",
        resource_id=1,
        user_id=1
    )

    assert success is True

    # Verify permission is gone
    perm = rbac.get_resource_permission(
        resource_type="book",
        resource_id=1,
        user_id=1
    )

    assert perm is None


def test_get_resource_permissions(rbac):
    """Test getting all permissions for a resource."""
    # Grant multiple permissions
    rbac.grant_permission("book", 1, user_id=1, access_level="editor")
    rbac.grant_permission("book", 1, user_id=2, access_level="viewer")

    perms = rbac.get_resource_permissions("book", 1)

    assert len(perms) == 2
    access_levels = {p.access_level for p in perms}
    assert access_levels == {"editor", "viewer"}


def test_can_perform_action_owner(rbac):
    """Test action permissions for owner access level."""
    rbac.grant_permission("book", 1, user_id=1, access_level="owner")

    assert rbac.can_perform_action(1, "book", 1, "read") is True
    assert rbac.can_perform_action(1, "book", 1, "write") is True
    assert rbac.can_perform_action(1, "book", 1, "delete") is True
    assert rbac.can_perform_action(1, "book", 1, "manage_permissions") is True


def test_can_perform_action_editor(rbac):
    """Test action permissions for editor access level."""
    rbac.grant_permission("book", 1, user_id=1, access_level="editor")

    assert rbac.can_perform_action(1, "book", 1, "read") is True
    assert rbac.can_perform_action(1, "book", 1, "write") is True
    assert rbac.can_perform_action(1, "book", 1, "publish") is True
    assert rbac.can_perform_action(1, "book", 1, "delete") is False  # Editors can't delete


def test_can_perform_action_viewer(rbac):
    """Test action permissions for viewer access level."""
    rbac.grant_permission("book", 1, user_id=1, access_level="viewer")

    assert rbac.can_perform_action(1, "book", 1, "read") is True
    assert rbac.can_perform_action(1, "book", 1, "write") is False
    assert rbac.can_perform_action(1, "book", 1, "delete") is False


def test_can_perform_action_reviewer(rbac):
    """Test action permissions for reviewer access level."""
    rbac.grant_permission("book", 1, user_id=1, access_level="reviewer")

    assert rbac.can_perform_action(1, "book", 1, "read") is True
    assert rbac.can_perform_action(1, "book", 1, "comment") is True
    assert rbac.can_perform_action(1, "book", 1, "review") is True
    assert rbac.can_perform_action(1, "book", 1, "write") is False


def test_permission_expiry(rbac):
    """Test that expired permissions are not considered."""
    # Grant permission that expires in the past
    expires_at = datetime.now() - timedelta(hours=1)
    rbac.grant_permission(
        "book", 1,
        user_id=1,
        access_level="editor",
        expires_at=expires_at
    )

    # Permission should not be valid
    assert rbac.can_perform_action(1, "book", 1, "read") is False


def test_permission_audit_log(rbac):
    """Test permission audit logging."""
    rbac.grant_permission("book", 1, user_id=1, access_level="editor", granted_by=2)

    logs = rbac.get_permission_audit_log()

    assert len(logs) > 0
    latest_log = logs[0]
    assert latest_log.action == "grant_permission"
    assert latest_log.resource_type == "book"
    assert latest_log.resource_id == 1


def test_add_organization_member(rbac):
    """Test adding organization members."""
    success = rbac.add_organization_member(1, 1, role="owner")

    assert success is True

    members = rbac.get_organization_members(1)
    assert len(members) == 1
    assert members[0] == (1, "owner")


def test_remove_organization_member(rbac):
    """Test removing organization members."""
    rbac.add_organization_member(1, 1, role="member")

    success = rbac.remove_organization_member(1, 1)

    assert success is True

    members = rbac.get_organization_members(1)
    assert len(members) == 0


def test_permission_inheritance_from_role(rbac):
    """Test that users inherit permissions from their roles."""
    # Create role
    rbac.db.execute("INSERT INTO Roles (name) VALUES (?)", ("editor_role",))
    rbac.db.commit()
    role_id = rbac.db.execute("SELECT id FROM Roles WHERE name = ?", ("editor_role",)).fetchone()[0]

    # Assign user to role
    rbac.db.execute(
        "INSERT INTO UserRoles (user_id, role_id) VALUES (?, ?)",
        (1, role_id)
    )
    rbac.db.commit()

    # Grant permission to role
    rbac.grant_permission("book", 1, role_id=role_id, access_level="editor")

    # User should have editor permissions through role
    assert rbac.can_perform_action(1, "book", 1, "read") is True
    assert rbac.can_perform_action(1, "book", 1, "write") is True
