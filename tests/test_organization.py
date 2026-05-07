"""
Tests for organization and user hierarchy management.
"""

import pytest
import sqlite3
from datetime import datetime, timedelta
from infrastructure.auth.organization import OrganizationManager, Organization


@pytest.fixture
def org_manager(tmp_path):
    """Create organization manager with in-memory database."""
    db_path = tmp_path / "test_org.db"
    db = sqlite3.connect(str(db_path))
    
    # Create Users table (required by foreign keys)
    db.execute("""
        CREATE TABLE Users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            email TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL
        )
    """)
    
    # Add test users
    db.execute("INSERT INTO Users (username, email, password_hash) VALUES (?, ?, ?)", 
               ("user1", "user1@example.com", "hash1"))
    db.execute("INSERT INTO Users (username, email, password_hash) VALUES (?, ?, ?)", 
               ("user2", "user2@example.com", "hash2"))
    db.execute("INSERT INTO Users (username, email, password_hash) VALUES (?, ?, ?)", 
               ("user3", "user3@example.com", "hash3"))
    db.commit()
    
    manager = OrganizationManager(db)
    yield manager
    db.close()


class TestOrganizationManagement:
    """Test organization creation and management."""

    def test_create_organization(self, org_manager):
        """Test creating a new organization."""
        org = org_manager.create_organization(
            name="Acme Corp",
            owner_id=1,
            description="A test organization"
        )

        assert org is not None
        assert org.name == "Acme Corp"
        assert org.owner_id == 1
        assert org.is_active is True

    def test_get_organization(self, org_manager):
        """Test retrieving organization."""
        created = org_manager.create_organization("Test Org", 1)
        retrieved = org_manager.get_organization(created.id)

        assert retrieved is not None
        assert retrieved.name == "Test Org"
        assert retrieved.owner_id == 1

    def test_get_user_organizations(self, org_manager):
        """Test retrieving user's organizations."""
        org1 = org_manager.create_organization("Org1", 1)
        org2 = org_manager.create_organization("Org2", 1)
        org3 = org_manager.create_organization("Org3", 2)

        user1_orgs = org_manager.get_user_organizations(1)
        user2_orgs = org_manager.get_user_organizations(2)

        assert len(user1_orgs) == 2
        assert len(user2_orgs) == 1
        assert any(o.name == "Org1" for o in user1_orgs)
        assert user2_orgs[0].name == "Org3"

    def test_organization_owner_is_member(self, org_manager):
        """Test that organization creator is added as member."""
        org = org_manager.create_organization("Test Org", 1)
        member = org_manager.get_member(org.id, 1)

        assert member is not None
        assert member.role == "owner"


class TestDepartmentManagement:
    """Test department management."""

    def test_create_department(self, org_manager):
        """Test creating a department."""
        org = org_manager.create_organization("Test Org", 1)
        dept = org_manager.create_department(
            organization_id=org.id,
            name="Engineering",
            manager_id=1,
            description="Engineering department"
        )

        assert dept is not None
        assert dept.name == "Engineering"
        assert dept.manager_id == 1
        assert dept.organization_id == org.id

    def test_get_organization_departments(self, org_manager):
        """Test retrieving departments in organization."""
        org = org_manager.create_organization("Test Org", 1)
        dept1 = org_manager.create_department(org.id, "Engineering", 1)
        dept2 = org_manager.create_department(org.id, "Sales", 2)

        depts = org_manager.get_organization_departments(org.id)

        assert len(depts) == 2
        assert any(d.name == "Engineering" for d in depts)
        assert any(d.name == "Sales" for d in depts)

    def test_create_sub_department(self, org_manager):
        """Test creating nested departments."""
        org = org_manager.create_organization("Test Org", 1)
        parent = org_manager.create_department(org.id, "Engineering", 1)
        child = org_manager.create_department(
            org.id, "Backend", 2, parent_department_id=parent.id
        )

        assert child.parent_department_id == parent.id
        retrieved = org_manager.get_department(child.id)
        assert retrieved.parent_department_id == parent.id


class TestMemberManagement:
    """Test member management."""

    def test_add_member(self, org_manager):
        """Test adding a member to organization."""
        org = org_manager.create_organization("Test Org", 1)
        member = org_manager.add_member(org.id, 2, role="editor")

        assert member is not None
        assert member.user_id == 2
        assert member.role == "editor"
        assert member.is_active is True

    def test_get_member(self, org_manager):
        """Test retrieving member info."""
        org = org_manager.create_organization("Test Org", 1)
        org_manager.add_member(org.id, 2, role="member")

        member = org_manager.get_member(org.id, 2)

        assert member is not None
        assert member.user_id == 2
        assert member.role == "member"

    def test_get_organization_members(self, org_manager):
        """Test retrieving all members of organization."""
        org = org_manager.create_organization("Test Org", 1)
        org_manager.add_member(org.id, 2, role="editor")
        org_manager.add_member(org.id, 3, role="viewer")

        members = org_manager.get_organization_members(org.id)

        assert len(members) == 3  # owner + 2 added members
        assert any(m.user_id == 1 and m.role == "owner" for m in members)
        assert any(m.user_id == 2 and m.role == "editor" for m in members)
        assert any(m.user_id == 3 and m.role == "viewer" for m in members)

    def test_update_member_role(self, org_manager):
        """Test updating member role."""
        org = org_manager.create_organization("Test Org", 1)
        org_manager.add_member(org.id, 2, role="member")

        updated = org_manager.update_member_role(org.id, 2, "admin")

        assert updated is True
        member = org_manager.get_member(org.id, 2)
        assert member.role == "admin"

    def test_remove_member(self, org_manager):
        """Test removing member from organization."""
        org = org_manager.create_organization("Test Org", 1)
        org_manager.add_member(org.id, 2, role="member")

        removed = org_manager.remove_member(org.id, 2)

        assert removed is True
        member = org_manager.get_member(org.id, 2)
        assert member.is_active is False

    def test_add_member_to_department(self, org_manager):
        """Test adding member to specific department."""
        org = org_manager.create_organization("Test Org", 1)
        dept = org_manager.create_department(org.id, "Engineering", 1)
        member = org_manager.add_member(org.id, 2, role="member", department_id=dept.id)

        assert member.department_id == dept.id
        retrieved = org_manager.get_member(org.id, 2)
        assert retrieved.department_id == dept.id

    def test_get_department_members(self, org_manager):
        """Test retrieving members of a specific department."""
        org = org_manager.create_organization("Test Org", 1)
        dept1 = org_manager.create_department(org.id, "Engineering", 1)
        dept2 = org_manager.create_department(org.id, "Sales", 2)

        org_manager.add_member(org.id, 2, department_id=dept1.id)
        org_manager.add_member(org.id, 3, department_id=dept2.id)

        eng_members = org_manager.get_organization_members(org.id, dept1.id)
        sales_members = org_manager.get_organization_members(org.id, dept2.id)

        assert len(eng_members) == 1
        assert eng_members[0].user_id == 2
        assert len(sales_members) == 1
        assert sales_members[0].user_id == 3


class TestTeamInvitations:
    """Test team invitation system."""

    def test_invite_user(self, org_manager):
        """Test inviting user to organization."""
        org = org_manager.create_organization("Test Org", 1)
        invitation = org_manager.invite_user(
            org.id,
            "newuser@example.com",
            invited_by=1,
            role="member"
        )

        assert invitation is not None
        assert invitation.email == "newuser@example.com"
        assert invitation.role == "member"
        assert invitation.is_accepted is False

    def test_get_invitation(self, org_manager):
        """Test retrieving invitation."""
        org = org_manager.create_organization("Test Org", 1)
        created = org_manager.invite_user(org.id, "new@example.com", 1)
        retrieved = org_manager.get_invitation(created.id)

        assert retrieved is not None
        assert retrieved.email == "new@example.com"

    def test_accept_invitation(self, org_manager):
        """Test accepting invitation and joining organization."""
        org = org_manager.create_organization("Test Org", 1)

        invitation = org_manager.invite_user(org.id, "user3@example.com", 1, "editor")
        accepted = org_manager.accept_invitation(invitation.id, 3)

        assert accepted is True
        member = org_manager.get_member(org.id, 3)
        assert member is not None
        assert member.role == "editor"
        assert member.is_active is True

    def test_get_pending_invitations(self, org_manager):
        """Test retrieving pending invitations for email."""
        org1 = org_manager.create_organization("Org1", 1)
        org2 = org_manager.create_organization("Org2", 2)

        org_manager.invite_user(org1.id, "user@example.com", 1)
        org_manager.invite_user(org2.id, "user@example.com", 2)

        invitations = org_manager.get_pending_invitations("user@example.com")

        assert len(invitations) == 2

    def test_invitation_expiry(self, org_manager):
        """Test that expired invitations are not returned."""
        org = org_manager.create_organization("Test Org", 1)
        
        # Create invitation that expires in the past
        expires_at = datetime.now() - timedelta(hours=1)
        org_manager.invite_user(org.id, "user@example.com", 1, expires_at=expires_at)

        # Create active invitation
        org_manager.invite_user(org.id, "active@example.com", 1)

        pending = org_manager.get_pending_invitations("user@example.com")
        assert len(pending) == 0

        pending_active = org_manager.get_pending_invitations("active@example.com")
        assert len(pending_active) == 1


class TestOrganizationHierarchy:
    """Test organization hierarchy retrieval."""

    def test_get_organization_hierarchy(self, org_manager):
        """Test retrieving complete organization structure."""
        org = org_manager.create_organization("Test Org", 1)
        eng = org_manager.create_department(org.id, "Engineering", 1)
        backend = org_manager.create_department(
            org.id, "Backend", 2, parent_department_id=eng.id
        )

        org_manager.add_member(org.id, 2, department_id=eng.id)
        org_manager.add_member(org.id, 3, department_id=backend.id)

        hierarchy = org_manager.get_organization_hierarchy(org.id)

        assert hierarchy["organization"].name == "Test Org"
        assert hierarchy["members_count"] == 3  # owner + 2 members
        assert len(hierarchy["departments"]) > 0

    def test_hierarchy_with_nested_departments(self, org_manager):
        """Test hierarchy with multiple nesting levels."""
        org = org_manager.create_organization("Test Org", 1)
        level1 = org_manager.create_department(org.id, "Level1", 1)
        level2 = org_manager.create_department(
            org.id, "Level2", 2, parent_department_id=level1.id
        )

        hierarchy = org_manager.get_organization_hierarchy(org.id)

        assert hierarchy is not None
        assert hierarchy["organization"].name == "Test Org"
