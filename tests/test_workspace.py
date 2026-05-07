"""
Tests for team workspace and project management.
"""

import sqlite3
from datetime import datetime, timedelta

import pytest

from infrastructure.auth.organization import OrganizationManager
from infrastructure.auth.audit import ComplianceAuditManager
from infrastructure.auth.workspace import WorkspaceManager


@pytest.fixture
def db_connection():
    """Create an in-memory database for workspace tests."""
    conn = sqlite3.connect(":memory:")

    conn.execute("""
        CREATE TABLE Users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            email TEXT UNIQUE,
            password_hash TEXT NOT NULL
        )
    """)

    for user_id in range(1, 5):
        conn.execute(
            "INSERT INTO Users (username, email, password_hash) VALUES (?, ?, ?)",
            (f"user{user_id}", f"user{user_id}@example.com", f"hash{user_id}")
        )

    conn.commit()
    return conn


@pytest.fixture
def managers(db_connection):
    """Create organization and workspace managers."""
    org = OrganizationManager(db_connection)
    workspace = WorkspaceManager(db_connection)
    audit = ComplianceAuditManager(db_connection)
    return org, workspace, audit


def test_create_workspace_adds_owner_member(managers):
    """Creating a workspace should add the creator as owner."""
    org, workspace, _audit = managers
    organization = org.create_organization("Publishing Team", 1)

    created = workspace.create_workspace(organization.id, "Editorial", created_by=1)

    assert created.name == "Editorial"
    assert created.organization_id == organization.id

    owner = workspace.get_workspace_member(created.id, 1)
    assert owner is not None
    assert owner.role == "owner"


def test_add_workspace_member_and_list_user_workspaces(managers):
    """Workspace members should see their active workspaces."""
    org, workspace, _audit = managers
    organization = org.create_organization("Publishing Team", 1)
    created = workspace.create_workspace(organization.id, "Translations", created_by=1)

    member = workspace.add_workspace_member(created.id, 2, role="editor")

    assert member is not None
    assert member.role == "editor"

    workspaces = workspace.get_user_workspaces(2, organization_id=organization.id)
    assert len(workspaces) == 1
    assert workspaces[0].name == "Translations"


def test_create_project_adds_owner_assignment(managers):
    """Creating a project should add the owner as project owner."""
    org, workspace, _audit = managers
    organization = org.create_organization("Publishing Team", 1)
    created = workspace.create_workspace(organization.id, "Books", created_by=1)
    due_at = datetime.now() + timedelta(days=14)

    project = workspace.create_project(
        created.id,
        "Ramadan Reader",
        owner_id=1,
        description="Seasonal multilingual release",
        due_at=due_at
    )

    assert project.name == "Ramadan Reader"
    assert project.status == "planning"
    assert project.due_at is not None

    members = workspace.get_project_members(project.id)
    assert len(members) == 1
    assert members[0].role == "owner"


def test_assign_project_member_and_update_status(managers):
    """Projects should support member assignment and workflow status changes."""
    org, workspace, _audit = managers
    organization = org.create_organization("Publishing Team", 1)
    created = workspace.create_workspace(organization.id, "Audio", created_by=1)
    project = workspace.create_project(created.id, "Narration QA", owner_id=1)

    assignment = workspace.assign_project_member(project.id, 2, role="reviewer", performed_by=1)
    updated = workspace.update_project_status(project.id, "in_review", performed_by=1)

    assert assignment is not None
    assert assignment.role == "reviewer"
    assert updated is True
    assert workspace.get_project(project.id).status == "in_review"

    projects = workspace.get_workspace_projects(created.id)
    assert [item.name for item in projects] == ["Narration QA"]


def test_workspace_and_project_actions_write_audit_events(managers):
    """Workspace and project actions should produce a compliance trail."""
    org, workspace, audit = managers
    organization = org.create_organization("Publishing Team", 1)
    created = workspace.create_workspace(organization.id, "Compliance", created_by=1)
    workspace.add_workspace_member(created.id, 2, role="editor", performed_by=1)
    project = workspace.create_project(created.id, "Audit Trail", owner_id=1)
    workspace.assign_project_member(project.id, 2, role="reviewer", performed_by=1)
    workspace.update_project_status(project.id, "approved", performed_by=1)

    workspace_events = audit.get_resource_timeline("workspace", created.id)
    project_events = audit.get_resource_timeline("project", project.id)

    assert [event.action for event in workspace_events] == [
        "workspace.member.add",
        "workspace.create",
    ]
    project_actions = [
        event.action for event in project_events
        if event.action != "notification.create"
    ]
    assert project_actions == [
        "project.status.update",
        "project.member.assign",
        "project.create",
    ]
    assert project_events[0].details == "Project status changed from planning to approved"
