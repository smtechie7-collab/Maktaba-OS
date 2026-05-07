"""
Tests for approval workflow automation.
"""

import sqlite3

import pytest

from infrastructure.auth.audit import ComplianceAuditManager
from infrastructure.auth.organization import OrganizationManager
from infrastructure.auth.workflow import WorkflowManager


@pytest.fixture
def managers():
    """Create workflow test managers."""
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
    org = OrganizationManager(conn)
    workflow = WorkflowManager(conn, audit)
    return conn, audit, org, workflow


def test_create_workflow_with_ordered_stages(managers):
    """Workflow definitions should persist ordered approval stages."""
    _conn, audit, org, workflow = managers
    organization = org.create_organization("Publishing Team", 1)

    created = workflow.create_workflow(
        organization_id=organization.id,
        name="Editorial Approval",
        created_by=1,
        stages=[
            {"name": "Draft", "required_role": "editor"},
            {"name": "Scholar Review", "required_role": "reviewer"},
            {"name": "Approved", "is_terminal": True},
        ],
    )

    stages = workflow.get_stages(created.id)
    events = audit.get_resource_timeline("workflow", created.id)

    assert [stage.name for stage in stages] == ["Draft", "Scholar Review", "Approved"]
    assert stages[-1].is_terminal is True
    assert events[0].action == "workflow.create"


def test_workflow_run_advances_and_completes(managers):
    """A workflow run should move through stages and complete at terminal stage."""
    _conn, audit, org, workflow = managers
    organization = org.create_organization("Publishing Team", 1)
    created = workflow.create_workflow(
        organization.id,
        "Release Approval",
        created_by=1,
        stages=[
            {"name": "Draft"},
            {"name": "Review"},
            {"name": "Approved", "is_terminal": True},
        ],
    )

    run = workflow.start_run(created.id, "project", 42, started_by=1)
    assert run.status == "active"

    run = workflow.advance_run(run.id, transitioned_by=2, note="Ready for final review")
    assert run.status == "active"
    assert workflow.get_stages(created.id)[1].id == run.current_stage_id

    run = workflow.advance_run(run.id, transitioned_by=3, decision="approve")
    assert run.status == "active"
    assert workflow.get_stages(created.id)[2].id == run.current_stage_id

    run = workflow.advance_run(run.id, transitioned_by=1, decision="publish")
    assert run.status == "completed"
    assert run.completed_at is not None

    transitions = workflow.get_transitions(run.id)
    assert [transition.decision for transition in transitions] == [
        "start",
        "approve",
        "approve",
        "publish",
    ]

    events = audit.get_resource_timeline("project", 42)
    workflow_actions = [
        event.action for event in events
        if event.action != "notification.create"
    ]
    assert workflow_actions == [
        "workflow.run.advance",
        "workflow.run.advance",
        "workflow.run.advance",
        "workflow.run.start",
    ]


def test_reject_workflow_run_records_warning(managers):
    """Rejected workflow runs should close and emit warning audit events."""
    _conn, audit, org, workflow = managers
    organization = org.create_organization("Publishing Team", 1)
    created = workflow.create_workflow(
        organization.id,
        "Review",
        created_by=1,
        stages=[
            {"name": "Draft"},
            {"name": "Approved", "is_terminal": True},
        ],
    )
    run = workflow.start_run(created.id, "project", 9, started_by=1)

    rejected = workflow.reject_run(run.id, transitioned_by=2, note="Missing citations")

    assert rejected.status == "rejected"
    assert rejected.completed_at is not None
    warning_events = audit.query_events(severity="warning")
    assert warning_events[0].action == "workflow.run.reject"
    assert "Missing citations" in warning_events[0].details
