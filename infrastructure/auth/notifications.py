"""
Notification and reminder infrastructure for enterprise collaboration.

Notifications are stored in SQLite so desktop, web, or future sync services can
render the same inbox. Reminders use the same table with a scheduled delivery
time, which keeps the implementation simple and testable.
"""

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import List, Optional

from infrastructure.auth.audit import ComplianceAuditManager


@dataclass
class Notification:
    """User-facing notification or scheduled reminder."""
    id: int
    user_id: int
    notification_type: str
    title: str
    message: str
    resource_type: Optional[str]
    resource_id: Optional[int]
    priority: str
    status: str
    scheduled_for: Optional[datetime]
    sent_at: Optional[datetime]
    read_at: Optional[datetime]
    created_at: datetime


class NotificationManager:
    """Creates, queries, and updates notifications."""

    def __init__(
        self,
        db_connection: sqlite3.Connection,
        audit_manager: Optional[ComplianceAuditManager] = None
    ):
        self.db = db_connection
        self.audit = audit_manager or ComplianceAuditManager(db_connection)
        self._ensure_schema()

    def _ensure_schema(self):
        """Ensure notification schema exists."""
        with self.db:
            self.db.execute("""
                CREATE TABLE IF NOT EXISTS Notifications (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    notification_type TEXT NOT NULL,
                    title TEXT NOT NULL,
                    message TEXT NOT NULL,
                    resource_type TEXT,
                    resource_id INTEGER,
                    priority TEXT NOT NULL DEFAULT 'normal',
                    status TEXT NOT NULL DEFAULT 'pending',
                    scheduled_for TIMESTAMP,
                    sent_at TIMESTAMP,
                    read_at TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES Users(id) ON DELETE CASCADE
                )
            """)

    def create_notification(
        self,
        user_id: int,
        notification_type: str,
        title: str,
        message: str,
        resource_type: Optional[str] = None,
        resource_id: Optional[int] = None,
        priority: str = "normal",
        scheduled_for: Optional[datetime] = None,
    ) -> Notification:
        """Create a notification or scheduled reminder."""
        status = "scheduled" if scheduled_for else "pending"
        with self.db:
            cursor = self.db.execute("""
                INSERT INTO Notifications
                (user_id, notification_type, title, message, resource_type, resource_id, priority, status, scheduled_for)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                user_id,
                notification_type,
                title,
                message,
                resource_type,
                resource_id,
                priority,
                status,
                scheduled_for,
            ))
            notification_id = cursor.lastrowid

            self.audit.record_event(
                action="notification.create",
                resource_type=resource_type or "notification",
                resource_id=resource_id or notification_id,
                user_id=user_id,
                details=f"Created {notification_type} notification: {title}",
            )

        return self.get_notification(notification_id)

    def notify_project_assignment(
        self,
        project_id: int,
        user_id: int,
        project_name: str,
        role: str,
    ) -> Notification:
        """Create a project assignment notification."""
        return self.create_notification(
            user_id=user_id,
            notification_type="project_assignment",
            title="Project assignment",
            message=f"You were assigned to '{project_name}' as {role}.",
            resource_type="project",
            resource_id=project_id,
            priority="normal",
        )

    def notify_workflow_stage(
        self,
        run_id: int,
        user_id: int,
        stage_name: str,
        resource_type: str,
        resource_id: int,
    ) -> Notification:
        """Create a workflow stage notification."""
        return self.create_notification(
            user_id=user_id,
            notification_type="workflow_stage",
            title="Workflow review needed",
            message=f"Workflow run {run_id} is waiting at '{stage_name}'.",
            resource_type=resource_type,
            resource_id=resource_id,
            priority="high",
        )

    def schedule_deadline_reminder(
        self,
        user_id: int,
        resource_type: str,
        resource_id: int,
        title: str,
        due_at: datetime,
        remind_before: timedelta = timedelta(days=1),
    ) -> Notification:
        """Schedule a reminder before a deadline."""
        scheduled_for = due_at - remind_before
        return self.create_notification(
            user_id=user_id,
            notification_type="deadline_reminder",
            title="Deadline reminder",
            message=f"{title} is due at {due_at.isoformat()}.",
            resource_type=resource_type,
            resource_id=resource_id,
            priority="high",
            scheduled_for=scheduled_for,
        )

    def get_notification(self, notification_id: int) -> Optional[Notification]:
        """Get one notification by ID."""
        row = self.db.execute("""
            SELECT id, user_id, notification_type, title, message, resource_type,
                   resource_id, priority, status, scheduled_for, sent_at, read_at, created_at
            FROM Notifications
            WHERE id = ?
        """, (notification_id,)).fetchone()

        return self._row_to_notification(row) if row else None

    def get_user_notifications(
        self,
        user_id: int,
        include_read: bool = False,
        limit: int = 100,
    ) -> List[Notification]:
        """Get a user's inbox."""
        read_filter = "" if include_read else " AND read_at IS NULL"
        cursor = self.db.execute(f"""
            SELECT id, user_id, notification_type, title, message, resource_type,
                   resource_id, priority, status, scheduled_for, sent_at, read_at, created_at
            FROM Notifications
            WHERE user_id = ?{read_filter}
            ORDER BY created_at DESC, id DESC
            LIMIT ?
        """, (user_id, limit))

        return [self._row_to_notification(row) for row in cursor.fetchall()]

    def get_due_notifications(self, now: Optional[datetime] = None, limit: int = 100) -> List[Notification]:
        """Return scheduled notifications due for delivery."""
        now = now or datetime.now()
        cursor = self.db.execute("""
            SELECT id, user_id, notification_type, title, message, resource_type,
                   resource_id, priority, status, scheduled_for, sent_at, read_at, created_at
            FROM Notifications
            WHERE status = 'scheduled' AND scheduled_for <= ?
            ORDER BY scheduled_for ASC, id ASC
            LIMIT ?
        """, (now, limit))

        return [self._row_to_notification(row) for row in cursor.fetchall()]

    def mark_sent(self, notification_id: int, sent_at: Optional[datetime] = None) -> bool:
        """Mark a notification as sent."""
        sent_at = sent_at or datetime.now()
        with self.db:
            cursor = self.db.execute("""
                UPDATE Notifications
                SET status = 'sent', sent_at = ?
                WHERE id = ?
            """, (sent_at, notification_id))
            return cursor.rowcount > 0

    def mark_read(self, notification_id: int, read_at: Optional[datetime] = None) -> bool:
        """Mark a notification as read."""
        read_at = read_at or datetime.now()
        with self.db:
            cursor = self.db.execute("""
                UPDATE Notifications
                SET read_at = ?
                WHERE id = ?
            """, (read_at, notification_id))
            return cursor.rowcount > 0

    def _row_to_notification(self, row) -> Notification:
        """Convert a SQLite row or tuple to a notification."""
        return Notification(
            id=row[0],
            user_id=row[1],
            notification_type=row[2],
            title=row[3],
            message=row[4],
            resource_type=row[5],
            resource_id=row[6],
            priority=row[7],
            status=row[8],
            scheduled_for=datetime.fromisoformat(row[9]) if row[9] else None,
            sent_at=datetime.fromisoformat(row[10]) if row[10] else None,
            read_at=datetime.fromisoformat(row[11]) if row[11] else None,
            created_at=datetime.fromisoformat(row[12]),
        )
