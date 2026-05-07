"""
Compliance audit logging for Maktaba-OS enterprise features.

The audit log is intentionally boring and durable: every security or
collaboration action becomes a queryable database row that can be used for
access reports, compliance exports, and incident review.
"""

import sqlite3
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional


@dataclass
class ComplianceAuditEvent:
    """A persisted compliance audit event."""
    id: int
    user_id: Optional[int]
    action: str
    resource_type: str
    resource_id: Optional[int]
    details: Optional[str]
    ip_address: Optional[str]
    user_agent: Optional[str]
    severity: str
    correlation_id: Optional[str]
    timestamp: datetime


class ComplianceAuditManager:
    """Writes and queries compliance audit events."""

    def __init__(self, db_connection: sqlite3.Connection):
        self.db = db_connection
        self._ensure_schema()

    def _ensure_schema(self):
        """Ensure the audit table and newer columns exist."""
        with self.db:
            self.db.execute("""
                CREATE TABLE IF NOT EXISTS AuditLog (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    action TEXT NOT NULL,
                    resource_type TEXT NOT NULL,
                    resource_id INTEGER,
                    details TEXT,
                    ip_address TEXT,
                    user_agent TEXT,
                    severity TEXT NOT NULL DEFAULT 'info',
                    correlation_id TEXT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES Users(id)
                )
            """)

            existing = {
                row[1]
                for row in self.db.execute("PRAGMA table_info(AuditLog)").fetchall()
            }
            columns = {
                "severity": "TEXT NOT NULL DEFAULT 'info'",
                "correlation_id": "TEXT",
                "ip_address": "TEXT",
                "user_agent": "TEXT",
            }
            for name, definition in columns.items():
                if name not in existing:
                    self.db.execute(f"ALTER TABLE AuditLog ADD COLUMN {name} {definition}")

    def record_event(
        self,
        action: str,
        resource_type: str,
        resource_id: Optional[int] = None,
        user_id: Optional[int] = None,
        details: Optional[str] = None,
        severity: str = "info",
        correlation_id: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> ComplianceAuditEvent:
        """Persist a single audit event and return it."""
        with self.db:
            cursor = self.db.execute("""
                INSERT INTO AuditLog
                (user_id, action, resource_type, resource_id, details, ip_address, user_agent, severity, correlation_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                user_id,
                action,
                resource_type,
                resource_id,
                details,
                ip_address,
                user_agent,
                severity,
                correlation_id,
            ))

        return self.get_event(cursor.lastrowid)

    def get_event(self, event_id: int) -> Optional[ComplianceAuditEvent]:
        """Get one audit event by ID."""
        row = self.db.execute("""
            SELECT id, user_id, action, resource_type, resource_id, details,
                   ip_address, user_agent, severity, correlation_id, timestamp
            FROM AuditLog
            WHERE id = ?
        """, (event_id,)).fetchone()

        return self._row_to_event(row) if row else None

    def query_events(
        self,
        user_id: Optional[int] = None,
        resource_type: Optional[str] = None,
        resource_id: Optional[int] = None,
        action: Optional[str] = None,
        severity: Optional[str] = None,
        limit: int = 100,
    ) -> List[ComplianceAuditEvent]:
        """Query audit events with optional filters."""
        query = """
            SELECT id, user_id, action, resource_type, resource_id, details,
                   ip_address, user_agent, severity, correlation_id, timestamp
            FROM AuditLog
        """
        filters = []
        params = []

        if user_id is not None:
            filters.append("user_id = ?")
            params.append(user_id)
        if resource_type is not None:
            filters.append("resource_type = ?")
            params.append(resource_type)
        if resource_id is not None:
            filters.append("resource_id = ?")
            params.append(resource_id)
        if action is not None:
            filters.append("action = ?")
            params.append(action)
        if severity is not None:
            filters.append("severity = ?")
            params.append(severity)

        if filters:
            query += " WHERE " + " AND ".join(filters)

        query += " ORDER BY timestamp DESC, id DESC LIMIT ?"
        params.append(limit)

        cursor = self.db.execute(query, params)
        return [self._row_to_event(row) for row in cursor.fetchall()]

    def get_resource_timeline(
        self,
        resource_type: str,
        resource_id: int,
        limit: int = 100,
    ) -> List[ComplianceAuditEvent]:
        """Return recent events for a specific resource."""
        return self.query_events(
            resource_type=resource_type,
            resource_id=resource_id,
            limit=limit,
        )

    def _row_to_event(self, row) -> ComplianceAuditEvent:
        """Convert a SQLite row or tuple to an audit event."""
        return ComplianceAuditEvent(
            id=row[0],
            user_id=row[1],
            action=row[2],
            resource_type=row[3],
            resource_id=row[4],
            details=row[5],
            ip_address=row[6],
            user_agent=row[7],
            severity=row[8],
            correlation_id=row[9],
            timestamp=datetime.fromisoformat(row[10]),
        )
