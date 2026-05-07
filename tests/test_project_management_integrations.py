"""
Tests for Jira/Asana project-management integration hooks.
"""

import sqlite3
from datetime import datetime, timedelta

import pytest

from infrastructure.auth.audit import ComplianceAuditManager
from infrastructure.auth.organization import OrganizationManager
from infrastructure.auth.workspace import WorkspaceManager
from modules.integrations import ProjectManagementIntegrationManager


@pytest.fixture
def managers():
    """Create integration test managers."""
    conn = sqlite3.connect(":memory:")
    conn.execute("""
        CREATE TABLE Users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            email TEXT UNIQUE,
            password_hash TEXT NOT NULL
        )
    """)
    conn.execute("INSERT INTO Users (username, email, password_hash) VALUES (?, ?, ?)", ("owner", "owner@example.com", "hash"))
    conn.commit()

    audit = ComplianceAuditManager(conn)
    org = OrganizationManager(conn)
    workspace = WorkspaceManager(conn, audit)
    integrations = ProjectManagementIntegrationManager(conn, audit)
    return conn, audit, org, workspace, integrations


def create_project(org, workspace):
    """Create a workspace project for integration tests."""
    organization = org.create_organization("Publishing Team", 1)
    team = workspace.create_workspace(organization.id, "Editorial", created_by=1)
    project = workspace.create_project(
        team.id,
        "Release Checklist",
        owner_id=1,
        description="Coordinate release work",
        due_at=datetime.now() + timedelta(days=10),
    )
    return organization, project


def test_create_and_list_connections(managers):
    """Connections should be stored per provider and organization."""
    _conn, audit, _org, _workspace, integrations = managers

    jira = integrations.create_connection(
        organization_id=1,
        provider="jira",
        name="Editorial Jira",
        created_by=1,
        base_url="https://example.atlassian.net",
    )
    integrations.create_connection(
        organization_id=1,
        provider="asana",
        name="Asana Workspace",
        created_by=1,
        external_workspace_id="workspace-1",
    )

    assert jira.provider == "jira"
    assert [conn.provider for conn in integrations.list_connections(1, provider="jira")] == ["jira"]
    assert len(integrations.list_connections(1)) == 2

    events = audit.get_resource_timeline("integration_connection", jira.id)
    assert events[0].action == "integration.connection.create"


def test_unsupported_provider_is_rejected(managers):
    """Only known project-management providers should be accepted."""
    _conn, _audit, _org, _workspace, integrations = managers

    with pytest.raises(ValueError, match="Unsupported"):
        integrations.create_connection(
            organization_id=1,
            provider="trello",
            name="Nope",
            created_by=1,
        )


def test_build_jira_and_asana_payloads(managers):
    """Payload builders should produce provider-specific shapes."""
    _conn, _audit, org, workspace, integrations = managers
    _organization, project = create_project(org, workspace)

    jira_payload = integrations.build_project_payload("jira", project)
    asana_payload = integrations.build_project_payload("asana", project)

    assert jira_payload["fields"]["summary"] == "Release Checklist"
    assert jira_payload["fields"]["duedate"] == project.due_at.date().isoformat()
    assert "status-planning" in jira_payload["fields"]["labels"]

    assert asana_payload["data"]["name"] == "Release Checklist"
    assert asana_payload["data"]["due_on"] == project.due_at.date().isoformat()
    assert asana_payload["data"]["completed"] is False


def test_link_project_and_enqueue_create(managers):
    """Local projects should link to external items and queue outbound creates."""
    _conn, audit, org, workspace, integrations = managers
    organization, project = create_project(org, workspace)
    connection = integrations.create_connection(
        organization.id,
        provider="jira",
        name="Jira",
        created_by=1,
    )

    link = integrations.link_project(
        connection.id,
        project.id,
        external_id="MAK-12",
        external_url="https://example.atlassian.net/browse/MAK-12",
    )
    outbox = integrations.enqueue_project_create(connection.id, project)

    assert link.external_id == "MAK-12"
    assert outbox.provider == "jira"
    assert outbox.action == "create_project_item"
    assert outbox.payload["fields"]["summary"] == project.name

    pending = integrations.get_pending_outbox(provider="jira")
    assert [item.id for item in pending] == [outbox.id]
    assert audit.query_events(resource_type="project")[0].action == "integration.outbox.enqueue"


def test_mark_outbox_processed_updates_link_sync_state(managers):
    """Processed outbox items should update linked project sync state when possible."""
    _conn, _audit, org, workspace, integrations = managers
    organization, project = create_project(org, workspace)
    connection = integrations.create_connection(organization.id, "asana", "Asana", created_by=1)
    link = integrations.link_project(connection.id, project.id, external_id="task-1")
    outbox = integrations.enqueue_project_update(connection.id, project, external_id="task-1")

    assert integrations.mark_outbox_processed(outbox.id, external_id="task-1") is True

    processed = integrations.get_outbox_item(outbox.id)
    synced_link = integrations.get_project_link(link.id)
    assert processed.status == "processed"
    assert processed.processed_at is not None
    assert synced_link.sync_status == "synced"
    assert synced_link.last_synced_at is not None


def test_mark_outbox_failed_records_attempt_and_warning(managers):
    """Failed outbox delivery should retain retry state and emit warning audit."""
    _conn, audit, org, workspace, integrations = managers
    organization, project = create_project(org, workspace)
    connection = integrations.create_connection(organization.id, "jira", "Jira", created_by=1)
    outbox = integrations.enqueue_project_create(connection.id, project)

    assert integrations.mark_outbox_failed(outbox.id, "HTTP 401") is True

    failed = integrations.get_outbox_item(outbox.id)
    warning_events = audit.query_events(severity="warning")

    assert failed.status == "pending"
    assert failed.attempts == 1
    assert failed.last_error == "HTTP 401"
    assert warning_events[0].action == "integration.outbox.fail"
