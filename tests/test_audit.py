"""
Tests for compliance audit logging.
"""

import sqlite3

from infrastructure.auth.audit import ComplianceAuditManager


def test_record_and_query_audit_event():
    """Audit events should be persisted and queryable by resource."""
    conn = sqlite3.connect(":memory:")
    conn.execute("""
        CREATE TABLE Users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            password_hash TEXT NOT NULL
        )
    """)
    conn.execute("INSERT INTO Users (username, password_hash) VALUES (?, ?)", ("owner", "hash"))
    conn.commit()

    audit = ComplianceAuditManager(conn)
    event = audit.record_event(
        action="workspace.create",
        resource_type="workspace",
        resource_id=7,
        user_id=1,
        details="Created workspace",
        severity="info",
        correlation_id="req-1",
    )

    assert event.id == 1
    assert event.correlation_id == "req-1"

    events = audit.get_resource_timeline("workspace", 7)
    assert len(events) == 1
    assert events[0].action == "workspace.create"
    assert events[0].user_id == 1


def test_existing_audit_log_schema_is_upgraded():
    """Older AuditLog tables should receive compliance columns."""
    conn = sqlite3.connect(":memory:")
    conn.execute("""
        CREATE TABLE AuditLog (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            action TEXT NOT NULL,
            resource_type TEXT NOT NULL,
            resource_id INTEGER,
            details TEXT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()

    audit = ComplianceAuditManager(conn)
    event = audit.record_event(
        action="project.status.update",
        resource_type="project",
        resource_id=3,
        severity="warning",
    )

    assert event.severity == "warning"
    columns = {row[1] for row in conn.execute("PRAGMA table_info(AuditLog)").fetchall()}
    assert {"severity", "correlation_id", "ip_address", "user_agent"}.issubset(columns)
