"""
Tests for enterprise access management integration.
"""

import pytest
import sqlite3
from datetime import datetime
from infrastructure.auth.rbac import GranularAccessControl
from infrastructure.auth.organization import OrganizationManager
from infrastructure.auth.enterprise import EnterpriseAccessManager


@pytest.fixture
def enterprise_manager(tmp_path):
    """Create integrated enterprise manager with in-memory database."""
    db_path = tmp_path / "test_enterprise.db"
    db = sqlite3.connect(str(db_path))

    # Create Users table
    db.execute("""
        CREATE TABLE Users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            email TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL
        )
    """)

    # Create UserRoles table
    db.execute("""
        CREATE TABLE UserRoles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            role_id INTEGER NOT NULL,
            FOREIGN KEY (user_id) REFERENCES Users(id),
            UNIQUE(user_id, role_id)
        )
    """)

    # Add test users
    for i in range(1, 5):
        db.execute(
            "INSERT INTO Users (username, email, password_hash) VALUES (?, ?, ?)",
            (f"user{i}", f"user{i}@example.com", f"hash{i}")
        )
    db.commit()

    # Initialize RBAC first (creates base tables)
    rbac = GranularAccessControl(db)
    
    # Then initialize org manager (creates org-specific tables)
    org_mgr = OrganizationManager(db)
    
    enterprise = EnterpriseAccessManager(rbac, org_mgr)

    yield enterprise
    db.close()


class TestEnterpriseAccessControl:
    """Test enterprise-level access control."""

    def test_grant_organization_permission(self, enterprise_manager):
        """Test granting permission on organization."""
        org = enterprise_manager.org.create_organization("Test Org", 1)

        perm = enterprise_manager.grant_organization_permission(
            org.id,
            user_id=2,
            access_level="editor",
            granted_by=1
        )

        assert perm is not None
        assert perm.access_level == "editor"

    def test_can_manage_organization(self, enterprise_manager):
        """Test checking management permissions."""
        org = enterprise_manager.org.create_organization("Test Org", 1)

        # Owner can manage
        assert enterprise_manager.can_manage_organization(1, org.id) is True

        # Non-member cannot manage
        assert enterprise_manager.can_manage_organization(2, org.id) is False

        # Admin member can manage
        enterprise_manager.org.add_member(org.id, 2, role="admin")
        assert enterprise_manager.can_manage_organization(2, org.id) is True

    def test_can_access_organization(self, enterprise_manager):
        """Test checking read access to organization."""
        org = enterprise_manager.org.create_organization("Test Org", 1)

        # Owner can access
        assert enterprise_manager.can_access_organization(1, org.id) is True

        # Non-member cannot access
        assert enterprise_manager.can_access_organization(2, org.id) is False

        # Member can access
        enterprise_manager.org.add_member(org.id, 2, role="member")
        assert enterprise_manager.can_access_organization(2, org.id) is True

    def test_get_organization_access_report(self, enterprise_manager):
        """Test generating access report."""
        org = enterprise_manager.org.create_organization("Test Org", 1)
        enterprise_manager.org.add_member(org.id, 2, role="admin")
        enterprise_manager.org.add_member(org.id, 3, role="member")

        dept = enterprise_manager.org.create_department(org.id, "Engineering", 1)

        report = enterprise_manager.get_organization_access_report(org.id)

        assert report["organization"].name == "Test Org"
        assert report["total_members"] == 3
        assert report["total_departments"] == 1
        assert "owner" in report["members_by_role"]

    def test_assign_document_to_department(self, enterprise_manager):
        """Test assigning document to department."""
        org = enterprise_manager.org.create_organization("Test Org", 1)
        dept = enterprise_manager.org.create_department(org.id, "Engineering", 1)

        enterprise_manager.org.add_member(org.id, 2, department_id=dept.id)
        enterprise_manager.org.add_member(org.id, 3, department_id=dept.id)

        assigned = enterprise_manager.assign_document_to_department(
            document_id=1,
            organization_id=org.id,
            department_id=dept.id,
            access_level="editor"
        )

        assert assigned is True


class TestEnterprisePermissionPropagation:
    """Test permission propagation in enterprise."""

    def test_revoke_organization_access(self, enterprise_manager):
        """Test revoking organization access."""
        org = enterprise_manager.org.create_organization("Test Org", 1)
        enterprise_manager.org.add_member(org.id, 2, role="member")

        # Verify access before revoke
        assert enterprise_manager.can_access_organization(2, org.id) is True

        # Revoke access
        removed = enterprise_manager.revoke_organization_access(org.id, 2)

        assert removed is True
        assert enterprise_manager.can_access_organization(2, org.id) is False

    def test_get_effective_permissions(self, enterprise_manager):
        """Test getting effective permissions."""
        org = enterprise_manager.org.create_organization("Test Org", 1)

        enterprise_manager.grant_organization_permission(
            org.id,
            user_id=2,
            access_level="editor",
            granted_by=1
        )

        perms = enterprise_manager.get_effective_permissions(2, "organization", org.id)

        assert perms["user_id"] == 2
        assert perms["effective_access_level"] == "editor"
        assert "editor" in perms["direct_permissions"]


class TestOrganizationHierarchyManagement:
    """Test organization hierarchy creation and management."""

    def test_create_organization_with_hierarchy(self, enterprise_manager):
        """Test creating organization with initial departments."""
        org = enterprise_manager.create_organization_with_hierarchy(
            org_name="Tech Corp",
            owner_id=1,
            departments=[
                {"name": "Engineering", "manager_id": 2},
                {"name": "Sales", "manager_id": 3},
                {"name": "Marketing", "manager_id": 4}
            ]
        )

        assert org.name == "Tech Corp"

        depts = enterprise_manager.org.get_organization_departments(org.id)
        assert len(depts) == 3

    def test_complex_organizational_structure(self, enterprise_manager):
        """Test complex org structure with nested departments."""
        org = enterprise_manager.org.create_organization("Large Corp", 1)

        # Top level departments
        eng = enterprise_manager.org.create_department(org.id, "Engineering", 1)
        sales = enterprise_manager.org.create_department(org.id, "Sales", 2)

        # Sub-departments
        backend = enterprise_manager.org.create_department(
            org.id, "Backend", 2, parent_department_id=eng.id
        )
        frontend = enterprise_manager.org.create_department(
            org.id, "Frontend", 3, parent_department_id=eng.id
        )

        # Add members to departments
        enterprise_manager.org.add_member(org.id, 2, department_id=backend.id)
        enterprise_manager.org.add_member(org.id, 3, department_id=frontend.id)
        enterprise_manager.org.add_member(org.id, 4, department_id=sales.id)

        # Verify hierarchy
        hierarchy = enterprise_manager.org.get_organization_hierarchy(org.id)
        assert hierarchy["members_count"] == 4  # owner + 3 members
