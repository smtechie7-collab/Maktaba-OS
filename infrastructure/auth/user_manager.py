"""
User management and authentication for Maktaba-OS multi-user support.

This module provides:
- User account management
- Password hashing and verification
- Role-based access control (RBAC)
- Session management
- Audit logging
"""

import hashlib
import hmac
import os
import secrets
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import logging

logger = logging.getLogger(__name__)


@dataclass
class User:
    """User account data."""
    id: int
    username: str
    email: Optional[str]
    display_name: Optional[str]
    created_at: datetime
    last_login: Optional[datetime]
    is_active: bool


@dataclass
class Role:
    """User role data."""
    id: int
    name: str
    description: Optional[str]
    created_at: datetime


@dataclass
class Permission:
    """Permission data."""
    id: int
    name: str
    description: Optional[str]
    resource_type: str
    action: str
    created_at: datetime


class PasswordHasher:
    """Secure password hashing using PBKDF2."""

    SALT_LENGTH = 32
    HASH_ITERATIONS = 100000
    KEY_LENGTH = 32

    @staticmethod
    def hash_password(password: str) -> str:
        """Hash a password with salt."""
        salt = os.urandom(PasswordHasher.SALT_LENGTH)
        key = hashlib.pbkdf2_hmac(
            'sha256',
            password.encode('utf-8'),
            salt,
            PasswordHasher.HASH_ITERATIONS,
            PasswordHasher.KEY_LENGTH
        )
        # Store salt + hash together
        return salt.hex() + key.hex()

    @staticmethod
    def verify_password(password: str, hashed: str) -> bool:
        """Verify a password against its hash."""
        try:
            salt_hex = hashed[:PasswordHasher.SALT_LENGTH * 2]
            stored_key_hex = hashed[PasswordHasher.SALT_LENGTH * 2:]

            salt = bytes.fromhex(salt_hex)
            stored_key = bytes.fromhex(stored_key_hex)

            key = hashlib.pbkdf2_hmac(
                'sha256',
                password.encode('utf-8'),
                salt,
                PasswordHasher.HASH_ITERATIONS,
                PasswordHasher.KEY_LENGTH
            )

            return hmac.compare_digest(key, stored_key)
        except (ValueError, TypeError):
            return False


class UserManager:
    """Manages user accounts, authentication, and authorization."""

    def __init__(self, db_connection: sqlite3.Connection):
        self.db = db_connection
        self._ensure_schema()

    def _ensure_schema(self):
        """Ensure the user management schema exists."""
        # Schema is created by DatabaseManager, but we can add any missing tables here
        pass

    def create_user(self, username: str, password: str, email: Optional[str] = None,
                   display_name: Optional[str] = None, created_by: Optional[int] = None) -> User:
        """Create a new user account."""
        if self.get_user_by_username(username):
            raise ValueError(f"Username '{username}' already exists")

        password_hash = PasswordHasher.hash_password(password)

        with self.db:
            cursor = self.db.execute("""
                INSERT INTO Users (username, email, display_name, password_hash)
                VALUES (?, ?, ?, ?)
            """, (username, email, display_name, password_hash))

            user_id = cursor.lastrowid

            # Assign default 'author' role
            author_role = self.get_role_by_name('author')
            if author_role:
                self.assign_role(user_id, author_role.id, created_by or user_id)

            # Log the creation
            self._audit_log(created_by or user_id, 'create', 'user', user_id,
                          f"Created user account: {username}")

            return self.get_user_by_id(user_id)

    def authenticate_user(self, username: str, password: str) -> Optional[User]:
        """Authenticate a user with username and password."""
        user = self.get_user_by_username(username)
        if not user or not user.is_active:
            return None

        # Get password hash from database
        cursor = self.db.execute("SELECT password_hash FROM Users WHERE id = ?", (user.id,))
        row = cursor.fetchone()
        if not row:
            return None

        stored_hash = row[0]
        if not PasswordHasher.verify_password(password, stored_hash):
            return None

        # Update last login
        with self.db:
            self.db.execute("""
                UPDATE Users SET last_login = CURRENT_TIMESTAMP WHERE id = ?
            """, (user.id,))

            self._audit_log(user.id, 'login', 'user', user.id, f"User login: {username}")

        return self.get_user_by_id(user.id)  # Refresh with updated last_login

    def get_user_by_id(self, user_id: int) -> Optional[User]:
        """Get user by ID."""
        cursor = self.db.execute("""
            SELECT id, username, email, display_name, created_at, last_login, is_active
            FROM Users WHERE id = ?
        """, (user_id,))

        row = cursor.fetchone()
        if not row:
            return None

        return User(
            id=row[0],
            username=row[1],
            email=row[2],
            display_name=row[3],
            created_at=datetime.fromisoformat(row[4]),
            last_login=datetime.fromisoformat(row[5]) if row[5] else None,
            is_active=bool(row[6])
        )

    def get_user_by_username(self, username: str) -> Optional[User]:
        """Get user by username."""
        cursor = self.db.execute("""
            SELECT id, username, email, display_name, created_at, last_login, is_active
            FROM Users WHERE username = ?
        """, (username,))

        row = cursor.fetchone()
        if not row:
            return None

        return User(
            id=row[0],
            username=row[1],
            email=row[2],
            display_name=row[3],
            created_at=datetime.fromisoformat(row[4]),
            last_login=datetime.fromisoformat(row[5]) if row[5] else None,
            is_active=bool(row[6])
        )

    def update_user(self, user_id: int, email: Optional[str] = None,
                   display_name: Optional[str] = None, is_active: Optional[bool] = None) -> bool:
        """Update user information."""
        updates = []
        params = []

        if email is not None:
            updates.append("email = ?")
            params.append(email)
        if display_name is not None:
            updates.append("display_name = ?")
            params.append(display_name)
        if is_active is not None:
            updates.append("is_active = ?")
            params.append(1 if is_active else 0)

        if not updates:
            return False

        params.append(user_id)

        with self.db:
            self.db.execute(f"""
                UPDATE Users SET {', '.join(updates)} WHERE id = ?
            """, params)

            self._audit_log(user_id, 'update', 'user', user_id, f"Updated user profile")

        return True

    def change_password(self, user_id: int, old_password: str, new_password: str) -> bool:
        """Change user password."""
        user = self.get_user_by_id(user_id)
        if not user:
            return False

        # Verify old password
        cursor = self.db.execute("SELECT password_hash FROM Users WHERE id = ?", (user_id,))
        row = cursor.fetchone()
        if not row or not PasswordHasher.verify_password(old_password, row[0]):
            return False

        # Update password
        new_hash = PasswordHasher.hash_password(new_password)
        with self.db:
            self.db.execute("""
                UPDATE Users SET password_hash = ? WHERE id = ?
            """, (new_hash, user_id))

            self._audit_log(user_id, 'update', 'user', user_id, "Password changed")

        return True

    def get_role_by_name(self, role_name: str) -> Optional[Role]:
        """Get role by name."""
        cursor = self.db.execute("""
            SELECT id, name, description, created_at FROM Roles WHERE name = ?
        """, (role_name,))

        row = cursor.fetchone()
        if not row:
            return None

        return Role(
            id=row[0],
            name=row[1],
            description=row[2],
            created_at=datetime.fromisoformat(row[3])
        )

    def assign_role(self, user_id: int, role_id: int, assigned_by: int) -> bool:
        """Assign a role to a user."""
        try:
            with self.db:
                self.db.execute("""
                    INSERT INTO UserRoles (user_id, role_id, assigned_by)
                    VALUES (?, ?, ?)
                """, (user_id, role_id, assigned_by))

                role = self._get_role_by_id(role_id)
                user = self.get_user_by_id(user_id)
                self._audit_log(assigned_by, 'assign', 'role', role_id,
                              f"Assigned role '{role.name}' to user '{user.username}'")

            return True
        except sqlite3.IntegrityError:
            return False  # Role already assigned

    def revoke_role(self, user_id: int, role_id: int, revoked_by: int) -> bool:
        """Revoke a role from a user."""
        with self.db:
            cursor = self.db.execute("""
                DELETE FROM UserRoles WHERE user_id = ? AND role_id = ?
            """, (user_id, role_id))

            if cursor.rowcount > 0:
                role = self._get_role_by_id(role_id)
                user = self.get_user_by_id(user_id)
                self._audit_log(revoked_by, 'revoke', 'role', role_id,
                              f"Revoked role '{role.name}' from user '{user.username}'")
                return True

        return False

    def get_user_roles(self, user_id: int) -> List[Role]:
        """Get all roles assigned to a user."""
        cursor = self.db.execute("""
            SELECT r.id, r.name, r.description, r.created_at
            FROM Roles r
            JOIN UserRoles ur ON r.id = ur.role_id
            WHERE ur.user_id = ?
        """, (user_id,))

        roles = []
        for row in cursor.fetchall():
            roles.append(Role(
                id=row[0],
                name=row[1],
                description=row[2],
                created_at=datetime.fromisoformat(row[3])
            ))

        return roles

    def get_user_permissions(self, user_id: int) -> List[Permission]:
        """Get all permissions for a user based on their roles."""
        cursor = self.db.execute("""
            SELECT DISTINCT p.id, p.name, p.description, p.resource_type, p.action, p.created_at
            FROM Permissions p
            JOIN RolePermissions rp ON p.id = rp.permission_id
            JOIN UserRoles ur ON rp.role_id = ur.role_id
            WHERE ur.user_id = ?
        """, (user_id,))

        permissions = []
        for row in cursor.fetchall():
            permissions.append(Permission(
                id=row[0],
                name=row[1],
                description=row[2],
                resource_type=row[3],
                action=row[4],
                created_at=datetime.fromisoformat(row[5])
            ))

        return permissions

    def has_permission(self, user_id: int, resource_type: str, action: str) -> bool:
        """Check if user has permission for a specific action on a resource type."""
        cursor = self.db.execute("""
            SELECT COUNT(*) FROM Permissions p
            JOIN RolePermissions rp ON p.id = rp.permission_id
            JOIN UserRoles ur ON rp.role_id = ur.role_id
            WHERE ur.user_id = ? AND p.resource_type = ? AND p.action = ?
        """, (user_id, resource_type, action))

        return cursor.fetchone()[0] > 0

    def can_access_book(self, user_id: int, book_id: int, action: str = 'read') -> bool:
        """Check if user can access a specific book."""
        # Check if user owns the book
        cursor = self.db.execute("""
            SELECT ownership_type FROM BookOwnership
            WHERE book_id = ? AND user_id = ?
        """, (book_id, user_id))

        row = cursor.fetchone()
        if row:
            ownership_type = row[0]
            if ownership_type == 'owner':
                return True
            elif ownership_type == 'editor' and action in ['read', 'write']:
                return True
            elif ownership_type == 'viewer' and action == 'read':
                return True

        # Check if book is public and action is read
        cursor = self.db.execute("""
            SELECT is_public FROM Books WHERE id = ?
        """, (book_id,))

        row = cursor.fetchone()
        if row and row[0] and action == 'read':
            return True

        return False

    def grant_book_access(self, book_id: int, user_id: int, ownership_type: str, granted_by: int) -> bool:
        """Grant access to a book for a user."""
        try:
            with self.db:
                self.db.execute("""
                    INSERT INTO BookOwnership (book_id, user_id, ownership_type, granted_by)
                    VALUES (?, ?, ?, ?)
                """, (book_id, user_id, ownership_type, granted_by))

                user = self.get_user_by_id(user_id)
                self._audit_log(granted_by, 'share', 'book', book_id,
                              f"Granted '{ownership_type}' access to user '{user.username}'")

            return True
        except sqlite3.IntegrityError:
            return False  # Access already granted

    def revoke_book_access(self, book_id: int, user_id: int, revoked_by: int) -> bool:
        """Revoke access to a book from a user."""
        with self.db:
            cursor = self.db.execute("""
                DELETE FROM BookOwnership WHERE book_id = ? AND user_id = ?
            """, (book_id, user_id))

            if cursor.rowcount > 0:
                user = self.get_user_by_id(user_id)
                self._audit_log(revoked_by, 'revoke', 'book', book_id,
                              f"Revoked access from user '{user.username}'")
                return True

        return False

    def _get_role_by_id(self, role_id: int) -> Optional[Role]:
        """Get role by ID (internal method)."""
        cursor = self.db.execute("""
            SELECT id, name, description, created_at FROM Roles WHERE id = ?
        """, (role_id,))

        row = cursor.fetchone()
        if not row:
            return None

        return Role(
            id=row[0],
            name=row[1],
            description=row[2],
            created_at=datetime.fromisoformat(row[3])
        )

    def _audit_log(self, user_id: Optional[int], action: str, resource_type: str,
                  resource_id: Optional[int], details: str):
        """Log an action to the audit log."""
        try:
            with self.db:
                self.db.execute("""
                    INSERT INTO AuditLog (user_id, action, resource_type, resource_id, details)
                    VALUES (?, ?, ?, ?, ?)
                """, (user_id, action, resource_type, resource_id, details))
        except Exception as e:
            logger.warning(f"Failed to write audit log: {e}")


# Convenience functions for the default user manager
_default_user_manager = None

def get_user_manager(db_connection: sqlite3.Connection) -> UserManager:
    """Get the default user manager instance."""
    global _default_user_manager
    if _default_user_manager is None or _default_user_manager.db != db_connection:
        _default_user_manager = UserManager(db_connection)
    return _default_user_manager