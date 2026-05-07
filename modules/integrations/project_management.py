"""
Project-management integrations for Jira and Asana.

The core app should not block on live external APIs. This module stores
connection metadata, maps local projects to external records, and writes
outbound sync requests into a durable outbox that an API worker can deliver.
"""

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional

from infrastructure.auth.audit import ComplianceAuditManager
from infrastructure.auth.workspace import Project


SUPPORTED_PROVIDERS = {"jira", "asana"}


@dataclass
class IntegrationConnection:
    """Configured external project-management connection."""
    id: int
    organization_id: int
    provider: str
    name: str
    base_url: Optional[str]
    external_workspace_id: Optional[str]
    created_by: int
    created_at: datetime
    is_active: bool


@dataclass
class ProjectLink:
    """Mapping between a local project and an external issue/task."""
    id: int
    connection_id: int
    project_id: int
    external_id: str
    external_url: Optional[str]
    last_synced_at: Optional[datetime]
    sync_status: str


@dataclass
class IntegrationOutboxItem:
    """Durable outbound sync request."""
    id: int
    connection_id: int
    provider: str
    action: str
    resource_type: str
    resource_id: int
    payload: Dict[str, Any]
    status: str
    attempts: int
    last_error: Optional[str]
    created_at: datetime
    processed_at: Optional[datetime]


class ProjectManagementIntegrationManager:
    """Manages Jira/Asana connection metadata and outbound sync jobs."""

    def __init__(
        self,
        db_connection: sqlite3.Connection,
        audit_manager: Optional[ComplianceAuditManager] = None,
    ):
        self.db = db_connection
        self.audit = audit_manager or ComplianceAuditManager(db_connection)
        self._ensure_schema()

    def _ensure_schema(self):
        """Ensure project-management integration schema exists."""
        with self.db:
            self.db.execute("""
                CREATE TABLE IF NOT EXISTS IntegrationConnections (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    organization_id INTEGER NOT NULL,
                    provider TEXT NOT NULL,
                    name TEXT NOT NULL,
                    base_url TEXT,
                    external_workspace_id TEXT,
                    created_by INTEGER NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    is_active INTEGER DEFAULT 1,
                    FOREIGN KEY (created_by) REFERENCES Users(id),
                    UNIQUE(organization_id, provider, name)
                )
            """)

            self.db.execute("""
                CREATE TABLE IF NOT EXISTS ProjectIntegrationLinks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    connection_id INTEGER NOT NULL,
                    project_id INTEGER NOT NULL,
                    external_id TEXT NOT NULL,
                    external_url TEXT,
                    last_synced_at TIMESTAMP,
                    sync_status TEXT NOT NULL DEFAULT 'linked',
                    FOREIGN KEY (connection_id) REFERENCES IntegrationConnections(id) ON DELETE CASCADE,
                    UNIQUE(connection_id, project_id),
                    UNIQUE(connection_id, external_id)
                )
            """)

            self.db.execute("""
                CREATE TABLE IF NOT EXISTS IntegrationOutbox (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    connection_id INTEGER NOT NULL,
                    provider TEXT NOT NULL,
                    action TEXT NOT NULL,
                    resource_type TEXT NOT NULL,
                    resource_id INTEGER NOT NULL,
                    payload_json TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'pending',
                    attempts INTEGER NOT NULL DEFAULT 0,
                    last_error TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    processed_at TIMESTAMP,
                    FOREIGN KEY (connection_id) REFERENCES IntegrationConnections(id) ON DELETE CASCADE
                )
            """)

    def create_connection(
        self,
        organization_id: int,
        provider: str,
        name: str,
        created_by: int,
        base_url: Optional[str] = None,
        external_workspace_id: Optional[str] = None,
    ) -> IntegrationConnection:
        """Create a Jira or Asana integration connection."""
        self._validate_provider(provider)
        with self.db:
            cursor = self.db.execute("""
                INSERT INTO IntegrationConnections
                (organization_id, provider, name, base_url, external_workspace_id, created_by)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (organization_id, provider, name, base_url, external_workspace_id, created_by))
            connection_id = cursor.lastrowid

            self.audit.record_event(
                action="integration.connection.create",
                resource_type="integration_connection",
                resource_id=connection_id,
                user_id=created_by,
                details=f"Created {provider} integration '{name}'",
            )

        return self.get_connection(connection_id)

    def get_connection(self, connection_id: int) -> Optional[IntegrationConnection]:
        """Get an integration connection."""
        row = self.db.execute("""
            SELECT id, organization_id, provider, name, base_url, external_workspace_id,
                   created_by, created_at, is_active
            FROM IntegrationConnections
            WHERE id = ?
        """, (connection_id,)).fetchone()

        return self._row_to_connection(row) if row else None

    def list_connections(self, organization_id: int, provider: Optional[str] = None) -> List[IntegrationConnection]:
        """List active connections for an organization."""
        params = [organization_id]
        provider_filter = ""
        if provider:
            self._validate_provider(provider)
            provider_filter = " AND provider = ?"
            params.append(provider)

        cursor = self.db.execute(f"""
            SELECT id, organization_id, provider, name, base_url, external_workspace_id,
                   created_by, created_at, is_active
            FROM IntegrationConnections
            WHERE organization_id = ? AND is_active = 1{provider_filter}
            ORDER BY created_at DESC, id DESC
        """, params)

        return [self._row_to_connection(row) for row in cursor.fetchall()]

    def link_project(
        self,
        connection_id: int,
        project_id: int,
        external_id: str,
        external_url: Optional[str] = None,
    ) -> ProjectLink:
        """Link a local project to an existing external issue/task."""
        connection = self._require_connection(connection_id)
        with self.db:
            cursor = self.db.execute("""
                INSERT INTO ProjectIntegrationLinks
                (connection_id, project_id, external_id, external_url)
                VALUES (?, ?, ?, ?)
            """, (connection_id, project_id, external_id, external_url))
            link_id = cursor.lastrowid

            self.audit.record_event(
                action="integration.project.link",
                resource_type="project",
                resource_id=project_id,
                user_id=connection.created_by,
                details=f"Linked project {project_id} to {connection.provider} item {external_id}",
            )

        return self.get_project_link(link_id)

    def get_project_link(self, link_id: int) -> Optional[ProjectLink]:
        """Get a project integration link by ID."""
        row = self.db.execute("""
            SELECT id, connection_id, project_id, external_id, external_url, last_synced_at, sync_status
            FROM ProjectIntegrationLinks
            WHERE id = ?
        """, (link_id,)).fetchone()

        return self._row_to_link(row) if row else None

    def get_project_links(self, project_id: int) -> List[ProjectLink]:
        """Get all external links for a local project."""
        cursor = self.db.execute("""
            SELECT id, connection_id, project_id, external_id, external_url, last_synced_at, sync_status
            FROM ProjectIntegrationLinks
            WHERE project_id = ?
            ORDER BY id ASC
        """, (project_id,))

        return [self._row_to_link(row) for row in cursor.fetchall()]

    def enqueue_project_create(
        self,
        connection_id: int,
        project: Project,
        description: Optional[str] = None,
    ) -> IntegrationOutboxItem:
        """Queue creation of an external issue/task for a project."""
        connection = self._require_connection(connection_id)
        payload = self.build_project_payload(connection.provider, project, description=description)
        return self._enqueue(
            connection=connection,
            action="create_project_item",
            resource_type="project",
            resource_id=project.id,
            payload=payload,
        )

    def enqueue_project_update(
        self,
        connection_id: int,
        project: Project,
        external_id: str,
        description: Optional[str] = None,
    ) -> IntegrationOutboxItem:
        """Queue update of an external issue/task for a project."""
        connection = self._require_connection(connection_id)
        payload = self.build_project_payload(connection.provider, project, description=description)
        payload["external_id"] = external_id
        return self._enqueue(
            connection=connection,
            action="update_project_item",
            resource_type="project",
            resource_id=project.id,
            payload=payload,
        )

    def build_project_payload(
        self,
        provider: str,
        project: Project,
        description: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Build a provider-specific project payload."""
        self._validate_provider(provider)
        if provider == "jira":
            return {
                "fields": {
                    "summary": project.name,
                    "description": description or project.description or "",
                    "duedate": project.due_at.date().isoformat() if project.due_at else None,
                    "labels": ["maktaba-os", f"status-{project.status}"],
                }
            }

        return {
            "data": {
                "name": project.name,
                "notes": description or project.description or "",
                "due_on": project.due_at.date().isoformat() if project.due_at else None,
                "completed": project.status in {"published", "completed", "approved"},
            }
        }

    def get_pending_outbox(self, provider: Optional[str] = None, limit: int = 100) -> List[IntegrationOutboxItem]:
        """Return pending outbound sync jobs."""
        params = []
        provider_filter = ""
        if provider:
            self._validate_provider(provider)
            provider_filter = " AND provider = ?"
            params.append(provider)

        params.append(limit)
        cursor = self.db.execute(f"""
            SELECT id, connection_id, provider, action, resource_type, resource_id, payload_json,
                   status, attempts, last_error, created_at, processed_at
            FROM IntegrationOutbox
            WHERE status = 'pending'{provider_filter}
            ORDER BY created_at ASC, id ASC
            LIMIT ?
        """, params)

        return [self._row_to_outbox_item(row) for row in cursor.fetchall()]

    def mark_outbox_processed(self, outbox_id: int, external_id: Optional[str] = None) -> bool:
        """Mark an outbox item as processed and update linked sync state if present."""
        item = self.get_outbox_item(outbox_id)
        if not item:
            return False

        now = datetime.now()
        with self.db:
            cursor = self.db.execute("""
                UPDATE IntegrationOutbox
                SET status = 'processed', processed_at = ?
                WHERE id = ?
            """, (now, outbox_id))
            if cursor.rowcount == 0:
                return False

            if external_id:
                self.db.execute("""
                    UPDATE ProjectIntegrationLinks
                    SET last_synced_at = ?, sync_status = 'synced'
                    WHERE connection_id = ? AND project_id = ? AND external_id = ?
                """, (now, item.connection_id, item.resource_id, external_id))

        return True

    def mark_outbox_failed(self, outbox_id: int, error: str) -> bool:
        """Record a failed delivery attempt."""
        item = self.get_outbox_item(outbox_id)
        if not item:
            return False

        with self.db:
            cursor = self.db.execute("""
                UPDATE IntegrationOutbox
                SET attempts = attempts + 1, last_error = ?
                WHERE id = ?
            """, (error, outbox_id))
            if cursor.rowcount == 0:
                return False

            self.audit.record_event(
                action="integration.outbox.fail",
                resource_type=item.resource_type,
                resource_id=item.resource_id,
                details=f"Integration outbox {outbox_id} failed: {error}",
                severity="warning",
            )

        return True

    def get_outbox_item(self, outbox_id: int) -> Optional[IntegrationOutboxItem]:
        """Get a single outbound sync job."""
        row = self.db.execute("""
            SELECT id, connection_id, provider, action, resource_type, resource_id, payload_json,
                   status, attempts, last_error, created_at, processed_at
            FROM IntegrationOutbox
            WHERE id = ?
        """, (outbox_id,)).fetchone()

        return self._row_to_outbox_item(row) if row else None

    def _enqueue(
        self,
        connection: IntegrationConnection,
        action: str,
        resource_type: str,
        resource_id: int,
        payload: Dict[str, Any],
    ) -> IntegrationOutboxItem:
        """Persist an outbound sync job."""
        with self.db:
            cursor = self.db.execute("""
                INSERT INTO IntegrationOutbox
                (connection_id, provider, action, resource_type, resource_id, payload_json)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                connection.id,
                connection.provider,
                action,
                resource_type,
                resource_id,
                json.dumps(payload, ensure_ascii=False),
            ))
            outbox_id = cursor.lastrowid

            self.audit.record_event(
                action="integration.outbox.enqueue",
                resource_type=resource_type,
                resource_id=resource_id,
                user_id=connection.created_by,
                details=f"Queued {connection.provider} {action}",
            )

        return self.get_outbox_item(outbox_id)

    def _require_connection(self, connection_id: int) -> IntegrationConnection:
        """Return active connection or raise."""
        connection = self.get_connection(connection_id)
        if not connection or not connection.is_active:
            raise ValueError(f"Active integration connection not found: {connection_id}")
        return connection

    def _validate_provider(self, provider: str):
        """Validate supported provider."""
        if provider not in SUPPORTED_PROVIDERS:
            raise ValueError(f"Unsupported project management provider: {provider}")

    def _row_to_connection(self, row) -> IntegrationConnection:
        """Convert SQLite row to connection."""
        return IntegrationConnection(
            id=row[0],
            organization_id=row[1],
            provider=row[2],
            name=row[3],
            base_url=row[4],
            external_workspace_id=row[5],
            created_by=row[6],
            created_at=datetime.fromisoformat(row[7]),
            is_active=bool(row[8]),
        )

    def _row_to_link(self, row) -> ProjectLink:
        """Convert SQLite row to project link."""
        return ProjectLink(
            id=row[0],
            connection_id=row[1],
            project_id=row[2],
            external_id=row[3],
            external_url=row[4],
            last_synced_at=datetime.fromisoformat(row[5]) if row[5] else None,
            sync_status=row[6],
        )

    def _row_to_outbox_item(self, row) -> IntegrationOutboxItem:
        """Convert SQLite row to outbox item."""
        return IntegrationOutboxItem(
            id=row[0],
            connection_id=row[1],
            provider=row[2],
            action=row[3],
            resource_type=row[4],
            resource_id=row[5],
            payload=json.loads(row[6]),
            status=row[7],
            attempts=row[8],
            last_error=row[9],
            created_at=datetime.fromisoformat(row[10]),
            processed_at=datetime.fromisoformat(row[11]) if row[11] else None,
        )
