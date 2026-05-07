"""
Tests for notifications and reminders.
"""

import sqlite3
from datetime import datetime, timedelta

import pytest

from infrastructure.auth.audit import ComplianceAuditManager
from infrastructure.auth.notifications import NotificationManager
from infrastructure.auth.organization import OrganizationManager
from infrastructure.auth.workspace import WorkspaceManager
from infrastructure.auth.workflow import WorkflowManager


@pytest.fixture
def managers():
    """Create notification test managers."""
    conn = sqlite3.connect(":memory:")
    conn.execute("""
        CREATE TABLE Users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            email TEXT UNIQUE,
            password_hash TEXT NOT NULL
        )
    """)
    for user_id in range(1, 4):
        conn.execute(
            "INSERT INTO Users (username, email, password_hash) VALUES (?, ?, ?)",
            (f"user{user_id}", f"user{user_id}@example.com", f"hash{user_id}")
        )
    conn.commit()

    audit = ComplianceAuditManager(conn)
    notifications = NotificationManager(conn, audit)
    org = OrganizationManager(conn)
    workspace = WorkspaceManager(conn, audit, notifications)
    workflow = WorkflowManager(conn, audit, notifications)
    return conn, audit, notifications, org, workspace, workflow


def test_create_notification_and_mark_read(managers):
    """Notifications should appear in the user's unread inbox until read."""
    _conn, _audit, notifications, _org, _workspace, _workflow = managers

    created = notifications.create_notification(
        user_id=1,
        notification_type="manual",
        title="Review needed",
        message="Please review the draft.",
        resource_type="project",
        resource_id=4,
    )

    unread = notifications.get_user_notifications(1)
    assert unread[0].id == created.id

    assert notifications.mark_read(created.id) is True
    assert notifications.get_user_notifications(1) == []
    assert notifications.get_user_notifications(1, include_read=True)[0].read_at is not None


def test_scheduled_deadline_reminder_becomes_due(managers):
    """Scheduled reminders should be queryable when their delivery time arrives."""
    _conn, _audit, notifications, _org, _workspace, _workflow = managers
    due_at = datetime.now() + timedelta(days=2)

    reminder = notifications.schedule_deadline_reminder(
        user_id=1,
        resource_type="project",
        resource_id=9,
        title="Final proof",
        due_at=due_at,
        remind_before=timedelta(days=1),
    )

    assert reminder.status == "scheduled"
    assert notifications.get_due_notifications(now=datetime.now()) == []

    due = notifications.get_due_notifications(now=due_at)
    assert [item.id for item in due] == [reminder.id]

    assert notifications.mark_sent(reminder.id, sent_at=due_at) is True
    assert notifications.get_notification(reminder.id).status == "sent"


def test_project_assignment_creates_notification_and_reminder(managers):
    """Assigning a user to a project should create an inbox item and deadline reminder."""
    _conn, _audit, notifications, org, workspace, _workflow = managers
    organization = org.create_organization("Publishing Team", 1)
    team = workspace.create_workspace(organization.id, "Editorial", created_by=1)
    project = workspace.create_project(
        team.id,
        "Translation Release",
        owner_id=1,
        due_at=datetime.now() + timedelta(days=5),
    )

    assignment = workspace.assign_project_member(project.id, 2, role="reviewer", performed_by=1)

    assert assignment is not None
    inbox = notifications.get_user_notifications(2)
    assert [item.notification_type for item in inbox] == [
        "deadline_reminder",
        "project_assignment",
    ]
    assert inbox[1].message == "You were assigned to 'Translation Release' as reviewer."


def test_workflow_stage_creates_high_priority_notification(managers):
    """Workflow start and stage advancement should create review notifications."""
    _conn, _audit, notifications, org, _workspace, workflow = managers
    organization = org.create_organization("Publishing Team", 1)
    definition = workflow.create_workflow(
        organization.id,
        "Review",
        created_by=1,
        stages=[
            {"name": "Draft"},
            {"name": "Scholar Review"},
            {"name": "Approved", "is_terminal": True},
        ],
    )

    run = workflow.start_run(definition.id, "project", 12, started_by=1)
    workflow.advance_run(run.id, transitioned_by=2)

    user_one = notifications.get_user_notifications(1)
    user_two = notifications.get_user_notifications(2)

    assert user_one[0].notification_type == "workflow_stage"
    assert user_one[0].priority == "high"
    assert user_two[0].message == f"Workflow run {run.id} is waiting at 'Scholar Review'."
