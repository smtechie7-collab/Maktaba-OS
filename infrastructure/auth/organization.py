"""
Organization and user hierarchy management for Maktaba-OS.

This module provides:
- Organization management
- User hierarchies and team structures
- Department and role management
- User invitations and team joining
- Organization-wide permission inheritance
"""

import sqlite3
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional, Tuple
import logging

logger = logging.getLogger(__name__)


@dataclass
class Organization:
    """Organization data."""
    id: int
    name: str
    description: Optional[str]
    owner_id: int
    created_at: datetime
    is_active: bool


@dataclass
class Department:
    """Department within an organization."""
    id: int
    organization_id: int
    name: str
    description: Optional[str]
    manager_id: Optional[int]
    parent_department_id: Optional[int]
    created_at: datetime


@dataclass
class OrganizationMember:
    """Member of an organization."""
    id: int
    organization_id: int
    user_id: int
    role: str  # owner, admin, manager, member
    department_id: Optional[int]
    joined_at: datetime
    is_active: bool


@dataclass
class TeamInvitation:
    """Invitation to join an organization."""
    id: int
    organization_id: int
    email: str
    invited_by: int
    invited_at: datetime
    expires_at: Optional[datetime]
    role: str
    is_accepted: bool


class OrganizationManager:
    """Manages organizations, departments, and user hierarchies."""

    def __init__(self, db_connection: sqlite3.Connection):
        self.db = db_connection
        self._ensure_schema()

    def _ensure_schema(self):
        """Ensure organization schema exists."""
        with self.db:
            # Organizations table
            self.db.execute("""
                CREATE TABLE IF NOT EXISTS Organizations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    description TEXT,
                    owner_id INTEGER NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    is_active INTEGER DEFAULT 1,
                    FOREIGN KEY (owner_id) REFERENCES Users(id)
                )
            """)

            # Departments table
            self.db.execute("""
                CREATE TABLE IF NOT EXISTS Departments (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    organization_id INTEGER NOT NULL,
                    name TEXT NOT NULL,
                    description TEXT,
                    manager_id INTEGER,
                    parent_department_id INTEGER,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (organization_id) REFERENCES Organizations(id) ON DELETE CASCADE,
                    FOREIGN KEY (manager_id) REFERENCES Users(id),
                    FOREIGN KEY (parent_department_id) REFERENCES Departments(id)
                )
            """)

            # Organization members table
            self.db.execute("""
                CREATE TABLE IF NOT EXISTS OrganizationMembers (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    organization_id INTEGER NOT NULL,
                    user_id INTEGER NOT NULL,
                    role TEXT NOT NULL DEFAULT 'member',
                    department_id INTEGER,
                    joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    is_active INTEGER DEFAULT 1,
                    FOREIGN KEY (organization_id) REFERENCES Organizations(id) ON DELETE CASCADE,
                    FOREIGN KEY (user_id) REFERENCES Users(id) ON DELETE CASCADE,
                    FOREIGN KEY (department_id) REFERENCES Departments(id),
                    UNIQUE(organization_id, user_id)
                )
            """)

            # Team invitations table
            self.db.execute("""
                CREATE TABLE IF NOT EXISTS TeamInvitations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    organization_id INTEGER NOT NULL,
                    email TEXT NOT NULL,
                    invited_by INTEGER NOT NULL,
                    invited_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    expires_at TIMESTAMP,
                    role TEXT NOT NULL DEFAULT 'member',
                    is_accepted INTEGER DEFAULT 0,
                    FOREIGN KEY (organization_id) REFERENCES Organizations(id) ON DELETE CASCADE,
                    FOREIGN KEY (invited_by) REFERENCES Users(id)
                )
            """)

    def create_organization(
        self,
        name: str,
        owner_id: int,
        description: Optional[str] = None
    ) -> Organization:
        """Create a new organization."""
        with self.db:
            cursor = self.db.execute("""
                INSERT INTO Organizations (name, description, owner_id)
                VALUES (?, ?, ?)
            """, (name, description, owner_id))

            org_id = cursor.lastrowid

            # Add owner as member
            self.db.execute("""
                INSERT INTO OrganizationMembers (organization_id, user_id, role)
                VALUES (?, ?, ?)
            """, (org_id, owner_id, "owner"))

            logger.info(f"Organization created: {org_id} - {name} (owner: {owner_id})")

        return self.get_organization(org_id)

    def get_organization(self, org_id: int) -> Optional[Organization]:
        """Get organization by ID."""
        cursor = self.db.execute("""
            SELECT id, name, description, owner_id, created_at, is_active
            FROM Organizations WHERE id = ?
        """, (org_id,))

        row = cursor.fetchone()
        if not row:
            return None

        return Organization(
            id=row[0],
            name=row[1],
            description=row[2],
            owner_id=row[3],
            created_at=datetime.fromisoformat(row[4]),
            is_active=bool(row[5])
        )

    def get_user_organizations(self, user_id: int) -> List[Organization]:
        """Get all organizations a user belongs to."""
        cursor = self.db.execute("""
            SELECT DISTINCT o.id, o.name, o.description, o.owner_id, o.created_at, o.is_active
            FROM Organizations o
            JOIN OrganizationMembers om ON o.id = om.organization_id
            WHERE om.user_id = ? AND om.is_active = 1 AND o.is_active = 1
            ORDER BY o.created_at DESC
        """, (user_id,))

        orgs = []
        for row in cursor.fetchall():
            orgs.append(Organization(
                id=row[0],
                name=row[1],
                description=row[2],
                owner_id=row[3],
                created_at=datetime.fromisoformat(row[4]),
                is_active=bool(row[5])
            ))

        return orgs

    def create_department(
        self,
        organization_id: int,
        name: str,
        manager_id: Optional[int] = None,
        description: Optional[str] = None,
        parent_department_id: Optional[int] = None
    ) -> Department:
        """Create a new department in an organization."""
        with self.db:
            cursor = self.db.execute("""
                INSERT INTO Departments
                (organization_id, name, description, manager_id, parent_department_id)
                VALUES (?, ?, ?, ?, ?)
            """, (organization_id, name, description, manager_id, parent_department_id))

            dept_id = cursor.lastrowid

            logger.info(f"Department created: {dept_id} - {name} in org {organization_id}")

        return self.get_department(dept_id)

    def get_department(self, dept_id: int) -> Optional[Department]:
        """Get department by ID."""
        cursor = self.db.execute("""
            SELECT id, organization_id, name, description, manager_id, parent_department_id, created_at
            FROM Departments WHERE id = ?
        """, (dept_id,))

        row = cursor.fetchone()
        if not row:
            return None

        return Department(
            id=row[0],
            organization_id=row[1],
            name=row[2],
            description=row[3],
            manager_id=row[4],
            parent_department_id=row[5],
            created_at=datetime.fromisoformat(row[6])
        )

    def get_organization_departments(self, org_id: int) -> List[Department]:
        """Get all departments in an organization."""
        cursor = self.db.execute("""
            SELECT id, organization_id, name, description, manager_id, parent_department_id, created_at
            FROM Departments
            WHERE organization_id = ?
            ORDER BY parent_department_id, name
        """, (org_id,))

        depts = []
        for row in cursor.fetchall():
            depts.append(Department(
                id=row[0],
                organization_id=row[1],
                name=row[2],
                description=row[3],
                manager_id=row[4],
                parent_department_id=row[5],
                created_at=datetime.fromisoformat(row[6])
            ))

        return depts

    def add_member(
        self,
        organization_id: int,
        user_id: int,
        role: str = "member",
        department_id: Optional[int] = None
    ) -> Optional[OrganizationMember]:
        """Add a member to an organization."""
        try:
            with self.db:
                self.db.execute("""
                    INSERT INTO OrganizationMembers
                    (organization_id, user_id, role, department_id)
                    VALUES (?, ?, ?, ?)
                """, (organization_id, user_id, role, department_id))

                logger.info(f"User {user_id} added to organization {organization_id} as {role}")

            return self.get_member(organization_id, user_id)
        except sqlite3.IntegrityError:
            logger.warning(f"User {user_id} already member of organization {organization_id}")
            return None

    def get_member(
        self,
        organization_id: int,
        user_id: int
    ) -> Optional[OrganizationMember]:
        """Get organization member info."""
        cursor = self.db.execute("""
            SELECT id, organization_id, user_id, role, department_id, joined_at, is_active
            FROM OrganizationMembers
            WHERE organization_id = ? AND user_id = ?
        """, (organization_id, user_id))

        row = cursor.fetchone()
        if not row:
            return None

        return OrganizationMember(
            id=row[0],
            organization_id=row[1],
            user_id=row[2],
            role=row[3],
            department_id=row[4],
            joined_at=datetime.fromisoformat(row[5]),
            is_active=bool(row[6])
        )

    def get_organization_members(
        self,
        organization_id: int,
        department_id: Optional[int] = None
    ) -> List[OrganizationMember]:
        """Get all members of an organization."""
        if department_id:
            cursor = self.db.execute("""
                SELECT id, organization_id, user_id, role, department_id, joined_at, is_active
                FROM OrganizationMembers
                WHERE organization_id = ? AND department_id = ? AND is_active = 1
                ORDER BY role DESC, joined_at ASC
            """, (organization_id, department_id))
        else:
            cursor = self.db.execute("""
                SELECT id, organization_id, user_id, role, department_id, joined_at, is_active
                FROM OrganizationMembers
                WHERE organization_id = ? AND is_active = 1
                ORDER BY role DESC, joined_at ASC
            """, (organization_id,))

        members = []
        for row in cursor.fetchall():
            members.append(OrganizationMember(
                id=row[0],
                organization_id=row[1],
                user_id=row[2],
                role=row[3],
                department_id=row[4],
                joined_at=datetime.fromisoformat(row[5]),
                is_active=bool(row[6])
            ))

        return members

    def update_member_role(
        self,
        organization_id: int,
        user_id: int,
        new_role: str
    ) -> bool:
        """Update a member's role in the organization."""
        with self.db:
            cursor = self.db.execute("""
                UPDATE OrganizationMembers
                SET role = ?
                WHERE organization_id = ? AND user_id = ?
            """, (new_role, organization_id, user_id))

            if cursor.rowcount > 0:
                logger.info(f"User {user_id} role updated to {new_role} in org {organization_id}")
                return True

        return False

    def remove_member(
        self,
        organization_id: int,
        user_id: int
    ) -> bool:
        """Remove a member from an organization."""
        with self.db:
            cursor = self.db.execute("""
                UPDATE OrganizationMembers
                SET is_active = 0
                WHERE organization_id = ? AND user_id = ?
            """, (organization_id, user_id))

            if cursor.rowcount > 0:
                logger.info(f"User {user_id} removed from organization {organization_id}")
                return True

        return False

    def invite_user(
        self,
        organization_id: int,
        email: str,
        invited_by: int,
        role: str = "member",
        expires_at: Optional[datetime] = None
    ) -> Optional[TeamInvitation]:
        """Invite a user to join an organization."""
        try:
            with self.db:
                cursor = self.db.execute("""
                    INSERT INTO TeamInvitations
                    (organization_id, email, invited_by, role, expires_at)
                    VALUES (?, ?, ?, ?, ?)
                """, (organization_id, email, invited_by, role, expires_at))

                inv_id = cursor.lastrowid

                logger.info(f"Invitation {inv_id} sent to {email} for org {organization_id}")

            return self.get_invitation(inv_id)
        except sqlite3.IntegrityError:
            logger.warning(f"Invitation already exists for {email} to org {organization_id}")
            return None

    def get_invitation(self, inv_id: int) -> Optional[TeamInvitation]:
        """Get invitation by ID."""
        cursor = self.db.execute("""
            SELECT id, organization_id, email, invited_by, invited_at, expires_at, role, is_accepted
            FROM TeamInvitations WHERE id = ?
        """, (inv_id,))

        row = cursor.fetchone()
        if not row:
            return None

        return TeamInvitation(
            id=row[0],
            organization_id=row[1],
            email=row[2],
            invited_by=row[3],
            invited_at=datetime.fromisoformat(row[4]),
            expires_at=datetime.fromisoformat(row[5]) if row[5] else None,
            role=row[6],
            is_accepted=bool(row[7])
        )

    def accept_invitation(
        self,
        invitation_id: int,
        user_id: int
    ) -> bool:
        """Accept an invitation and add user to organization."""
        with self.db:
            cursor = self.db.execute("""
                SELECT organization_id, role FROM TeamInvitations WHERE id = ?
            """, (invitation_id,))

            row = cursor.fetchone()
            if not row:
                return False

            org_id, role = row

            # Add user to organization
            try:
                self.db.execute("""
                    INSERT INTO OrganizationMembers (organization_id, user_id, role)
                    VALUES (?, ?, ?)
                """, (org_id, user_id, role))
            except sqlite3.IntegrityError:
                # User already member
                pass

            # Mark invitation as accepted
            self.db.execute("""
                UPDATE TeamInvitations SET is_accepted = 1 WHERE id = ?
            """, (invitation_id,))

            logger.info(f"Invitation {invitation_id} accepted by user {user_id}")

        return True

    def get_pending_invitations(self, email: str) -> List[TeamInvitation]:
        """Get pending invitations for an email."""
        now = datetime.now().isoformat()
        cursor = self.db.execute("""
            SELECT id, organization_id, email, invited_by, invited_at, expires_at, role, is_accepted
            FROM TeamInvitations
            WHERE email = ? AND is_accepted = 0
            AND (expires_at IS NULL OR expires_at > ?)
            ORDER BY invited_at DESC
        """, (email, now))

        invitations = []
        for row in cursor.fetchall():
            invitations.append(TeamInvitation(
                id=row[0],
                organization_id=row[1],
                email=row[2],
                invited_by=row[3],
                invited_at=datetime.fromisoformat(row[4]),
                expires_at=datetime.fromisoformat(row[5]) if row[5] else None,
                role=row[6],
                is_accepted=bool(row[7])
            ))

        return invitations

    def get_organization_hierarchy(self, org_id: int) -> Dict:
        """Get complete organization hierarchy."""
        org = self.get_organization(org_id)
        if not org:
            return {}

        depts = self.get_organization_departments(org_id)
        members = self.get_organization_members(org_id)

        # Build hierarchy
        dept_tree = {}
        for dept in depts:
            if dept.parent_department_id is None:
                # Root department
                dept_tree[dept.id] = {
                    "dept": dept,
                    "members": [],
                    "children": []
                }

        # Add sub-departments
        for dept in depts:
            if dept.parent_department_id is not None:
                parent = dept_tree.get(dept.parent_department_id)
                if parent:
                    parent["children"].append({
                        "dept": dept,
                        "members": [],
                        "children": []
                    })

        # Assign members to departments
        for member in members:
            if member.department_id:
                # Find department
                dept = self.get_department(member.department_id)
                if dept and dept.id in dept_tree:
                    dept_tree[dept.id]["members"].append(member)

        return {
            "organization": org,
            "departments": dept_tree,
            "members_count": len(members)
        }
