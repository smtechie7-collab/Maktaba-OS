"""
Advanced Role-Based Access Control (RBAC) with granular permissions.

This module provides:
- Granular resource-level permissions
- Organization-level access control
- Document-level permission management
- Permission inheritance and delegation
- Audit logging for access control decisions
"""

import sqlite3
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Set, Tuple
import logging

logger = logging.getLogger(__name__)


class ResourceType(Enum):
    """Types of resources that can be protected."""
    BOOK = "book"
    DOCUMENT = "document"
    CHAPTER = "chapter"
    ORGANIZATION = "organization"
    WORKSPACE = "workspace"
    TEMPLATE = "template"
    REPORT = "report"


class Action(Enum):
    """Actions that can be performed on resources."""
    READ = "read"
    WRITE = "write"
    DELETE = "delete"
    SHARE = "share"
    ADMIN = "admin"
    COMMENT = "comment"
    REVIEW = "review"
    PUBLISH = "publish"
    MANAGE_PERMISSIONS = "manage_permissions"


class AccessLevel(Enum):
    """Access levels for resource sharing."""
    OWNER = "owner"  # Full control
    ADMIN = "admin"  # Administrative access
    EDITOR = "editor"  # Can edit content
    REVIEWER = "reviewer"  # Can review and comment
    COMMENTER = "commenter"  # Can only comment
    VIEWER = "viewer"  # Read-only access


@dataclass
class ResourcePermission:
    """Permission for a specific resource."""
    id: int
    resource_type: str
    resource_id: int
    user_id: Optional[int]  # None if it's for a role
    role_id: Optional[int]  # None if it's for a user
    access_level: str
    granted_at: datetime
    granted_by: Optional[int]
    expires_at: Optional[datetime]
    is_delegated: bool


@dataclass
class PermissionAuditLog:
    """Log entry for permission changes."""
    id: int
    user_id: int
    action: str
    resource_type: str
    resource_id: int
    target_user_id: Optional[int]
    old_value: Optional[str]
    new_value: str
    timestamp: datetime
    reason: Optional[str]


class GranularAccessControl:
    """Manages granular, resource-level access control."""

    def __init__(self, db_connection: sqlite3.Connection):
        self.db = db_connection
        self._ensure_schema()

    def _ensure_schema(self):
        """Ensure RBAC schema exists."""
        with self.db:
            # Resource permissions table
            self.db.execute("""
                CREATE TABLE IF NOT EXISTS ResourcePermissions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    resource_type TEXT NOT NULL,
                    resource_id INTEGER NOT NULL,
                    user_id INTEGER,
                    role_id INTEGER,
                    access_level TEXT NOT NULL,
                    granted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    granted_by INTEGER,
                    expires_at TIMESTAMP,
                    is_delegated INTEGER DEFAULT 0,
                    FOREIGN KEY (user_id) REFERENCES Users(id) ON DELETE CASCADE,
                    FOREIGN KEY (role_id) REFERENCES Roles(id) ON DELETE CASCADE,
                    FOREIGN KEY (granted_by) REFERENCES Users(id),
                    CHECK (user_id IS NOT NULL OR role_id IS NOT NULL),
                    UNIQUE(resource_type, resource_id, user_id, role_id)
                )
            """)

            # Permission audit log
            self.db.execute("""
                CREATE TABLE IF NOT EXISTS PermissionAuditLog (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    action TEXT NOT NULL,
                    resource_type TEXT NOT NULL,
                    resource_id INTEGER NOT NULL,
                    target_user_id INTEGER,
                    old_value TEXT,
                    new_value TEXT NOT NULL,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    reason TEXT,
                    FOREIGN KEY (user_id) REFERENCES Users(id),
                    FOREIGN KEY (target_user_id) REFERENCES Users(id)
                )
            """)

            # RBAC exposes organization membership helpers, so keep the shared
            # membership table available even when OrganizationManager is not
            # initialized in a test or lightweight service.
            self.db.execute("""
                CREATE TABLE IF NOT EXISTS OrganizationMembers (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    organization_id INTEGER NOT NULL,
                    user_id INTEGER NOT NULL,
                    role TEXT NOT NULL DEFAULT 'member',
                    department_id INTEGER,
                    joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    is_active INTEGER DEFAULT 1,
                    FOREIGN KEY (user_id) REFERENCES Users(id) ON DELETE CASCADE,
                    UNIQUE(organization_id, user_id)
                )
            """)



    def grant_permission(
        self,
        resource_type: str,
        resource_id: int,
        user_id: Optional[int] = None,
        role_id: Optional[int] = None,
        access_level: str = "viewer",
        granted_by: int = None,
        expires_at: Optional[datetime] = None,
        reason: Optional[str] = None
    ) -> ResourcePermission:
        """Grant permission on a resource to a user or role."""
        if user_id is None and role_id is None:
            raise ValueError("Either user_id or role_id must be provided")

        # For audit logging, use granted_by if provided, otherwise use user_id, or fallback to system user (0)
        audit_user_id = granted_by or user_id or 0

        with self.db:
            # Check if permission already exists
            cursor = self.db.execute("""
                SELECT id, access_level FROM ResourcePermissions
                WHERE resource_type = ? AND resource_id = ?
                AND ((user_id = ?) OR (role_id = ?))
            """, (resource_type, resource_id, user_id, role_id))

            existing = cursor.fetchone()
            if existing:
                # Update existing permission
                perm_id, old_level = existing
                self.db.execute("""
                    UPDATE ResourcePermissions
                    SET access_level = ?, expires_at = ?, granted_by = ?
                    WHERE id = ?
                """, (access_level, expires_at, granted_by, perm_id))

                self._log_permission_change(
                    audit_user_id,
                    "update_permission",
                    resource_type,
                    resource_id,
                    user_id,
                    old_level,
                    access_level,
                    reason
                )
            else:
                # Create new permission
                self.db.execute("""
                    INSERT INTO ResourcePermissions
                    (resource_type, resource_id, user_id, role_id, access_level, granted_by, expires_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (resource_type, resource_id, user_id, role_id, access_level, granted_by, expires_at))

                self._log_permission_change(
                    audit_user_id,
                    "grant_permission",
                    resource_type,
                    resource_id,
                    user_id,
                    None,
                    access_level,
                    reason
                )

            return self.get_resource_permission(resource_type, resource_id, user_id, role_id)

    def revoke_permission(
        self,
        resource_type: str,
        resource_id: int,
        user_id: Optional[int] = None,
        role_id: Optional[int] = None,
        revoked_by: int = None,
        reason: Optional[str] = None
    ) -> bool:
        """Revoke permission on a resource."""
        cursor = self.db.execute("""
            SELECT access_level FROM ResourcePermissions
            WHERE resource_type = ? AND resource_id = ?
            AND ((user_id = ?) OR (role_id = ?))
        """, (resource_type, resource_id, user_id, role_id))

        existing = cursor.fetchone()
        if not existing:
            return False

        old_level = existing[0]
        
        # For audit logging
        audit_user_id = revoked_by or user_id or 0

        with self.db:
            self.db.execute("""
                DELETE FROM ResourcePermissions
                WHERE resource_type = ? AND resource_id = ?
                AND ((user_id = ?) OR (role_id = ?))
            """, (resource_type, resource_id, user_id, role_id))

            self._log_permission_change(
                audit_user_id,
                "revoke_permission",
                resource_type,
                resource_id,
                user_id,
                old_level,
                "revoked",
                reason
            )

        return True

    def get_resource_permission(
        self,
        resource_type: str,
        resource_id: int,
        user_id: Optional[int] = None,
        role_id: Optional[int] = None
    ) -> Optional[ResourcePermission]:
        """Get a specific resource permission."""
        cursor = self.db.execute("""
            SELECT id, resource_type, resource_id, user_id, role_id, access_level,
                   granted_at, granted_by, expires_at, is_delegated
            FROM ResourcePermissions
            WHERE resource_type = ? AND resource_id = ?
            AND ((user_id = ?) OR (role_id = ?))
        """, (resource_type, resource_id, user_id, role_id))

        row = cursor.fetchone()
        if not row:
            return None

        return ResourcePermission(
            id=row[0],
            resource_type=row[1],
            resource_id=row[2],
            user_id=row[3],
            role_id=row[4],
            access_level=row[5],
            granted_at=datetime.fromisoformat(row[6]),
            granted_by=row[7],
            expires_at=datetime.fromisoformat(row[8]) if row[8] else None,
            is_delegated=bool(row[9])
        )

    def get_resource_permissions(
        self,
        resource_type: str,
        resource_id: int
    ) -> List[ResourcePermission]:
        """Get all permissions for a resource."""
        cursor = self.db.execute("""
            SELECT id, resource_type, resource_id, user_id, role_id, access_level,
                   granted_at, granted_by, expires_at, is_delegated
            FROM ResourcePermissions
            WHERE resource_type = ? AND resource_id = ?
            ORDER BY access_level DESC, granted_at DESC
        """, (resource_type, resource_id))

        permissions = []
        for row in cursor.fetchall():
            permissions.append(ResourcePermission(
                id=row[0],
                resource_type=row[1],
                resource_id=row[2],
                user_id=row[3],
                role_id=row[4],
                access_level=row[5],
                granted_at=datetime.fromisoformat(row[6]),
                granted_by=row[7],
                expires_at=datetime.fromisoformat(row[8]) if row[8] else None,
                is_delegated=bool(row[9])
            ))

        return permissions

    def can_perform_action(
        self,
        user_id: int,
        resource_type: str,
        resource_id: int,
        action: str
    ) -> bool:
        """Check if user can perform an action on a resource."""
        # Get user's access level for this resource
        access_level = self._get_user_access_level(user_id, resource_type, resource_id)

        if access_level is None:
            return False

        # Check action permissions based on access level
        return self._action_allowed(access_level, action)

    def _get_user_access_level(
        self,
        user_id: int,
        resource_type: str,
        resource_id: int
    ) -> Optional[str]:
        """Get user's effective access level for a resource."""
        now = datetime.now().isoformat()
        
        # Check direct user permissions
        cursor = self.db.execute("""
            SELECT access_level FROM ResourcePermissions
            WHERE resource_type = ? AND resource_id = ? AND user_id = ?
            AND (expires_at IS NULL OR expires_at > ?)
        """, (resource_type, resource_id, user_id, now))

        row = cursor.fetchone()
        if row:
            return row[0]

        # Check role-based permissions
        cursor = self.db.execute("""
            SELECT rp.access_level FROM ResourcePermissions rp
            JOIN UserRoles ur ON rp.role_id = ur.role_id
            WHERE rp.resource_type = ? AND rp.resource_id = ? AND ur.user_id = ?
            AND (rp.expires_at IS NULL OR rp.expires_at > ?)
            ORDER BY rp.access_level DESC
            LIMIT 1
        """, (resource_type, resource_id, user_id, now))

        row = cursor.fetchone()
        if row:
            return row[0]

        return None

    def _action_allowed(self, access_level: str, action: str) -> bool:
        """Check if action is allowed for given access level."""
        permissions = {
            AccessLevel.OWNER.value: {
                Action.READ.value, Action.WRITE.value, Action.DELETE.value,
                Action.SHARE.value, Action.ADMIN.value, Action.COMMENT.value,
                Action.REVIEW.value, Action.PUBLISH.value, Action.MANAGE_PERMISSIONS.value
            },
            AccessLevel.ADMIN.value: {
                Action.READ.value, Action.WRITE.value, Action.DELETE.value,
                Action.SHARE.value, Action.ADMIN.value, Action.COMMENT.value,
                Action.REVIEW.value, Action.PUBLISH.value, Action.MANAGE_PERMISSIONS.value
            },
            AccessLevel.EDITOR.value: {
                Action.READ.value, Action.WRITE.value, Action.COMMENT.value,
                Action.REVIEW.value, Action.PUBLISH.value
            },
            AccessLevel.REVIEWER.value: {
                Action.READ.value, Action.COMMENT.value, Action.REVIEW.value
            },
            AccessLevel.COMMENTER.value: {
                Action.READ.value, Action.COMMENT.value
            },
            AccessLevel.VIEWER.value: {
                Action.READ.value
            }
        }

        return action in permissions.get(access_level, set())

    def _log_permission_change(
        self,
        user_id: int,
        action: str,
        resource_type: str,
        resource_id: int,
        target_user_id: Optional[int],
        old_value: Optional[str],
        new_value: str,
        reason: Optional[str]
    ):
        """Log a permission change to audit log."""
        with self.db:
            self.db.execute("""
                INSERT INTO PermissionAuditLog
                (user_id, action, resource_type, resource_id, target_user_id, old_value, new_value, reason)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (user_id, action, resource_type, resource_id, target_user_id, old_value, new_value, reason))

            logger.info(
                f"Permission {action}: user={user_id}, resource={resource_type}#{resource_id}, "
                f"target={target_user_id}, {old_value} -> {new_value}"
            )

    def get_permission_audit_log(
        self,
        resource_type: Optional[str] = None,
        resource_id: Optional[int] = None,
        limit: int = 100
    ) -> List[PermissionAuditLog]:
        """Get audit log for permission changes."""
        query = "SELECT id, user_id, action, resource_type, resource_id, target_user_id, old_value, new_value, timestamp, reason FROM PermissionAuditLog"
        params = []
        filters = []

        if resource_type:
            filters.append("resource_type = ?")
            params.append(resource_type)

        if resource_id:
            filters.append("resource_id = ?")
            params.append(resource_id)

        if filters:
            query += " WHERE " + " AND ".join(filters)

        query += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)

        cursor = self.db.execute(query, params)
        logs = []
        for row in cursor.fetchall():
            logs.append(PermissionAuditLog(
                id=row[0],
                user_id=row[1],
                action=row[2],
                resource_type=row[3],
                resource_id=row[4],
                target_user_id=row[5],
                old_value=row[6],
                new_value=row[7],
                timestamp=datetime.fromisoformat(row[8]),
                reason=row[9]
            ))

        return logs

    def add_organization_member(
        self,
        organization_id: int,
        user_id: int,
        role: str = "member"
    ) -> bool:
        """Add a member to an organization."""
        try:
            with self.db:
                self.db.execute("""
                    INSERT INTO OrganizationMembers (organization_id, user_id, role)
                    VALUES (?, ?, ?)
                """, (organization_id, user_id, role))

                self._log_permission_change(
                    user_id,
                    "org_member_added",
                    "organization",
                    organization_id,
                    user_id,
                    None,
                    role,
                    None
                )

            return True
        except sqlite3.IntegrityError:
            return False

    def remove_organization_member(
        self,
        organization_id: int,
        user_id: int
    ) -> bool:
        """Remove a member from an organization."""
        # Get current role for audit
        cursor = self.db.execute(
            "SELECT role FROM OrganizationMembers WHERE organization_id = ? AND user_id = ?",
            (organization_id, user_id)
        )
        row = cursor.fetchone()
        current_role = row[0] if row else "member"

        with self.db:
            cursor = self.db.execute(
                "DELETE FROM OrganizationMembers WHERE organization_id = ? AND user_id = ?",
                (organization_id, user_id)
            )

            if cursor.rowcount > 0:
                self._log_permission_change(
                    user_id,
                    "org_member_removed",
                    "organization",
                    organization_id,
                    user_id,
                    current_role,
                    "removed",
                    None
                )
                return True

        return False

    def get_organization_members(self, organization_id: int) -> List[Tuple[int, str]]:
        """Get all members of an organization."""
        cursor = self.db.execute("""
            SELECT user_id, role FROM OrganizationMembers
            WHERE organization_id = ?
            ORDER BY joined_at DESC
        """, (organization_id,))

        return [(row[0], row[1]) for row in cursor.fetchall()]
