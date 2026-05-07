"""
Team workspace and project management for Maktaba-OS.

This module provides the collaboration container above organizations:
- Workspaces scoped to an organization
- Workspace membership
- Project records for grouped publishing work
- Project member assignment and status tracking
"""

import logging
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional

from infrastructure.auth.audit import ComplianceAuditManager
from infrastructure.auth.notifications import NotificationManager

logger = logging.getLogger(__name__)


@dataclass
class Workspace:
    """Team workspace inside an organization."""
    id: int
    organization_id: int
    name: str
    description: Optional[str]
    created_by: int
    created_at: datetime
    is_active: bool


@dataclass
class WorkspaceMember:
    """Member of a team workspace."""
    id: int
    workspace_id: int
    user_id: int
    role: str
    joined_at: datetime
    is_active: bool


@dataclass
class Project:
    """Publishing project inside a workspace."""
    id: int
    workspace_id: int
    name: str
    description: Optional[str]
    status: str
    owner_id: int
    due_at: Optional[datetime]
    created_at: datetime
    is_active: bool


@dataclass
class ProjectMember:
    """Project assignment for a workspace member."""
    id: int
    project_id: int
    user_id: int
    role: str
    assigned_at: datetime
    is_active: bool


class WorkspaceManager:
    """Manages team workspaces and project assignments."""

    def __init__(
        self,
        db_connection: sqlite3.Connection,
        audit_manager: Optional[ComplianceAuditManager] = None,
        notification_manager: Optional[NotificationManager] = None
    ):
        self.db = db_connection
        self._ensure_schema()
        self.audit = audit_manager or ComplianceAuditManager(db_connection)
        self.notifications = notification_manager or NotificationManager(db_connection, self.audit)

    def _ensure_schema(self):
        """Ensure workspace and project schema exists."""
        with self.db:
            self.db.execute("""
                CREATE TABLE IF NOT EXISTS Workspaces (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    organization_id INTEGER NOT NULL,
                    name TEXT NOT NULL,
                    description TEXT,
                    created_by INTEGER NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    is_active INTEGER DEFAULT 1,
                    FOREIGN KEY (organization_id) REFERENCES Organizations(id) ON DELETE CASCADE,
                    FOREIGN KEY (created_by) REFERENCES Users(id),
                    UNIQUE(organization_id, name)
                )
            """)

            self.db.execute("""
                CREATE TABLE IF NOT EXISTS WorkspaceMembers (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    workspace_id INTEGER NOT NULL,
                    user_id INTEGER NOT NULL,
                    role TEXT NOT NULL DEFAULT 'member',
                    joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    is_active INTEGER DEFAULT 1,
                    FOREIGN KEY (workspace_id) REFERENCES Workspaces(id) ON DELETE CASCADE,
                    FOREIGN KEY (user_id) REFERENCES Users(id) ON DELETE CASCADE,
                    UNIQUE(workspace_id, user_id)
                )
            """)

            self.db.execute("""
                CREATE TABLE IF NOT EXISTS Projects (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    workspace_id INTEGER NOT NULL,
                    name TEXT NOT NULL,
                    description TEXT,
                    status TEXT NOT NULL DEFAULT 'planning',
                    owner_id INTEGER NOT NULL,
                    due_at TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    is_active INTEGER DEFAULT 1,
                    FOREIGN KEY (workspace_id) REFERENCES Workspaces(id) ON DELETE CASCADE,
                    FOREIGN KEY (owner_id) REFERENCES Users(id),
                    UNIQUE(workspace_id, name)
                )
            """)

            self.db.execute("""
                CREATE TABLE IF NOT EXISTS ProjectMembers (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    project_id INTEGER NOT NULL,
                    user_id INTEGER NOT NULL,
                    role TEXT NOT NULL DEFAULT 'contributor',
                    assigned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    is_active INTEGER DEFAULT 1,
                    FOREIGN KEY (project_id) REFERENCES Projects(id) ON DELETE CASCADE,
                    FOREIGN KEY (user_id) REFERENCES Users(id) ON DELETE CASCADE,
                    UNIQUE(project_id, user_id)
                )
            """)

    def create_workspace(
        self,
        organization_id: int,
        name: str,
        created_by: int,
        description: Optional[str] = None
    ) -> Workspace:
        """Create a workspace and add the creator as owner."""
        with self.db:
            cursor = self.db.execute("""
                INSERT INTO Workspaces (organization_id, name, description, created_by)
                VALUES (?, ?, ?, ?)
            """, (organization_id, name, description, created_by))
            workspace_id = cursor.lastrowid

            self.db.execute("""
                INSERT INTO WorkspaceMembers (workspace_id, user_id, role)
                VALUES (?, ?, ?)
            """, (workspace_id, created_by, "owner"))

            self.audit.record_event(
                action="workspace.create",
                resource_type="workspace",
                resource_id=workspace_id,
                user_id=created_by,
                details=f"Created workspace '{name}' in organization {organization_id}",
            )

            logger.info("Workspace created: %s in org %s", name, organization_id)

        return self.get_workspace(workspace_id)

    def get_workspace(self, workspace_id: int) -> Optional[Workspace]:
        """Get workspace by ID."""
        row = self.db.execute("""
            SELECT id, organization_id, name, description, created_by, created_at, is_active
            FROM Workspaces
            WHERE id = ?
        """, (workspace_id,)).fetchone()

        if not row:
            return None

        return Workspace(
            id=row[0],
            organization_id=row[1],
            name=row[2],
            description=row[3],
            created_by=row[4],
            created_at=datetime.fromisoformat(row[5]),
            is_active=bool(row[6])
        )

    def add_workspace_member(
        self,
        workspace_id: int,
        user_id: int,
        role: str = "member",
        performed_by: Optional[int] = None
    ) -> Optional[WorkspaceMember]:
        """Add a user to a workspace."""
        try:
            with self.db:
                self.db.execute("""
                    INSERT INTO WorkspaceMembers (workspace_id, user_id, role)
                    VALUES (?, ?, ?)
                """, (workspace_id, user_id, role))
                self.audit.record_event(
                    action="workspace.member.add",
                    resource_type="workspace",
                    resource_id=workspace_id,
                    user_id=performed_by or user_id,
                    details=f"Added user {user_id} to workspace {workspace_id} as {role}",
                )
            return self.get_workspace_member(workspace_id, user_id)
        except sqlite3.IntegrityError:
            return None

    def get_workspace_member(self, workspace_id: int, user_id: int) -> Optional[WorkspaceMember]:
        """Get workspace membership record."""
        row = self.db.execute("""
            SELECT id, workspace_id, user_id, role, joined_at, is_active
            FROM WorkspaceMembers
            WHERE workspace_id = ? AND user_id = ?
        """, (workspace_id, user_id)).fetchone()

        if not row:
            return None

        return WorkspaceMember(
            id=row[0],
            workspace_id=row[1],
            user_id=row[2],
            role=row[3],
            joined_at=datetime.fromisoformat(row[4]),
            is_active=bool(row[5])
        )

    def get_user_workspaces(self, user_id: int, organization_id: Optional[int] = None) -> List[Workspace]:
        """Get all active workspaces a user belongs to."""
        params = [user_id]
        org_filter = ""
        if organization_id is not None:
            org_filter = " AND w.organization_id = ?"
            params.append(organization_id)

        cursor = self.db.execute(f"""
            SELECT w.id, w.organization_id, w.name, w.description, w.created_by, w.created_at, w.is_active
            FROM Workspaces w
            JOIN WorkspaceMembers wm ON w.id = wm.workspace_id
            WHERE wm.user_id = ? AND wm.is_active = 1 AND w.is_active = 1{org_filter}
            ORDER BY w.created_at DESC
        """, params)

        return [
            Workspace(
                id=row[0],
                organization_id=row[1],
                name=row[2],
                description=row[3],
                created_by=row[4],
                created_at=datetime.fromisoformat(row[5]),
                is_active=bool(row[6])
            )
            for row in cursor.fetchall()
        ]

    def create_project(
        self,
        workspace_id: int,
        name: str,
        owner_id: int,
        description: Optional[str] = None,
        due_at: Optional[datetime] = None
    ) -> Project:
        """Create a project and assign the owner."""
        with self.db:
            cursor = self.db.execute("""
                INSERT INTO Projects (workspace_id, name, description, owner_id, due_at)
                VALUES (?, ?, ?, ?, ?)
            """, (workspace_id, name, description, owner_id, due_at))
            project_id = cursor.lastrowid

            self.db.execute("""
                INSERT INTO ProjectMembers (project_id, user_id, role)
                VALUES (?, ?, ?)
            """, (project_id, owner_id, "owner"))

            self.audit.record_event(
                action="project.create",
                resource_type="project",
                resource_id=project_id,
                user_id=owner_id,
                details=f"Created project '{name}' in workspace {workspace_id}",
            )
            if due_at:
                self.notifications.schedule_deadline_reminder(
                    user_id=owner_id,
                    resource_type="project",
                    resource_id=project_id,
                    title=name,
                    due_at=due_at,
                )

            logger.info("Project created: %s in workspace %s", name, workspace_id)

        return self.get_project(project_id)

    def get_project(self, project_id: int) -> Optional[Project]:
        """Get project by ID."""
        row = self.db.execute("""
            SELECT id, workspace_id, name, description, status, owner_id, due_at, created_at, is_active
            FROM Projects
            WHERE id = ?
        """, (project_id,)).fetchone()

        if not row:
            return None

        return Project(
            id=row[0],
            workspace_id=row[1],
            name=row[2],
            description=row[3],
            status=row[4],
            owner_id=row[5],
            due_at=datetime.fromisoformat(row[6]) if row[6] else None,
            created_at=datetime.fromisoformat(row[7]),
            is_active=bool(row[8])
        )

    def get_workspace_projects(self, workspace_id: int, include_inactive: bool = False) -> List[Project]:
        """Get projects in a workspace."""
        active_filter = "" if include_inactive else " AND is_active = 1"
        cursor = self.db.execute(f"""
            SELECT id, workspace_id, name, description, status, owner_id, due_at, created_at, is_active
            FROM Projects
            WHERE workspace_id = ?{active_filter}
            ORDER BY created_at DESC
        """, (workspace_id,))

        return [
            Project(
                id=row[0],
                workspace_id=row[1],
                name=row[2],
                description=row[3],
                status=row[4],
                owner_id=row[5],
                due_at=datetime.fromisoformat(row[6]) if row[6] else None,
                created_at=datetime.fromisoformat(row[7]),
                is_active=bool(row[8])
            )
            for row in cursor.fetchall()
        ]

    def update_project_status(
        self,
        project_id: int,
        status: str,
        performed_by: Optional[int] = None
    ) -> bool:
        """Update project workflow status."""
        with self.db:
            current = self.get_project(project_id)
            cursor = self.db.execute("""
                UPDATE Projects
                SET status = ?
                WHERE id = ? AND is_active = 1
            """, (status, project_id))
            updated = cursor.rowcount > 0
            if updated:
                self.audit.record_event(
                    action="project.status.update",
                    resource_type="project",
                    resource_id=project_id,
                    user_id=performed_by or (current.owner_id if current else None),
                    details=f"Project status changed from {current.status if current else 'unknown'} to {status}",
                )
            return updated

    def assign_project_member(
        self,
        project_id: int,
        user_id: int,
        role: str = "contributor",
        performed_by: Optional[int] = None
    ) -> Optional[ProjectMember]:
        """Assign a user to a project."""
        try:
            with self.db:
                self.db.execute("""
                    INSERT INTO ProjectMembers (project_id, user_id, role)
                    VALUES (?, ?, ?)
                """, (project_id, user_id, role))
                self.audit.record_event(
                    action="project.member.assign",
                    resource_type="project",
                    resource_id=project_id,
                    user_id=performed_by or user_id,
                    details=f"Assigned user {user_id} to project {project_id} as {role}",
                )
                project = self.get_project(project_id)
                self.notifications.notify_project_assignment(
                    project_id=project_id,
                    user_id=user_id,
                    project_name=project.name if project else f"Project {project_id}",
                    role=role,
                )
                if project and project.due_at:
                    self.notifications.schedule_deadline_reminder(
                        user_id=user_id,
                        resource_type="project",
                        resource_id=project_id,
                        title=project.name,
                        due_at=project.due_at,
                    )
            return self.get_project_member(project_id, user_id)
        except sqlite3.IntegrityError:
            return None

    def get_project_member(self, project_id: int, user_id: int) -> Optional[ProjectMember]:
        """Get project member assignment."""
        row = self.db.execute("""
            SELECT id, project_id, user_id, role, assigned_at, is_active
            FROM ProjectMembers
            WHERE project_id = ? AND user_id = ?
        """, (project_id, user_id)).fetchone()

        if not row:
            return None

        return ProjectMember(
            id=row[0],
            project_id=row[1],
            user_id=row[2],
            role=row[3],
            assigned_at=datetime.fromisoformat(row[4]),
            is_active=bool(row[5])
        )

    def get_project_members(self, project_id: int) -> List[ProjectMember]:
        """Get active project member assignments."""
        cursor = self.db.execute("""
            SELECT id, project_id, user_id, role, assigned_at, is_active
            FROM ProjectMembers
            WHERE project_id = ? AND is_active = 1
            ORDER BY assigned_at ASC
        """, (project_id,))

        return [
            ProjectMember(
                id=row[0],
                project_id=row[1],
                user_id=row[2],
                role=row[3],
                assigned_at=datetime.fromisoformat(row[4]),
                is_active=bool(row[5])
            )
            for row in cursor.fetchall()
        ]
