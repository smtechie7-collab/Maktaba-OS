"""
Approval workflow automation for Maktaba-OS publishing teams.

This module provides configurable workflow stages for project approvals. It is
small on purpose: the core rules are stored in SQLite, stage transitions are
validated, and every transition is written to the compliance audit log.
"""

import sqlite3
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional

from infrastructure.auth.audit import ComplianceAuditManager
from infrastructure.auth.notifications import NotificationManager


@dataclass
class Workflow:
    """Approval workflow definition."""
    id: int
    organization_id: int
    name: str
    description: Optional[str]
    created_by: int
    created_at: datetime
    is_active: bool


@dataclass
class WorkflowStage:
    """Single ordered stage in a workflow."""
    id: int
    workflow_id: int
    name: str
    sequence: int
    required_role: Optional[str]
    is_terminal: bool


@dataclass
class WorkflowRun:
    """Workflow instance attached to a resource."""
    id: int
    workflow_id: int
    resource_type: str
    resource_id: int
    current_stage_id: int
    status: str
    started_by: int
    started_at: datetime
    completed_at: Optional[datetime]


@dataclass
class WorkflowTransition:
    """Transition history for a workflow run."""
    id: int
    run_id: int
    from_stage_id: Optional[int]
    to_stage_id: int
    transitioned_by: int
    decision: str
    note: Optional[str]
    transitioned_at: datetime


class WorkflowManager:
    """Manages approval workflow definitions and runs."""

    def __init__(
        self,
        db_connection: sqlite3.Connection,
        audit_manager: Optional[ComplianceAuditManager] = None,
        notification_manager: Optional[NotificationManager] = None
    ):
        self.db = db_connection
        self.audit = audit_manager or ComplianceAuditManager(db_connection)
        self.notifications = notification_manager or NotificationManager(db_connection, self.audit)
        self._ensure_schema()

    def _ensure_schema(self):
        """Ensure workflow schema exists."""
        with self.db:
            self.db.execute("""
                CREATE TABLE IF NOT EXISTS Workflows (
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
                CREATE TABLE IF NOT EXISTS WorkflowStages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    workflow_id INTEGER NOT NULL,
                    name TEXT NOT NULL,
                    sequence INTEGER NOT NULL,
                    required_role TEXT,
                    is_terminal INTEGER DEFAULT 0,
                    FOREIGN KEY (workflow_id) REFERENCES Workflows(id) ON DELETE CASCADE,
                    UNIQUE(workflow_id, sequence),
                    UNIQUE(workflow_id, name)
                )
            """)

            self.db.execute("""
                CREATE TABLE IF NOT EXISTS WorkflowRuns (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    workflow_id INTEGER NOT NULL,
                    resource_type TEXT NOT NULL,
                    resource_id INTEGER NOT NULL,
                    current_stage_id INTEGER NOT NULL,
                    status TEXT NOT NULL DEFAULT 'active',
                    started_by INTEGER NOT NULL,
                    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    completed_at TIMESTAMP,
                    FOREIGN KEY (workflow_id) REFERENCES Workflows(id) ON DELETE CASCADE,
                    FOREIGN KEY (current_stage_id) REFERENCES WorkflowStages(id),
                    FOREIGN KEY (started_by) REFERENCES Users(id)
                )
            """)

            self.db.execute("""
                CREATE TABLE IF NOT EXISTS WorkflowTransitions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id INTEGER NOT NULL,
                    from_stage_id INTEGER,
                    to_stage_id INTEGER NOT NULL,
                    transitioned_by INTEGER NOT NULL,
                    decision TEXT NOT NULL,
                    note TEXT,
                    transitioned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (run_id) REFERENCES WorkflowRuns(id) ON DELETE CASCADE,
                    FOREIGN KEY (from_stage_id) REFERENCES WorkflowStages(id),
                    FOREIGN KEY (to_stage_id) REFERENCES WorkflowStages(id),
                    FOREIGN KEY (transitioned_by) REFERENCES Users(id)
                )
            """)

    def create_workflow(
        self,
        organization_id: int,
        name: str,
        created_by: int,
        stages: List[dict],
        description: Optional[str] = None
    ) -> Workflow:
        """Create a workflow with ordered stages."""
        if not stages:
            raise ValueError("Workflow must include at least one stage")

        with self.db:
            cursor = self.db.execute("""
                INSERT INTO Workflows (organization_id, name, description, created_by)
                VALUES (?, ?, ?, ?)
            """, (organization_id, name, description, created_by))
            workflow_id = cursor.lastrowid

            for index, stage in enumerate(stages, start=1):
                self.db.execute("""
                    INSERT INTO WorkflowStages
                    (workflow_id, name, sequence, required_role, is_terminal)
                    VALUES (?, ?, ?, ?, ?)
                """, (
                    workflow_id,
                    stage["name"],
                    stage.get("sequence", index),
                    stage.get("required_role"),
                    1 if stage.get("is_terminal", index == len(stages)) else 0,
                ))

            self.audit.record_event(
                action="workflow.create",
                resource_type="workflow",
                resource_id=workflow_id,
                user_id=created_by,
                details=f"Created workflow '{name}' with {len(stages)} stages",
            )

        return self.get_workflow(workflow_id)

    def get_workflow(self, workflow_id: int) -> Optional[Workflow]:
        """Get a workflow definition."""
        row = self.db.execute("""
            SELECT id, organization_id, name, description, created_by, created_at, is_active
            FROM Workflows
            WHERE id = ?
        """, (workflow_id,)).fetchone()

        if not row:
            return None

        return Workflow(
            id=row[0],
            organization_id=row[1],
            name=row[2],
            description=row[3],
            created_by=row[4],
            created_at=datetime.fromisoformat(row[5]),
            is_active=bool(row[6]),
        )

    def get_stages(self, workflow_id: int) -> List[WorkflowStage]:
        """Get ordered workflow stages."""
        cursor = self.db.execute("""
            SELECT id, workflow_id, name, sequence, required_role, is_terminal
            FROM WorkflowStages
            WHERE workflow_id = ?
            ORDER BY sequence ASC
        """, (workflow_id,))

        return [
            WorkflowStage(
                id=row[0],
                workflow_id=row[1],
                name=row[2],
                sequence=row[3],
                required_role=row[4],
                is_terminal=bool(row[5]),
            )
            for row in cursor.fetchall()
        ]

    def start_run(
        self,
        workflow_id: int,
        resource_type: str,
        resource_id: int,
        started_by: int
    ) -> WorkflowRun:
        """Start a workflow run at its first stage."""
        stages = self.get_stages(workflow_id)
        if not stages:
            raise ValueError("Workflow has no stages")

        first_stage = stages[0]
        with self.db:
            cursor = self.db.execute("""
                INSERT INTO WorkflowRuns
                (workflow_id, resource_type, resource_id, current_stage_id, started_by)
                VALUES (?, ?, ?, ?, ?)
            """, (workflow_id, resource_type, resource_id, first_stage.id, started_by))
            run_id = cursor.lastrowid

            self.db.execute("""
                INSERT INTO WorkflowTransitions
                (run_id, from_stage_id, to_stage_id, transitioned_by, decision, note)
                VALUES (?, NULL, ?, ?, ?, ?)
            """, (run_id, first_stage.id, started_by, "start", None))

            self.audit.record_event(
                action="workflow.run.start",
                resource_type=resource_type,
                resource_id=resource_id,
                user_id=started_by,
                details=f"Started workflow {workflow_id} at stage '{first_stage.name}'",
            )
            self.notifications.notify_workflow_stage(
                run_id=run_id,
                user_id=started_by,
                stage_name=first_stage.name,
                resource_type=resource_type,
                resource_id=resource_id,
            )

        return self.get_run(run_id)

    def advance_run(
        self,
        run_id: int,
        transitioned_by: int,
        decision: str = "approve",
        note: Optional[str] = None
    ) -> WorkflowRun:
        """Advance a run to the next stage, or complete if already terminal."""
        run = self.get_run(run_id)
        if not run:
            raise ValueError(f"Workflow run not found: {run_id}")
        if run.status != "active":
            raise ValueError("Only active workflow runs can advance")

        stages = self.get_stages(run.workflow_id)
        current_index = next(
            (index for index, stage in enumerate(stages) if stage.id == run.current_stage_id),
            None
        )
        if current_index is None:
            raise ValueError("Current workflow stage is invalid")

        current_stage = stages[current_index]
        next_stage = stages[current_index + 1] if current_index + 1 < len(stages) else current_stage
        completed = current_stage.is_terminal or next_stage.id == current_stage.id
        new_status = "completed" if completed else "active"

        with self.db:
            self.db.execute("""
                UPDATE WorkflowRuns
                SET current_stage_id = ?, status = ?, completed_at = CASE WHEN ? = 1 THEN CURRENT_TIMESTAMP ELSE completed_at END
                WHERE id = ?
            """, (next_stage.id, new_status, 1 if completed else 0, run_id))

            self.db.execute("""
                INSERT INTO WorkflowTransitions
                (run_id, from_stage_id, to_stage_id, transitioned_by, decision, note)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (run_id, current_stage.id, next_stage.id, transitioned_by, decision, note))

            self.audit.record_event(
                action="workflow.run.advance",
                resource_type=run.resource_type,
                resource_id=run.resource_id,
                user_id=transitioned_by,
                details=f"Workflow run {run_id}: {current_stage.name} -> {next_stage.name} ({decision})",
            )
            if not completed:
                self.notifications.notify_workflow_stage(
                    run_id=run_id,
                    user_id=transitioned_by,
                    stage_name=next_stage.name,
                    resource_type=run.resource_type,
                    resource_id=run.resource_id,
                )

        return self.get_run(run_id)

    def reject_run(
        self,
        run_id: int,
        transitioned_by: int,
        note: Optional[str] = None
    ) -> WorkflowRun:
        """Reject and close a workflow run."""
        run = self.get_run(run_id)
        if not run:
            raise ValueError(f"Workflow run not found: {run_id}")

        with self.db:
            self.db.execute("""
                UPDATE WorkflowRuns
                SET status = 'rejected', completed_at = CURRENT_TIMESTAMP
                WHERE id = ? AND status = 'active'
            """, (run_id,))

            self.db.execute("""
                INSERT INTO WorkflowTransitions
                (run_id, from_stage_id, to_stage_id, transitioned_by, decision, note)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (run_id, run.current_stage_id, run.current_stage_id, transitioned_by, "reject", note))

            self.audit.record_event(
                action="workflow.run.reject",
                resource_type=run.resource_type,
                resource_id=run.resource_id,
                user_id=transitioned_by,
                details=f"Rejected workflow run {run_id}: {note or ''}".strip(),
                severity="warning",
            )

        return self.get_run(run_id)

    def get_run(self, run_id: int) -> Optional[WorkflowRun]:
        """Get a workflow run."""
        row = self.db.execute("""
            SELECT id, workflow_id, resource_type, resource_id, current_stage_id,
                   status, started_by, started_at, completed_at
            FROM WorkflowRuns
            WHERE id = ?
        """, (run_id,)).fetchone()

        if not row:
            return None

        return WorkflowRun(
            id=row[0],
            workflow_id=row[1],
            resource_type=row[2],
            resource_id=row[3],
            current_stage_id=row[4],
            status=row[5],
            started_by=row[6],
            started_at=datetime.fromisoformat(row[7]),
            completed_at=datetime.fromisoformat(row[8]) if row[8] else None,
        )

    def get_transitions(self, run_id: int) -> List[WorkflowTransition]:
        """Get transition history for a run."""
        cursor = self.db.execute("""
            SELECT id, run_id, from_stage_id, to_stage_id, transitioned_by,
                   decision, note, transitioned_at
            FROM WorkflowTransitions
            WHERE run_id = ?
            ORDER BY transitioned_at ASC, id ASC
        """, (run_id,))

        return [
            WorkflowTransition(
                id=row[0],
                run_id=row[1],
                from_stage_id=row[2],
                to_stage_id=row[3],
                transitioned_by=row[4],
                decision=row[5],
                note=row[6],
                transitioned_at=datetime.fromisoformat(row[7]),
            )
            for row in cursor.fetchall()
        ]
